"""M7 regressions: synthetic sources, local stores, no agent/network calls."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from atlas.cli import main
from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.evidence import resolve_quote
from atlas.tasks.lines import make_lines
from atlas.tasks.merge import merge, records
from atlas.tasks.queue import Queue, read_json, instructions_for
from atlas.tasks.runners import prompt_text
from atlas.tasks.validate import check_schema, schema_for, accept_items, validate_output


class LightModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.addCleanup(self.store.db.close)
        self.graph = GraphStore(self.root)
        self.addCleanup(self.graph.close)
        self.text = 'Fictional garden，\n  blue flowers！ Garden. Garden.'
        self.store.upsert([Document('fiction', 'synthetic', '2024-01-01', self.text)])
        self.queue = Queue(self.root, self.store)
        self.task = self.queue.make()[0]
        self.payload = read_json(self.queue.locate(self.task)[1] / 'input.json')

    def entity(self, identity='e', quote='Garden.'):
        return dict(tmp_id=identity, type='place', name='Fictional garden', aliases=['Garden'],
                    evidence=[dict(doc_id='fiction', quote=quote)])

    def output(self):
        return dict(entities=[self.entity()], relations=[], statements=[])

    def submit(self, output):
        path = self.root / 'response.json'
        path.write_text(json.dumps(output, ensure_ascii=False), encoding='utf-8')
        return self.queue.submit(self.task, path)

    def test_exact_normalized_unicode_offsets_and_first_unused(self):
        docs = {'fiction': self.text}
        used = set()
        for expected in (self.text.index('Garden.'), self.text.rindex('Garden.'), self.text.index('Garden.')):
            pointer = resolve_quote(dict(doc_id='fiction', quote='Garden.'), docs, used)
            self.assertEqual(pointer['span'], [expected, expected + 7])
        pointer = resolve_quote(dict(doc_id='fiction', quote='garden, blue flowers!'), docs, set())
        start, end = pointer['span']
        self.assertEqual(self.text[start:end], 'garden，\n  blue flowers！')
        self.assertEqual(pointer['quote_hash'], hashlib.sha256(self.text[start:end].encode()).hexdigest()[:12])
        # Exact matches take precedence over earlier normalized matches.
        self.assertEqual(resolve_quote(dict(doc_id='d', quote='a b'), {'d': 'a  b / a b'}, set())['span'], [7, 10])

    def test_archive_normalized_output_graph_and_replay(self):
        output = self.output()
        output['entities'][0]['evidence'] *= 2
        self.assertEqual(self.submit(output)['state'], 'accepted')
        path = self.queue.locate(self.task)[1]
        saved = read_json(path / 'output.json')
        self.assertNotIn('"quote":', json.dumps(saved))
        self.assertNotEqual(*[e['span'] for e in saved['entities'][0]['evidence']])
        self.assertIn(output, [read_json(p) for p in path.glob('attempts/*/output.json')])
        self.assertEqual(self.queue.validate(self.task)['state'], 'accepted')
        merge(self.queue, self.graph, self.task)
        self.assertNotIn('"quote":', json.dumps(records(self.graph, 'nodes')))
        self.assertEqual(merge(self.queue, self.graph, self.task)['state'], 'noop')

    def test_partial_evidence_and_dependent_items(self):
        output = self.output()
        output['entities'][0]['evidence'].append(dict(doc_id='fiction', quote='invented'))
        output['entities'].append(self.entity('bad', 'invented'))
        output['relations'] = [dict(src='e', dst='bad', type='near', evidence=[dict(doc_id='fiction', quote='Garden.')])]
        result = self.submit(output)
        self.assertEqual(result['state'], 'accepted')
        self.assertTrue(result['partial'])
        self.assertEqual(result['counts'], {'accepted': 1, 'dropped': 2})
        self.assertNotIn('invented', json.dumps(result))
        self.assertNotIn('"quote":', (self.queue.locate(self.task)[1] / 'output.json').read_text())

    def test_invalid_quotes_and_scope(self):
        self.store.upsert([Document('outside', 'synthetic', '2024-01-01', 'Garden.')])
        for pointer in (dict(doc_id='fiction', quote=''),
                        dict(doc_id='fiction', quote='x' * 61), dict(doc_id='fiction', quote='  '),
                        dict(doc_id='fiction', quote='GARDEN.'),
                        dict(doc_id=[], quote='Garden.'), dict(doc_id='fiction', quote=123)):
            with self.subTest(pointer=pointer):
                output = self.output()
                output['entities'][0]['evidence'] = [pointer]
                self.assertEqual(self.submit(output)['state'], 'rejected')

    def test_legacy_pointer_unchanged_and_reserved(self):
        start = self.text.index('Garden.')
        pointer = dict(doc_id='fiction', span=[start, start+7], quote_hash=hashlib.sha256(b'Garden.').hexdigest()[:12])
        output = self.output()
        output['entities'][0]['evidence'].append(pointer)
        self.assertEqual(self.submit(output)['state'], 'accepted')
        evidence = read_json(self.queue.locate(self.task)[1] / 'output.json')['entities'][0]['evidence']
        self.assertEqual(evidence[1], pointer)
        self.assertEqual(evidence[0]['span'][0], self.text.rindex('Garden.'))
        pointer['quote_hash'] = '0' * 12
        self.assertEqual(self.submit(output)['state'], 'rejected')

    def test_name_alias_unknown_and_ambiguous_references(self):
        output = self.output()
        output['relations'] = [dict(src='Fictional garden', dst='Garden', type='near', evidence=[dict(doc_id='fiction', quote='Garden.')]),
                               dict(src='missing', dst='e', type='near', evidence=[dict(doc_id='fiction', quote='Garden.')])]
        output['statements'] = [dict(tmp_id='s', kind='fact', text='Fictional garden.', about=['Garden'], confidence=.5,
                                     evidence=[dict(doc_id='fiction', quote='Garden.')]),
                                dict(tmp_id='bad', kind='fact', text='Fictional garden.', about=['missing'], confidence=.5,
                                     evidence=[dict(doc_id='fiction', quote='Garden.')])]
        self.assertEqual(self.submit(output)['counts'], {'accepted': 3, 'dropped': 2})
        accepted = read_json(self.queue.locate(self.task)[1] / 'accepted.json')
        self.assertEqual(accepted['relations'][0]['src'], 'e')
        self.assertEqual(accepted['statements'][0]['about'], ['e'])
        output['entities'].append(self.entity('e2'))
        self.assertEqual(self.submit(output)['counts'], {'accepted': 2, 'dropped': 4})

    def test_proposition_support_counter_and_direct_validation(self):
        prop = dict(prop_id='p', text='Fictional garden.', kind='fact', subject_node_ids=['n'],
                    evidence=[dict(doc_id='fiction', quote='Garden.')] * 2,
                    counter_evidence=[dict(doc_id='fiction', quote='blue flowers！')],
                    confidence=.5, valid_from=None, valid_to=None, status='proposed')
        payload = dict(self.payload, node_id='n', subgraph={'nodes':[{'node_id':'n'}]}, propositions=[], corrections=[])
        output = {'ops':[{'op':'ADD', 'prop': prop}]}
        kept, errors, fatal, counts = accept_items('gen_propositions', output, payload, self.store)
        self.assertFalse(fatal, errors)
        self.assertEqual(counts['accepted'], 1)
        self.assertNotIn('"quote":', json.dumps(kept))
        self.assertEqual(validate_output('gen_propositions', kept, payload, self.store), [])
        # Existing counter evidence still cannot be discarded by an unresolved quote.
        payload['propositions'] = [copy.deepcopy(prop)]
        output['ops'][0]['op'] = 'UPDATE'
        prop['counter_evidence'] = [dict(doc_id='fiction', quote='invented')]
        self.assertTrue(accept_items('gen_propositions', output, payload, self.store)[2])

    def test_schema_forms_and_quote_limit(self):
        schema = schema_for('extract_entities.output')['properties']['entities']['items']['properties']['evidence']['items']
        self.assertEqual(check_schema(dict(doc_id='fiction', quote='x'*60), schema), [])
        for pointer in (dict(doc_id='fiction', quote='x'*61), dict(doc_id='fiction'),
                        dict(doc_id='fiction', quote='Garden.', span=[0,7], quote_hash='0'*12)):
            self.assertTrue(check_schema(pointer, schema))

    def test_credential_filtered_source_cannot_be_recovered(self):
        secret = 'sk-' + 'fictional' * 3
        self.store.upsert([Document('fiction', 'synthetic', '2024-01-01', secret)])
        self.assertIsNone(resolve_quote(dict(doc_id='fiction', quote=secret),
                                       {d.id:d.text for d in self.store.all()}, set()))

    def test_prompts_all_kinds(self):
        for kind in ('extract_entities', 'resolve_entities', 'gen_propositions', 'cluster_lens', 'verify'):
            instructions = instructions_for(kind)
            self.assertIn('{doc_id, quote}', instructions)
            self.assertIn('Do not compute hashes', instructions)
            self.assertIn('must exist in entities', instructions)
        prompt = prompt_text(self.queue.locate(self.task)[1])
        self.assertNotIn('compute spans and hashes', prompt)
        self.assertIn('Do not compute hashes', prompt)

    def test_lines_default_custom_and_char_limits(self):
        self.assertEqual(make_lines(self.queue, self.graph), [])
        for index in range(121):
            self.graph.put('statements', dict(statement_id=f's{index:03}', text='Fictional garden.',
                ts=None, speaker=None, about=['n'], evidence=[]))
        for limit, chars, expected in ((60,40000,[60,60,1]), (40,40000,[40,40,40,1]), (60,1,[1]*121)):
            queue = Queue(self.root, self.store, lines_batch=limit, batch_chars=chars)
            tasks = make_lines(queue, self.graph)
            sizes = [len(read_json(queue.locate(t)[1] / 'input.json')['statements']) for t in tasks]
            self.assertEqual(sizes, expected)
            self.assertEqual(make_lines(queue, self.graph), tasks)
        for invalid in (0, -1, True, 1.5, '60'):
            with self.assertRaises(ValueError):
                Queue(self.root, self.store, lines_batch=invalid)

    def test_cli_lines_batch_configuration(self):
        config = self.root / 'demo.toml'
        config.write_text('[tasks]\nlines_batch = 7\n', encoding='utf-8')
        cfg = dict(data_dir=str(self.root), out_dir=str(self.root/'site'), config_dir=str(self.root), tasks={'lines_batch':7})
        with patch('atlas.cli.C.load', return_value=cfg), patch('atlas.tasks.lines.make_lines', return_value=[]) as make, redirect_stdout(StringIO()):
            self.assertEqual(main(['tasks','make','--kind','cluster_lens','--config',str(config)]), 0)
        self.assertEqual(make.call_args.args[0].lines_batch, 7)
