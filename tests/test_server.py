import contextlib
import hashlib
import http.client
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from atlas.cli import main
from atlas.graph.store import GraphStore
from atlas.server import create_server
from atlas.web_data import ReadModel, connect
from examples.tasks_demo.seed_ui_v2 import seed


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        seed(self.root)
        self.server = create_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method="GET", headers=None):
        with contextlib.closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port)) as client:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def api(self, path):
        status, headers, body = self.request("/api/" + path)
        self.assertEqual(status, 200, body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        return json.loads(body)

    def test_lines_merge_exact_topics_and_preserve_fields(self):
        data = self.api("lines")
        self.assertEqual(len(data["lines"]), 1)
        line = data["lines"][0]
        self.assertEqual(len(line["lines"]), 2)
        self.assertEqual([p["statement_id"] for p in line["timeline"]], ["fiction-s0", "fiction-s1", "fiction-s2"])
        self.assertEqual(line["timeline"][2]["annotations"][0]["shift"], "reverse")
        self.assertNotIn("summary", line)
        self.assertNotIn("current_stance", line)
        self.assertNotIn('"quote":', json.dumps(data))

    def test_home_search_entity_and_sensitive_filter(self):
        self.assertEqual(len(self.api("home")["propositions"]), 1)
        self.assertTrue(self.api("search?" + urlencode({"q": "虚构试种"}))["results"])
        self.assertEqual(self.api("search?q=absent")["results"], [])
        entity = self.api("entity?id=fiction-garden")
        self.assertEqual(len(entity["statements"]), 3)
        self.assertEqual(len(entity["edges"]), 1)
        self.assertEqual(len(entity["aliases"]), 1)
        self.assertEqual(self.request("/api/entity?id=fiction-hidden")[0], 404)
        self.assertEqual(self.api("entity?id=fiction-hidden&sensitive=1")["node"]["node_id"], "fiction-hidden")
        self.assertNotIn("fiction-hidden", json.dumps(self.api("toc")))

    def test_evidence_only_resolves_registered_pointer_and_checks_hash(self):
        evidence = self.api("evidence?kind=statements&id=fiction-s0&index=0")
        self.assertIn("先在小花圃", evidence["quote"])
        self.assertEqual(hashlib.sha256(evidence["quote"].encode()).hexdigest()[:12], evidence["pointer"]["quote_hash"])
        for path in ("evidence?kind=documents&id=fiction-doc-0", "evidence?kind=statements&id=fiction-s0&index=-1", "evidence?kind=statements&id=fiction-s0&index=99"):
            self.assertEqual(self.request("/api/" + path)[0], 404)
        graph = GraphStore(self.root)
        row = graph.get("statements", "fiction-s0")
        row["evidence"][0]["quote_hash"] = "bad-hash"
        graph.put("statements", row)
        graph.close()
        status, _, body = self.request("/api/evidence?kind=statements&id=fiction-s0")
        self.assertEqual(status, 409)
        self.assertNotIn("虚构", body.decode())

    def test_readonly_no_files_changed_and_requests_not_logged(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with contextlib.redirect_stderr(io.StringIO()) as log:
            for path in ("home", "lines", "toc", "entities", "search?q=private-search", "line?id=fiction-garden", "entity?id=fiction-garden", "evidence?kind=statements&id=fiction-s0"):
                self.api(path)
        self.assertEqual(log.getvalue(), "")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        with contextlib.closing(connect(self.root / "graph.sqlite")) as db:
            with self.assertRaises(Exception):
                db.execute("DELETE FROM nodes")

    def test_corrections_project_without_mutating_database(self):
        row = dict(correction_id="fiction-correction", prop_id="fiction-prop", verdict="wrong", note="虚构纠正", observed_at="2025-04-01")
        (self.root / "corrections.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        data = self.api("home")
        self.assertEqual(data["propositions"][0]["status"], "rejected")
        with contextlib.closing(connect(self.root / "graph.sqlite")) as db:
            self.assertEqual(json.loads(db.execute("SELECT data FROM propositions").fetchone()[0])["status"], "proposed")

    def test_private_support_and_document_sensitivity_do_not_leak(self):
        graph = GraphStore(self.root)
        source = graph.get("statements", "fiction-s1")
        source["sensitive"] = True
        graph.put("statements", source)
        graph.close()
        line = self.api("lines")["lines"][0]
        self.assertNotIn("fiction-s1", json.dumps(line))
        self.assertEqual(line["timeline"][0]["annotations"][0]["outcome"], "unknown")

    def test_404s_methods_origin_and_default_binding(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path in ("/api/absent", "/api/line?id=missing", "/graph.sqlite", "/corpus.sqlite", "/../AGENTS.md", "/%2e%2e/AGENTS.md", "/data.js"):
            status, _, body = self.request(path)
            self.assertEqual(status, 404)
            self.assertEqual(json.loads(body), {"error": 404})
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(self.request("/api/home", method)[0], 405)
        self.assertEqual(self.request("/api/home", headers={"Host": "attacker.invalid"})[0], 403)
        self.assertEqual(self.request("/api/home", headers={"Origin": "https://attacker.invalid"})[0], 403)
        with self.assertRaises(ValueError):
            create_server(self.root, host="0.0.0.0")
        with patch("atlas.server.serve") as serve:
            self.assertEqual(main(["serve", "--data-dir", str(self.root)]), 0)
            serve.assert_called_once_with(str(self.root), "127.0.0.1", 8765)

    def test_missing_and_empty_stores(self):
        with self.assertRaises(ValueError):
            create_server(self.root / "absent")
        empty = self.root / "empty"
        GraphStore(empty).close()
        data = ReadModel(empty).get("home", {})
        self.assertEqual(data, {"lines": [], "nodes": [], "propositions": []})

    def test_private_document_text_and_extra_metadata_never_enter_list_api(self):
        with contextlib.closing(sqlite3.connect(self.root / "corpus.sqlite")) as db:
            db.execute("UPDATE documents SET text=?", ("FICTIONAL_CORPUS_ONLY_MARKER",))
            db.commit()
        graph = GraphStore(self.root)
        row = graph.get("nodes", "fiction-garden")
        row["private_extra"] = "FICTIONAL_EXTRA_MARKER"
        row["evidence"][0]["quote"] = "FICTIONAL_INLINE_MARKER"
        graph.put("nodes", row)
        graph.close()
        for route in ("home", "toc", "lines", "entities", "entity?id=fiction-garden", "search?q=fiction"):
            body = json.dumps(self.api(route))
            for marker in ("FICTIONAL_CORPUS_ONLY_MARKER", "FICTIONAL_EXTRA_MARKER", "FICTIONAL_INLINE_MARKER"):
                self.assertNotIn(marker, body)

    def test_document_sensitivity_filters_dependent_records_and_evidence(self):
        with contextlib.closing(sqlite3.connect(self.root / "corpus.sqlite")) as db:
            db.execute("UPDATE documents SET meta=? WHERE id=?", (json.dumps({"sensitive": True}), "fiction-doc-0"))
            db.commit()
        self.assertNotIn("fiction-garden", json.dumps(self.api("home")))
        self.assertEqual(self.request("/api/evidence?kind=statements&id=fiction-s0")[0], 404)
        self.assertIn("quote", self.api("evidence?kind=statements&id=fiction-s0&sensitive=1"))

    def test_static_assets_and_errors_have_no_store_and_security_headers(self):
        for path in ("/", "/theme.css", "/js/app.js", "/js/vendor/cytoscape.js"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
            self.assertTrue(body)
