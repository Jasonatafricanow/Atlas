import copy
import json
import tempfile
import unittest
from pathlib import Path

from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.merge import merge, records
from atlas.tasks.queue import Queue


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        corpus = Path("examples/synthetic_corpus/reading_notes.jsonl")
        self.store.upsert(Document(source="synthetic", **json.loads(line)) for line in corpus.read_text(encoding="utf-8").splitlines() if line)
        self.graph = GraphStore(self.root)
        self.queue = Queue(self.root, self.store)
        self.task = self.queue.make()[0]
        self.output = json.loads(Path("examples/tasks_demo/extract_entities.good.json").read_text(encoding="utf-8"))
        self.output["entities"][0]["aliases"] = ["Synthetic activity"]
        other = copy.deepcopy(self.output["entities"][0])
        other.update(tmp_id="e2", name="Synthetic district", type="place")
        self.output["entities"].append(other)
        self.output["relations"] = [{"src": "e1", "dst": "e2", "type": "observed_in",
                                      "valid_from": "2024-01-01", "evidence": other["evidence"]}]

    def tearDown(self):
        self.graph.close()
        self.store.db.close()
        self.temp.cleanup()

    def accept(self, output=None, task=None):
        path = self.root / "output.json"
        path.write_text(json.dumps(output or self.output), encoding="utf-8")
        self.assertEqual(self.queue.submit(task or self.task, path)["state"], "accepted")

    def test_extraction_idempotent_and_audited(self):
        self.accept()
        self.assertEqual(merge(self.queue, self.graph, self.task)["state"], "merged")
        before = self.graph.stats()
        self.assertEqual((before["nodes"], before["edges"], before["aliases"]), (2, 1, 4))
        self.assertEqual(merge(self.queue, self.graph, self.task)["state"], "noop")
        self.assertEqual(self.graph.stats(), before)
        self.assertEqual(before["propositions"], 0)

    def test_unaccepted_and_changed_output_refused(self):
        with self.assertRaisesRegex(ValueError, "accepted"):
            merge(self.queue, self.graph, self.task)
        self.accept()
        merge(self.queue, self.graph, self.task)
        before = self.graph.stats()
        self.output["entities"][0]["name"] = "Changed synthetic concept"
        self.accept()
        with self.assertRaisesRegex(ValueError, "changed output"):
            merge(self.queue, self.graph, self.task)
        self.assertEqual(before, self.graph.stats())

    def test_failure_rolls_back_all_rows_and_log(self):
        self.output["relations"][0]["valid_to"] = "2023-01-01"
        self.accept()
        merge(self.queue, self.graph, self.task)
        self.assertEqual(self.graph.stats()["edges"], 0)
        self.assertEqual(self.graph.stats()["nodes"], 2)

    def resolution(self, candidates, ops, nodes=None):
        payload = {"candidates": candidates, "nodes": nodes if nodes is not None else [
            {key: n[key] for key in ("node_id", "name", "type")} for n in records(self.graph, "nodes")],
            "documents": [d.to_dict() for d in self.store.all()]}
        task = self.queue.make("resolve_entities", payload)[0]
        self.accept({"ops": ops}, task)
        return task

    def test_resolution_add_merge_noop_and_references(self):
        self.accept()
        mapping = merge(self.queue, self.graph, self.task)["node_ids"]
        candidate = copy.deepcopy(self.output["entities"][0])
        candidate.update(tmp_id="new", name="Synthetic alternate activity")
        task = self.resolution([candidate], [{"op": "ADD", "tmp_id": "new", "reason": "Synthetic candidate"}])
        target = merge(self.queue, self.graph, task)["node_ids"]["new"]
        source = copy.deepcopy(self.output["entities"][0])
        source["node_id"] = mapping["e1"]
        unused = copy.deepcopy(candidate)
        unused["tmp_id"] = "unused"
        task = self.resolution([source, unused], [
            {"op": "MERGE_INTO", "tmp_id": "e1", "node_id": target, "reason": "Same synthetic entity"},
            {"op": "NOOP", "tmp_id": "unused", "reason": "No graph change"}])
        merge(self.queue, self.graph, task)
        self.assertEqual(self.graph.get("nodes", mapping["e1"])["superseded_by"], target)
        self.assertEqual(records(self.graph, "edges")[0]["src"], target)
        self.assertFalse(any(a["node_id"] == mapping["e1"] for a in records(self.graph, "aliases")))
        before = self.graph.stats()
        merge(self.queue, self.graph, task)
        self.assertEqual(before, self.graph.stats())

    def test_resolution_missing_live_target_rolls_back(self):
        candidate = self.output["entities"][0]
        task = self.resolution([candidate], [{"op": "MERGE_INTO", "tmp_id": "e1",
            "node_id": "missing", "reason": "Synthetic stale snapshot"}],
            [{"node_id": "missing", "type": "concept", "name": "Synthetic missing node"}])
        with self.assertRaisesRegex(ValueError, "target"):
            merge(self.queue, self.graph, task)
        self.assertEqual(self.graph.stats()["nodes"], 0)
        self.assertEqual(self.graph.stats()["ops_log"], 0)

    def test_resolution_operations_and_evidence_validation(self):
        candidate = self.output["entities"][0]
        payload = {"candidates": [candidate], "nodes": [], "documents": [d.to_dict() for d in self.store.all()]}
        task = self.queue.make("resolve_entities", payload)[0]
        for ops in ([], [{"op": "MERGE_INTO", "tmp_id": "e1", "reason": "Missing target"}],
                    [{"op": "ADD", "tmp_id": "e1", "reason": "Duplicate"}] * 2):
            path = self.root / "invalid.json"
            path.write_text(json.dumps({"ops": ops}), encoding="utf-8")
            self.assertEqual(self.queue.submit(task, path)["state"], "rejected")
        self.accept({"ops": [{"op": "ADD", "tmp_id": "e1", "reason": "Synthetic"}]}, task)
        doc = next(d for d in self.store.all() if d.id == candidate["evidence"][0]["doc_id"])
        doc.text = "Changed synthetic source"
        self.store.upsert([doc])
        with self.assertRaises(ValueError):
            merge(self.queue, self.graph, task)
        self.assertEqual(self.graph.stats()["nodes"], 0)

    def test_explicit_contradiction_preserves_history(self):
        self.accept()
        merge(self.queue, self.graph, self.task)
        old = records(self.graph, "edges")[0]
        self.store.upsert([Document("synthetic-revision", "synthetic", "2025-01-01", "Synthetic revision marker.")])
        task = self.queue.make()[0]
        self.output["relations"][0].update(supersedes=old["edge_id"], valid_from="2025-01-01")
        self.accept(task=task)
        merge(self.queue, self.graph, task)
        historical = self.graph.get("edges", old["edge_id"])
        self.assertEqual(historical["status"], "superseded")
        self.assertEqual(historical["valid_to"], "2025-01-01")
        self.assertEqual(historical["evidence"], old["evidence"])
        self.assertEqual(self.graph.get("edges", historical["superseded_by"])["status"], "confirmed")
        before = self.graph.stats()
        merge(self.queue, self.graph, task)
        self.assertEqual(before, self.graph.stats())

    def test_unmarked_relations_coexist_and_sensitive_is_inherited(self):
        doc = next(iter(self.store.all()))
        doc.meta["sensitive"] = True
        self.store.upsert([doc])
        # Use a fresh queue task snapshot after changing metadata.
        doc.id = "synthetic-sensitive-revision"
        self.store.upsert([doc])
        self.task = self.queue.make()[0]
        relation = copy.deepcopy(self.output["relations"][0])
        relation["valid_from"] = "2025-01-01"
        self.output["relations"].append(relation)
        self.accept()
        merge(self.queue, self.graph, self.task)
        self.assertTrue(all(n["sensitive"] for n in records(self.graph, "nodes")))
        edges = records(self.graph, "edges")
        self.assertEqual(len(edges), 2)
        self.assertTrue(all(e["status"] == "confirmed" and e["sensitive"] for e in edges))

