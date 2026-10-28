import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from atlas.cli import main
from atlas.entities import index_mentions, suggest_merges
from atlas.entities.index import mentions, normalize, alias_matches
from atlas.graph.models import Node
from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store
from atlas.web_data import ReadModel


class EntityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        graph = GraphStore(self.root)
        self.addCleanup(graph.close)
        for nid, name in [('a', 'Ｆｉｃｔｉｏｎ Ｏａｋ'), ('b', 'fiction-oak'),
                          ('c', 'Fiction Oak Grove'), ('d', 'Fiction Oak'),
                          ('short', 'F'), ('hidden', 'Hidden Garden'), ('other', 'Fiction Fern')]:
            graph.put('nodes', Node(nid, 'concept', name, sensitive=nid == 'hidden'))
        graph.put('aliases', dict(alias_id='alias', node_id='a', name='Fiction Oak'))
        graph.close()
        corpus = Store(self.root)
        self.addCleanup(corpus.db.close)
        for i in range(3):
            corpus.upsert([Document(id=f'fiction-doc-{i}', source='fiction', ts=None if i == 0 else '2025-01-01',
                          text='Fiction Oak and Fiction Fern. Fiction Oak Grove. F Hidden Garden. Unindexed prose.',
                          meta={})])
        corpus.upsert([Document(id='sensitive', source='fiction', ts=None, text='Fiction Oak', meta={'sensitive': True})])
        corpus.db.close()

    def test_no_text_no_merge_graph_untouched_and_idempotent(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        counts = index_mentions(self.root)
        self.assertEqual(counts, {'nodes': 6, 'documents': 3, 'mentions': 18})
        result = suggest_merges(self.root)
        self.assertGreater(result['suggestions'], 0)
        self.assertEqual(index_mentions(self.root), counts)
        self.assertEqual(suggest_merges(self.root), result)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir() if p.name in before})
        with contextlib.closing(sqlite3.connect(self.root / 'entities.sqlite')) as db:
            columns = [r[1] for r in db.execute('PRAGMA table_info(mentions_index)')]
            self.assertEqual(columns, ['node_id', 'doc_id', 'offset', 'length', 'matched_alias', 'built_at'])
            self.assertNotIn('Unindexed prose', str(db.execute('SELECT * FROM mentions_index').fetchall()))
            rules = {r[0] for r in db.execute('SELECT rule FROM entity_merge_suggestions')}
            self.assertEqual(rules, {'normalized_name_equal', 'name_contains', 'cooccurrence'})
            self.assertEqual({r[0] for r in db.execute('SELECT status FROM entity_merge_suggestions')}, {'suggested'})
            self.assertEqual(db.execute("SELECT COUNT(*) FROM mentions_index WHERE node_id IN ('hidden','short') OR doc_id='sensitive'").fetchone()[0], 0)
        self.assertEqual(normalize(' Ｆiction—ＯAK '), 'fictionoak')

    def test_pointer_metadata_and_current_sensitivity(self):
        index_mentions(self.root)
        rows = ReadModel(self.root).snapshot()
        result = mentions(self.root, rows, 'a')
        self.assertEqual(len(result), 6)
        self.assertIsNone(result[0]['ts'])
        self.assertNotIn('quote', result[0])
        self.assertNotIn('text', result[0])
        with contextlib.closing(sqlite3.connect(self.root / 'corpus.sqlite')) as db:
            db.execute("UPDATE documents SET meta=? WHERE id='fiction-doc-0'", (json.dumps({'sensitive': True}),))
            db.commit()
        self.assertEqual(len(mentions(self.root, rows, 'a')), 4)

    def test_cli_requires_path_and_prints_counts_only(self):
        for command in ('index-mentions', 'suggest-merges'):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main([command, '--data-dir', str(self.root)]), 0)
            result = json.loads(out.getvalue())
            self.assertTrue(result)
            self.assertTrue(all(type(v) is int for v in result.values()))
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([command])

    def test_empty_graph_never_gains_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = GraphStore(tmp)
            graph.close()
            corpus = Store(tmp)
            corpus.db.close()
            self.assertEqual(index_mentions(tmp), {'nodes': 0, 'documents': 0, 'mentions': 0})
            self.assertEqual(suggest_merges(tmp), {'nodes': 0, 'suggestions': 0})


    def test_backlinks_use_drawer_and_reject_stale_slices_or_tokens(self):
        index_mentions(self.root)
        suggest_merges(self.root)
        model = ReadModel(self.root)
        payload = model.get('entity', {'id': 'a'})
        self.assertEqual(payload['mention_count'], 6)
        self.assertTrue(payload['merge_suggestions'])
        self.assertNotIn('Unindexed prose', json.dumps(payload))
        self.assertNotIn('"quote":', json.dumps(payload))
        request = {'kind': 'mentions', 'id': 'a', 'index': '0', 'field': payload['mentions'][0]['token']}
        evidence = model.get('evidence', request)
        self.assertEqual(evidence['quote'], 'Fiction Oak')
        self.assertEqual(evidence['ref']['kind'], 'char_span')
        with self.assertRaises(KeyError):
            model.get('evidence', dict(request, field='arbitrary-token'))
        with self.assertRaises(KeyError):
            model.get('evidence', dict(request, index='-1'))
        with contextlib.closing(sqlite3.connect(self.root / 'corpus.sqlite')) as db:
            db.execute("UPDATE documents SET text='changed fictional text' WHERE id='fiction-doc-0'")
            db.commit()
        with self.assertRaises(ValueError):
            model.get('evidence', request)
        with contextlib.closing(sqlite3.connect(self.root / 'corpus.sqlite')) as db:
            db.execute("UPDATE documents SET meta=? WHERE id='fiction-doc-0'", (json.dumps({'sensitive': True}),))
            db.commit()
        with self.assertRaises(KeyError):
            ReadModel(self.root, sensitive=True).get('evidence', request)

    def test_absent_index_has_explicit_empty_state_without_creating_file(self):
        payload = ReadModel(self.root).get('entity', {'id': 'a'})
        self.assertFalse(payload['mentions_index_available'])
        self.assertEqual(payload['mention_count'], 0)
        self.assertEqual(payload['merge_suggestions'], [])
        self.assertFalse((self.root / 'entities.sqlite').exists())


    def test_short_names_ascii_boundaries_and_unicode_offsets(self):
        self.assertEqual(list(alias_matches('cloak oak oakwood', 'oak')), [6])
        self.assertEqual(list(alias_matches('F Fo', 'Fo')), [])
        self.assertEqual(list(alias_matches('雨 雨水', '雨')), [])
        self.assertEqual(list(alias_matches('虚构🌱雨水', '雨水')), [3])
