import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.queue import Queue
from atlas.tasks.validate import check_schema, schema_for, validate_output


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.upsert([Document("fiction-1", "synthetic", "2024-01-01", "A fictional garden.")])
        self.queue = Queue(self.root, self.store)
        self.identifier = self.queue.make()[0]
        self.good = {"entities": [{"tmp_id": "e1", "type": "place", "name": "Fictional garden",
                    "aliases": [], "evidence": [{"doc_id": "fiction-1", "span": [2, 18],
                    "quote_hash": hashlib.sha256(b"fictional garden").hexdigest()[:12]}]}],
                    "relations": [], "statements": []}
        self.output = self.root / "fixture.json"

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def submit(self, value, **kwargs):
        self.output.write_text(json.dumps(value), encoding="utf-8")
        return self.queue.submit(self.identifier, self.output, **kwargs)

    def test_good_bad_and_revalidation(self):
        self.assertEqual(self.submit(self.good)["state"], "accepted")
        self.assertEqual(self.queue.validate(self.identifier)["state"], "accepted")
        self.good["entities"][0]["evidence"][0]["quote_hash"] = "abcdefabcdef"
        result = self.submit(self.good)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("quote_hash", result["errors"][0])
        self.assertTrue(list(self.queue.locate(self.identifier)[1].glob("attempts/*/output.json")))

    def test_dedup_and_changed_input(self):
        self.assertEqual(self.queue.make(), [self.identifier])
        self.assertEqual(len(self.queue.list()), 1)
        self.store.upsert([Document("fiction-1", "synthetic", "2024-01-01", "Changed")])
        with self.assertRaises(ValueError):
            self.queue.make()
        self.assertEqual(self.submit(self.good)["state"], "rejected")

    def test_claim_owner_reap(self):
        self.queue.claim(self.identifier, "worker", 1)
        with self.assertRaises(ValueError):
            self.queue.claim(self.identifier, "other")
        with self.assertRaises(ValueError):
            self.submit(self.good, owner="other")
        self.assertEqual(self.queue.reap(float("inf")), [self.identifier])
        self.queue.claim(self.identifier, "worker")
        self.assertEqual(self.submit(self.good, owner="worker")["state"], "accepted")

    def test_schema_rejections(self):
        for field, value in [("type", "invalid"), ("aliases", "bad"), ("extra", True)]:
            with self.subTest(field=field):
                output = json.loads(json.dumps(self.good))
                output["entities"][0][field] = value
                self.assertEqual(self.submit(output)["state"], "rejected")
        self.assertTrue(check_schema(True, {"type": "integer"}))
        self.assertTrue(check_schema(float("nan"), {"type": "number"}))

    def test_span_and_document_scope(self):
        for field, value in [("span", [-1, 18]), ("span", [2, 200]), ("span", [2, 2]),
                             ("span", [True, 18]), ("doc_id", "not-in-task")]:
            with self.subTest(value=value):
                output = json.loads(json.dumps(self.good))
                output["entities"][0]["evidence"][0][field] = value
                self.assertEqual(self.submit(output)["state"], "rejected")

    def test_invalid_json_and_traversal(self):
        self.output.write_text("{invalid", encoding="utf-8")
        self.assertEqual(self.queue.submit(self.identifier, self.output)["state"], "rejected")
        with self.assertRaises(ValueError):
            self.queue.claim("../outside", "worker")

    def test_batches_and_all_schemas(self):
        self.store.upsert(Document(f"synthetic-{i}", "synthetic", "2024-01-01", "Fiction") for i in range(51))
        ids = self.queue.make()
        self.assertEqual(len(ids), 2)
        for identifier in ids:
            path = self.queue.locate(identifier)[1]
            self.assertLessEqual(len(json.loads((path / "input.json").read_text(encoding="utf-8"))["documents"]), 50)
        for kind in ("extract_entities", "resolve_entities", "gen_propositions", "cluster_lens", "verify"):
            for direction in ("input", "output"):
                self.assertEqual(schema_for(kind + "." + direction)["type"], "object")

    def test_tampered_input(self):
        path = self.queue.locate(self.identifier)[1] / "input.json"
        path.write_text('{"documents": []}', encoding="utf-8")
        self.assertEqual(self.submit(self.good)["state"], "rejected")

    def test_statement_constraints_and_unicode(self):
        self.good["statements"] = [{"tmp_id": "s1", "kind": "opinion", "about": ["e1"],
                                   "text": "A measured synthetic opinion", "confidence": 0.5,
                                   "evidence": self.good["entities"][0]["evidence"]}]
        self.assertEqual(self.submit(self.good)["state"], "accepted")
        for field, value in [("text", "Always correct"), ("text", "x" * 121),
                             ("confidence", 1.1), ("about", ["unknown"]), ("tmp_id", "e1")]:
            output = json.loads(json.dumps(self.good))
            output["statements"][0][field] = value
            result = self.submit(output)
            self.assertEqual(result["state"], "accepted")
            self.assertTrue(result["partial"])
            self.assertEqual(result["counts"], {"accepted": 1, "dropped": 1})
        text = "A synthetic tree: \u6a39\U0001f333"
        self.store.upsert([Document("unicode-fiction", "synthetic", "2024-01-01", text)])
        evidence = {"doc_id": "unicode-fiction", "span": [18, 20],
                    "quote_hash": hashlib.sha256(text[18:20].encode("utf-8")).hexdigest()[:12]}
        output = {"entities": [{"tmp_id": "tree", "type": "concept", "name": "Tree", "aliases": [],
                                "evidence": [evidence]}], "relations": [], "statements": []}
        self.assertEqual(validate_output("extract_entities", output,
                         {"documents": [{"id": "unicode-fiction"}]}, self.store), [])
