"""M9 synthetic-only regression coverage."""
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from atlas.cli import main, ingest, build
from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.seed import import_seed, reference_rows
from atlas.store import Store
from atlas.tasks.evidence import resolve_lines
from atlas.tasks.guard import sanitize, FilterCounter
from atlas.tasks.lines import make_lines
from atlas.tasks.queue import Queue, read_json, instructions_for
from atlas.tasks.validate import accept_items, check_schema, schema_for


class M9Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.addCleanup(self.store.db.close)
        self.graph = GraphStore(self.root)
        self.addCleanup(self.graph.close)
        self.text = 'Fictional A: Plant flowers.\r\nFictional B: Prefer trees.\nThird line.\n'
        self.store.upsert([Document('fiction', 'synthetic', '2024-01-01', self.text)])
        self.queue = Queue(self.root, self.store)

    def test_line_bounds_and_hash(self):
        docs = {'fiction': self.text}
        pointer = resolve_lines(dict(doc_id='fiction', lines=[2, 3]), docs)
        start = self.text.index('Fictional B')
        self.assertEqual(pointer['span'], [start, len(self.text)])
        self.assertEqual(pointer['quote_hash'], hashlib.sha256(self.text[start:].encode()).hexdigest()[:12])
        for bounds in ([0, 1], [2, 1], [1, 4], [True, 2], [1], '1,2'):
            self.assertIsNone(resolve_lines(dict(doc_id='fiction', lines=bounds), docs))
        self.assertIsNone(resolve_lines(dict(doc_id='outside', lines=[1, 1]), docs))
        self.assertIsNone(resolve_lines(dict(doc_id='d', lines=[1, 7]), {'d': 'a\n' * 7}))
        self.assertIsNotNone(resolve_lines(dict(doc_id='d', lines=[1, 6]), {'d': 'a\n' * 7}))

    def test_extract_partial_and_all_invalid(self):
        task = self.queue.make()[0]
        path = self.queue.locate(task)[1]
        payload = read_json(path / 'input.json')
        self.assertEqual(payload['documents'][0]['text'], self.text)
        self.assertIn('L2: Fictional B:', payload['documents'][0]['numbered_text'])
        good = dict(tmp_id='e', type='topic', name='Fictional garden', aliases=[],
                    evidence=[dict(doc_id='fiction', lines=[1, 1]), dict(doc_id='outside', lines=[1, 1]),
                              dict(doc_id='fiction', span=[0, 9999], quote_hash='0' * 12),
                              dict(doc_id='outside', span=[0, 1], quote_hash='0' * 12)])
        bad = dict(good, tmp_id='bad', evidence=[dict(doc_id='fiction', lines=[8, 9])])
        output = dict(entities=[good, bad], relations=[], statements=[])
        self.assertEqual(check_schema(output, schema_for('extract_entities.output')), [])
        response = self.root / 'response.json'
        response.write_text(json.dumps(output), encoding='utf-8')
        result = self.queue.submit(task, response)
        self.assertEqual(result['state'], 'accepted')
        self.assertEqual(result['counts'], dict(accepted=1, dropped=1))
        saved = read_json(self.queue.locate(task)[1] / 'accepted.json')
        self.assertEqual(len(saved['entities'][0]['evidence']), 1)
        self.assertIn('span', saved['entities'][0]['evidence'][0])
        response.write_text(json.dumps(dict(entities=[bad], relations=[], statements=[])), encoding='utf-8')
        self.assertEqual(self.queue.submit(task, response)['state'], 'rejected')
        prompt = instructions_for('extract_entities')
        self.assertIn('EVERY opinion', prompt)
        self.assertIn('named exactly as shown', prompt)
        self.assertIn('own words', prompt)

    def test_proposition_line_input_and_support(self):
        payload = dict(node_id='garden', subgraph=dict(nodes=[dict(node_id='garden', type='topic', name='Garden')], edges=[]),
                       propositions=[], corrections=[], documents=[d.to_dict() for d in self.store.all()])
        task = self.queue.make('gen_propositions', payload)[0]
        packed = read_json(self.queue.locate(task)[1] / 'input.json')
        self.assertIn('L1:', packed['documents'][0]['numbered_text'])
        prop = dict(prop_id='p', text='Fictional garden preferences', subject_node_ids=['garden'],
                    evidence=[dict(doc_id='fiction', lines=[1, 1]), dict(doc_id='fiction', lines=[2, 2]),
                              dict(doc_id='missing', lines=[1, 1])], counter_evidence=[], confidence=.4,
                    kind='preference', status='proposed', valid_from=None, valid_to=None)
        kept, errors, fatal, counts = accept_items('gen_propositions', dict(ops=[dict(op='ADD', prop=prop)]), packed, self.store)
        self.assertFalse(fatal, errors)
        self.assertEqual(len(kept['ops'][0]['prop']['evidence']), 2)

    def test_identifier_values_untouched_and_text_counted(self):
        value = '4' + '1' * 15
        fields = {k: [value] if k.endswith('ids') else value for k in ('id', 'ids', 'doc_id', 'msg_ids', 'node_ids')}
        original = copy.deepcopy(fields)
        fields.update(text=value, meta={'event_id': value, 'note': value})
        counter = FilterCounter()
        with self.assertNoLogs('atlas.tasks.guard'):
            filtered = sanitize(fields, counter)
        for key, item in original.items():
            self.assertEqual(filtered[key], item)
        self.assertEqual(filtered['text'], '[CREDENTIAL]')
        self.assertEqual(filtered['meta']['event_id'], value)
        self.assertEqual(counter.lines, 2)

    def test_ingest_single_summary(self):
        class Adapter:
            def read(self):
                return [Document('fiction-log', 'synthetic', '2024-01-01', 'password' + '=fiction\npassword' + '=fiction')]
        cfg = dict(data_dir=str(self.root), sources=[dict(adapter='fiction'), dict(adapter='fiction')])
        with patch('atlas.cli.R.load', return_value=Adapter), self.assertLogs('atlas.tasks.guard') as logs, redirect_stdout(StringIO()):
            st = ingest(cfg)
            st.db.close()
        self.assertEqual(len(logs.output), 1)
        self.assertIn('credential filter: 4 lines in 2 documents', logs.output[0])
        self.assertNotIn('password', logs.output[0])

    def test_shift_repair_and_schema(self):
        sources = [dict(statement_id=f's{i}', ts=f'2024-01-0{i+1}', about=['garden']) for i in range(4)]
        payload = dict(documents=[], statements=sources, propositions=[])
        points = [dict(statement_id=s['statement_id'], reason='Fictional reason', outcome='unknown',
                       outcome_statement_ids=[], outcome_reason='') for s in sources]
        points[2]['shift'] = 'invalid'
        points[3]['shift'] = 'strengthen'
        output = dict(lines=[dict(line_id='l', title='Garden', topic='garden', timeline=points)])
        self.assertTrue(check_schema(output, schema_for('cluster_lens.output')))
        kept, errors, fatal, counts = accept_items('cluster_lens', output, payload, self.store)
        self.assertFalse(fatal, errors)
        self.assertEqual(counts['shift_repairs'], 2)
        self.assertEqual([p['shift'] for p in kept['lines'][0]['timeline']], ['first', 'unclear', 'unclear', 'strengthen'])
        self.assertEqual(check_schema(kept, schema_for('cluster_lens.output')), [])

    def test_legacy_cli_storage_isolation_export_and_opt_in(self):
        self.graph.put('nodes', dict(node_id='a', name='Built garden', type='topic'))
        before = self.graph.stats()
        seed = dict(nodes=[dict(id='a', name='Reference garden'), dict(id='b')], edges=[
            dict(s='a', t='b', r=' SUPPORTS! ', date='2024-01-01'),
            dict(s='a', t='b', r='Mystery link'), dict(s='b', t='a', r='Collaborates')])
        source = self.root / 'seed.json'
        source.write_text(json.dumps(seed), encoding='utf-8')
        config = self.root / 'config.toml'
        config.write_text('[seed.relation_synonyms]\ncollaborates = "works_on"\n', encoding='utf-8')
        with patch.dict('os.environ', ATLAS_DATA_DIR=str(self.root), ATLAS_OUT_DIR=str(self.root / 'site')), redirect_stdout(StringIO()) as out:
            self.assertEqual(main(['seed', 'import', '--file', str(source), '--config', str(config)]), 0)
        self.assertEqual(json.loads(out.getvalue()), dict(nodes=2, edges=3, mapped=2, unmapped=1, distinct_original_relations=3))
        self.assertEqual(self.graph.stats(), before)
        self.assertEqual(self.graph.get('nodes', 'a')['name'], 'Built garden')
        refs = reference_rows(self.graph)
        self.assertTrue(all(r['source']=='legacy' and r['status']=='reference' for rows in refs.values() for r in rows))
        self.assertEqual(next(e for e in refs['edges'] if 'legacy_relation' in e)['r'], 'related_to')
        import_seed(self.graph, seed, {'collaborates':'works_on'})
        self.assertEqual(reference_rows(self.graph), refs)
        self.assertEqual(make_lines(self.queue, self.graph), [])
        self.store.upsert([Document('legacy-doc', 'legacy', '2024-01-01', 'Fictional reference.')])
        task = self.queue.make()[0]
        self.assertEqual(read_json(self.queue.locate(task)[1] / 'task.json')['doc_ids'], ['fiction'])
        opted = Queue(self.root, self.store, include_legacy=True)
        task = opted.make()[0]
        self.assertIn('legacy-doc', read_json(opted.locate(task)[1] / 'task.json')['doc_ids'])
        with redirect_stdout(StringIO()):
            build(dict(data_dir=str(self.root), out_dir=str(self.root / 'site'), lenses=[]), self.store)
        exported = json.loads((self.root / 'site/atlas.json').read_text(encoding='utf-8'))
        self.assertEqual(exported['legacy'], refs)
        self.assertEqual(len(exported['nodes']), 1)
        html = (self.root / 'site/index.html').read_text(encoding='utf-8')
        self.assertIn('\u65e7\u7248\u53c2\u8003</summary>', html)
        self.assertIn("unclear:'\u672a\u5224\u660e'", html)

    def test_invalid_seed_atomic(self):
        before = reference_rows(self.graph)
        with self.assertRaises(ValueError):
            import_seed(self.graph, dict(nodes=[dict(id='a')], edges=[dict(s='a', t='missing', r='supports')]))
        self.assertEqual(reference_rows(self.graph), before)
