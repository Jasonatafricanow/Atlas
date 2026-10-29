"""Fictional disposable fixtures only; no models or real data paths."""
import json
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from atlas.backends.digests import DigestSource
from atlas.web_data import ReadModel
from examples.tasks_demo.seed_ui_v2 import seed


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def fixture(root, data):
    rows = ReadModel(data).snapshot()
    points = [dict(ref=s["statement_id"], ts=s["ts"], text=s["text"]) for s in rows["statements"]]
    evidence = [{"doc_id": "fiction-doc-0", "quote": "先在小花圃试种"}]
    digest = {"sentences": [
        dict(section="what", text="虚构花圃试种计划。", evidence=evidence),
        dict(section="view", text="你计划先试种。", stance="计划", evidence=evidence),
        dict(section="evolution", text="从小花圃开始。", ts="2025-01-12", evidence=evidence),
        dict(section="record", text="结果尚未核验。", outcome="unknown", evidence=evidence)]}
    write(root, "A_merged.json", {"merged": [{"title": "虚构合并综述", "reason": "同一试种计划",
                                             "member_line_ids": ["fiction-line-0", "fiction-line-1"]}]})
    write(root, "B_line1/input.json", {"title": "虚构合并综述", "points": points})
    write(root, "B_line1.json", digest)
    write(root, "C_entity1/input.json", {"name": "花圃的试种与扩种", "type": "topic", "statements": points})
    write(root, "C_entity1.json", digest)
    return digest


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "fiction-data"
        self.root = Path(self.tmp.name) / "fiction-digests"
        seed(self.data)
        self.output = fixture(self.root, self.data)

    def source(self, sensitive=False):
        return DigestSource(self.root, ReadModel(self.data, sensitive))

    def test_read_mapping_entity_home_and_readonly(self):
        before = {p: p.read_bytes() for p in Path(self.tmp.name).rglob("*") if p.is_file()}
        source = self.source()
        digest = source.for_line("fiction-line-0")
        self.assertEqual(digest["validation"], {"valid": 4, "total": 4, "dropped": 0})
        self.assertEqual(digest, source.for_line("fiction-line-1"))
        self.assertEqual(digest["merged_title"], "虚构合并综述")
        self.assertEqual(source.for_entity("fiction-garden")["statement_count"], 3)
        self.assertIsNone(source.for_entity("fiction-rain"))
        self.assertEqual(len(source.home_views(100)), 6)
        self.assertEqual(len(source.home_views(2)), 2)
        self.assertEqual(source.home_views(0), [])
        self.assertEqual(before, {p: p.read_bytes() for p in Path(self.tmp.name).rglob("*") if p.is_file()})

    def test_missing_broken_and_bad_shapes_fall_back(self):
        for value in (None, [], {}, {"sentences": "bad"}, {"sentences": []}):
            write(self.root, "B_line1.json", value)
            self.assertIsNone(self.source().for_line("fiction-line-0"))
        (self.root / "B_line1.json").write_text("{bad", encoding="utf-8")
        self.assertIsNone(self.source().for_line("fiction-line-0"))
        (self.root / "B_line1.json").unlink()
        self.assertIsNone(self.source().for_line("fiction-line-0"))
        write(self.root, "B_line1.json", self.output)
        (self.root / "B_line1/input.json").unlink()
        self.assertIsNone(self.source().for_line("fiction-line-0"))
        self.assertIsNotNone(self.source().for_entity("fiction-garden"))

    def test_bad_sentences_drop_with_count_and_no_context(self):
        self.output["sentences"] += [None, {"section": "what"},
            dict(section="what", text="错误数字 999", evidence=self.output["sentences"][0]["evidence"]),
            dict(section="what", text="虚构错误引用", evidence=[{"doc_id": "fiction-doc-0", "quote": "不存在的引文"}])]
        write(self.root, "B_line1.json", self.output)
        with self.assertLogs("atlas.backends.digests", level="INFO") as log:
            digest = self.source().for_line("fiction-line-0")
        self.assertEqual(digest["validation"], {"valid": 4, "total": 8, "dropped": 4})
        self.assertIn("4/8", " ".join(log.output))
        self.assertNotIn("错误数字", " ".join(log.output))
        for sentence in digest["sentences"]:
            self.assertEqual(set(sentence["evidence"][0]), {"doc_id", "quote"})
        self.assertNotIn("context", json.dumps(digest))

    def test_drawer_authorizes_quote_and_reads_context_only_on_demand(self):
        params = {"kind": "digest_line", "id": "fiction-line-1",
                  "doc_id": "fiction-doc-0", "quote": "先在小花圃试种"}
        evidence = self.source().evidence(params)
        self.assertEqual(evidence["quote"], params["quote"])
        self.assertEqual(evidence["before"], "虚构记录：")
        with self.assertRaises(KeyError):
            self.source().evidence(dict(params, quote="虚构记录"))

    def test_entity_name_type_must_match_unambiguously(self):
        from atlas.graph.store import GraphStore
        graph = GraphStore(self.data)
        row = graph.get("nodes", "fiction-garden")
        row["node_id"] = "fiction-duplicate"
        graph.put("nodes", row)
        graph.close()
        with self.assertLogs("atlas.backends.digests", level="INFO"):
            self.assertIsNone(self.source().for_entity("fiction-garden"))

    def test_hidden_input_withheld_and_toggle_restores(self):
        from atlas.graph.store import GraphStore
        graph = GraphStore(self.data)
        row = graph.get("statements", "fiction-s1")
        row["sensitive"] = True
        graph.put("statements", row)
        graph.close()
        self.assertIsNone(self.source().for_line("fiction-line-0"))
        self.assertIsNone(self.source().for_entity("fiction-garden"))
        self.assertIsNotNone(self.source(True).for_line("fiction-line-0"))

    def test_config_cli_default_and_explicit_precedence(self):
        from unittest.mock import patch
        from atlas.cli import main
        from atlas.backends.atlas_sqlite import AtlasSqliteBackend
        from atlas.backends.mrmem import MrMemBackend
        config = Path(self.tmp.name) / "fiction.toml"
        config.write_text('[paths]\ndigest_dir = "fiction-digests"\n', encoding="utf-8")
        self.assertIsNone(AtlasSqliteBackend(self.data).digests())
        self.assertIsNone(MrMemBackend().digests())
        self.assertNotIn("digest", AtlasSqliteBackend(self.data).line({"id": "fiction-garden"}))
        with patch("atlas.server.serve") as serve:
            main(["serve", "--data-dir", str(self.data), "--config", str(config)])
            self.assertEqual(serve.call_args.kwargs["digest_dir"], str(self.root))
            main(["serve", "--data-dir", str(self.data), "--config", str(config), "--digest-dir", "fiction-override"])
            self.assertEqual(serve.call_args.kwargs["digest_dir"], "fiction-override")

    def test_http_api_is_pointer_only_and_drawer_remains_lazy(self):
        import http.client
        import threading
        from urllib.parse import urlencode
        from atlas.server import create_server
        before = {p: p.read_bytes() for p in Path(self.tmp.name).rglob("*") if p.is_file()}
        with create_server(self.data, port=0, digest_dir=self.root) as server:
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                def get(route, **params):
                    client = http.client.HTTPConnection('127.0.0.1', server.server_port)
                    try:
                        client.request('GET', '/api/' + route + '?' + urlencode(params))
                        response = client.getresponse()
                        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                        return response.status, json.loads(response.read())
                    finally:
                        client.close()
                for route, identifier in [('line','fiction-line-0'),('line','fiction-line-1'),('line','fiction-garden'),('entity','fiction-garden')]:
                    status, payload = get(route, id=identifier)
                    self.assertEqual(status, 200)
                    self.assertEqual(len(payload['digest']['sentences']), 4)
                    self.assertFalse({'before','after','context'} & set(payload['digest']))
                    self.assertNotIn('虚构记录：', json.dumps(payload['digest'], ensure_ascii=False))
                self.assertEqual(len(get('home')[1]['home_views']), 6)
                self.assertEqual(get('evidence',kind='digest_entity',id='fiction-garden',doc_id='fiction-doc-0',quote='先在小花圃试种')[0],200)
                self.assertEqual(get('evidence',kind='digest_line',id='fiction-line-0',doc_id='fiction-doc-0',quote='未授权引文')[0],404)
            finally:
                server.shutdown()
                worker.join()
        self.assertEqual(before, {p: p.read_bytes() for p in Path(self.tmp.name).rglob("*") if p.is_file()})

    def test_entity_wrong_type_duplicate_output_and_missing_merge(self):
        inp = json.loads((self.root / 'C_entity1/input.json').read_text(encoding='utf-8'))
        write(self.root, 'C_entity1/input.json', dict(inp, type='concept'))
        self.assertIsNone(self.source().for_entity('fiction-garden'))
        write(self.root, 'C_entity1/input.json', inp)
        write(self.root, 'C_entity2/input.json', inp)
        write(self.root, 'C_entity2.json', self.output)
        self.assertIsNone(self.source().for_entity('fiction-garden'))
        (self.root / 'C_entity2.json').unlink()
        (self.root / 'A_merged.json').unlink()
        self.assertIsNone(self.source().for_line('fiction-line-0'))
        self.assertIsNotNone(self.source().for_entity('fiction-garden'))

    def test_sensitive_document_and_stale_source_block_digests(self):
        import sqlite3
        with closing(sqlite3.connect(self.data / 'corpus.sqlite')) as db, db:
            db.execute("UPDATE documents SET meta=? WHERE id=?", (json.dumps({'sensitive':True}), 'fiction-doc-0'))
        self.assertEqual(self.source().home_views(), [])
        self.assertTrue(self.source(True).home_views())
        with closing(sqlite3.connect(self.data / 'corpus.sqlite')) as db, db:
            db.execute("UPDATE documents SET text=? WHERE id=?", ('虚构已改写的文本', 'fiction-doc-0'))
        self.assertEqual(self.source(True).home_views(), [])

    def test_correction_journal_takes_precedence_without_writing_graph(self):
        prop = ReadModel(self.data).snapshot()['propositions'][0]
        inp = {'name':'花圃的试种与扩种','type':'topic','statements':[{'ref':prop['prop_id']}]}
        write(self.root, 'C_entity1/input.json', inp)
        # This digest has a dated sentence outside the proposition input, which is dropped.
        self.assertIsNotNone(self.source().for_entity('fiction-garden'))
        for verdict in ('wrong','amend'):
            write(self.data, 'corrections.jsonl', dict(correction_id='fiction-correction',prop_id=prop['prop_id'],verdict=verdict,note='虚构更正',observed_at='2025-04-01'))
            self.assertIsNone(self.source().for_entity('fiction-garden'))

    def test_empty_graph_and_whitespace_quotes(self):
        from atlas.graph.store import GraphStore
        empty = Path(self.tmp.name) / 'fiction-empty'
        GraphStore(empty).close()
        self.assertEqual(DigestSource(self.root, ReadModel(empty)).home_views(), [])
        self.output['sentences'][0]['evidence'] = [{'doc_id':'fiction-doc-0','quote':'先在 小花圃试种'}]
        write(self.root, 'B_line1.json', self.output)
        source = self.source()
        self.assertEqual(source.for_line('fiction-line-0')['validation']['valid'], 4)
        self.assertEqual(source.evidence(dict(kind='digest_line',id='fiction-line-0',doc_id='fiction-doc-0',quote='先在 小花圃试种'))['quote'], '先在小花圃试种')


if __name__ == "__main__":
    unittest.main()
