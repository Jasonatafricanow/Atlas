"""M10 regressions use fictional documents and disposable local stores only."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from atlas.graph.store import GraphStore
from atlas.lenses.judgment_lines import grouped_lines, shift_stats
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.evidence import normalize_output
from atlas.tasks.lines import repair_lines
from atlas.tasks.merge import merge
from atlas.tasks.queue import Queue, read_json, task_id
from atlas.tasks.validate import check_schema, schema_for


class M10Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root)
        self.addCleanup(self.store.db.close)
        self.graph = GraphStore(self.root)
        self.addCleanup(self.graph.close)
        self.text = '[2024-01-01 10:00] Fictional A: Garden.\r\nSecond fictional line.\n'
        self.store.upsert([Document('fiction-long', 'synthetic', '2024-01-01', self.text)])
        self.queue = Queue(self.root, self.store)

    def test_compact_tasks_and_old_identity(self):
        old = task_id('extract_entities', ['fiction-long'], '5', '5')
        task = self.queue.make()[0]
        self.assertNotEqual(task, old)
        payload = dict(node_id='garden', subgraph={}, propositions=[], corrections=[],
                       documents=[d.to_dict() for d in self.store.all()])
        for kind, identifier in [('extract_entities', task),
                                 ('gen_propositions', self.queue.make('gen_propositions', payload)[0])]:
            path = self.queue.locate(identifier)[1]
            packed = read_json(path / 'input.json')
            doc = packed['documents'][0]
            self.assertNotIn('text', doc)
            self.assertEqual(doc['ref'], 'd1')
            self.assertTrue(doc['numbered_text'].startswith('[d1] L1: '))
            self.assertEqual(check_schema(packed, schema_for(kind + '.input')), [])
            self.assertIn('cite documents only by their ref', (path / 'INSTRUCTIONS.md').read_text())
        self.assertIn('text', payload['documents'][0])

    def test_refs_are_sorted_and_restart_per_batch(self):
        self.store.upsert([Document('aaa-fiction', 'synthetic', '2024-01-01', 'Fictional tree.')])
        task = self.queue.make()[0]
        docs = read_json(self.queue.locate(task)[1] / 'input.json')['documents']
        self.assertEqual([(d['id'], d['ref']) for d in docs], [('aaa-fiction', 'd1'), ('fiction-long', 'd2')])
        queue = Queue(self.root, self.store, batch_docs=1)
        for identifier in queue.make():
            self.assertEqual(read_json(queue.locate(identifier)[1] / 'input.json')['documents'][0]['ref'], 'd1')

    def test_all_evidence_forms_and_single_document_repair(self):
        payload = {'documents': [{'id': 'fiction-long', 'ref': 'd1'}]}
        end = self.text.index('\n') + 1
        canonical = dict(doc_id='fiction-long', span=[0, end],
                         quote_hash=hashlib.sha256(self.text[:end].encode()).hexdigest()[:12])
        for identifier in ('d1', 'fiction-long', 'invented-document'):
            for evidence in (dict(doc_id=identifier, lines=[1, 1]),
                             dict(doc_id=identifier, quote=self.text[:end]),
                             dict(canonical, doc_id=identifier)):
                output = {'evidence': [evidence]}
                self.assertEqual(normalize_output(output, payload, self.store), [])
                self.assertEqual(output['evidence'], [canonical])
                self.assertEqual(normalize_output(output, payload, self.store), [])

    def test_unknown_multiple_documents_and_missing_store_are_not_guessed(self):
        payload = {'documents': [{'id': 'fiction-long', 'ref': 'd1'}, {'id': 'absent', 'ref': 'd2'}]}
        for identifier in ('invented-document', 'd2'):
            output = {'evidence': [dict(doc_id=identifier, lines=[1, 1])]}
            self.assertTrue(normalize_output(output, payload, self.store))
            self.assertEqual(output['evidence'], [])
        output = {'evidence': [dict(doc_id='invented-document', lines=[1, 1])]}
        normalize_output(output, {'documents': [{'id': 'absent'}]}, self.store)
        self.assertEqual(output['evidence'], [])

    def test_compact_extract_merge_preserves_attribution_and_replay(self):
        identifier = self.queue.make()[0]
        evidence = [dict(doc_id='d1', lines=[1, 1])]
        output = dict(entities=[dict(tmp_id='garden', type='topic', name='Fictional garden',
                                    aliases=[], evidence=evidence)], relations=[], statements=[
            dict(tmp_id='s', about=['garden'], kind='opinion', text='Fictional garden view.',
                 confidence=.4, evidence=evidence)])
        path = self.root / 'output.json'
        path.write_text(json.dumps(output), encoding='utf-8')
        self.assertEqual(self.queue.submit(identifier, path)['state'], 'accepted')
        merge(self.queue, self.graph, identifier)
        statement = json.loads(self.graph.db.execute('SELECT data FROM statements').fetchone()[0])
        self.assertEqual(statement['speaker'], 'Fictional A')
        self.assertEqual(statement['ts'], '2024-01-01T10:00:00')
        self.assertEqual(statement['evidence'][0]['doc_id'], 'fiction-long')
        self.assertEqual(merge(self.queue, self.graph, identifier)['state'], 'noop')

    def test_shift_provenance_survives_revalidation_and_display(self):
        sources = [dict(statement_id=f's{i}', ts=f'2024-01-0{i+1}', about=['garden'],
                        text='Fictional garden.') for i in range(3)]
        points = [dict(statement_id=s['statement_id'], shift=shift, reason='Fictional reason',
                       outcome='unknown', outcome_statement_ids=[], outcome_reason='')
                  for s, shift in zip(sources, ('first', None, 'unclear'))]
        output = dict(lines=[dict(line_id='fiction', topic='garden', title='Garden', timeline=points)])
        payload = dict(statements=sources, propositions=[])
        repair_lines(output, payload)
        before = copy.deepcopy(output)
        repair_lines(output, payload)
        self.assertEqual(output, before)
        self.assertEqual([p['shift_source'] for p in points], ['model', 'repaired', 'model'])
        for source in sources:
            self.graph.put('statements', source)
        self.graph.put('nodes', dict(node_id='garden', type='topic', name='Garden'))
        self.graph.put('lines', dict(output['lines'][0], topic_node_id='garden'))
        self.assertEqual(self.graph.stats()['displayed_shift_labels'], dict(model=2, repaired=1, fallback=0))
        graph = dict(nodes=[], propositions=[], statements=sources, lines=[])
        lines = grouped_lines(graph)
        self.assertEqual([p['shift'] for p in lines[0]['timeline']], ['first', 'unclear', 'unclear'])
        self.assertEqual(shift_stats(lines), dict(model=0, repaired=0, fallback=3))
        self.assertEqual(grouped_lines(dict(nodes=[], propositions=[], statements=[], lines=[])), [])
        orphan = dict(sources[0], about=[])
        self.assertEqual(grouped_lines(dict(nodes=[], propositions=[], statements=[orphan], lines=[])), [])

    def test_canonical_id_takes_precedence_over_colliding_ref(self):
        self.store.upsert([Document('d1', 'synthetic', '2024-01-01', 'Fictional tree.')])
        payload = {'documents': [{'id': 'fiction-long', 'ref': 'd1'}, {'id': 'd1', 'ref': 'd2'}]}
        output = {'evidence': [dict(doc_id='d1', lines=[1, 1])]}
        self.assertEqual(normalize_output(output, payload, self.store), [])
        self.assertEqual(output['evidence'][0]['doc_id'], 'd1')
        self.assertEqual(output['evidence'][0]['quote_hash'], hashlib.sha256(b'Fictional tree.').hexdigest()[:12])


if __name__ == '__main__':
    unittest.main()
