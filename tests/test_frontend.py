import json
import tempfile
import unittest
from pathlib import Path

from atlas.cli import build
from atlas.store import Store
from examples.tasks_demo.seed_m5 import seed


class FrontendExportTests(unittest.TestCase):
    def test_graph_export_and_correction_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed(root)
            row = dict(correction_id='correction:synthetic-ui', prop_id='demo-prop',
                       verdict='wrong', note='Synthetic correction', observed_at='2025-01-01')
            (root / 'corrections.jsonl').write_text(json.dumps(row)+'\n', encoding='utf-8')
            store = Store(root)
            try:
                build(dict(data_dir=str(root), out_dir=str(root/'site'), config_dir='.',
                           lenses=[dict(lens='judgment_lines'), dict(lens='timeline')]), store)
            finally:
                store.db.close()
            data = json.loads((root/'site/atlas.json').read_text(encoding='utf-8'))
            self.assertEqual(set(data) & {'nodes', 'edges', 'propositions', 'lenses'},
                             {'nodes', 'edges', 'propositions', 'lenses'})
            self.assertEqual(len(data['nodes']), 3)
            self.assertEqual(len(data['edges']), 2)
            prop = next(p for p in data['propositions'] if p['prop_id']=='demo-prop')
            self.assertEqual(prop['status'], 'rejected')
            self.assertEqual(prop['suppressed_by'], row['correction_id'])
            self.assertTrue(any(p['sensitive'] for p in data['propositions']))
            lines = data['lenses'][0]['view']['lines']
            self.assertEqual(next(l for l in lines if l['topic_node_id']=='demo-topic')['timeline'][0]['statement_id'], 'demo-prop')
            script = (root/'site/data.js').read_text(encoding='utf-8')
            self.assertEqual(json.loads(script.removeprefix('window.ATLAS_DATA=').removesuffix(';')), data)
            self.assertTrue((root/'site/index.html').exists())

    def test_empty_graph_exports_without_invented_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                build(dict(data_dir=directory, out_dir=directory, lenses=[]), store)
            finally:
                store.db.close()
            data = json.loads((Path(directory)/'atlas.json').read_text(encoding='utf-8'))
            for field in ('nodes', 'edges', 'propositions', 'lenses'):
                self.assertEqual(data[field], [])
