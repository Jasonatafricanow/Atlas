import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from atlas.graph.models import Node
from atlas.graph.store import GraphStore
from atlas.profile import correct, snapshot, sync_corrections
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.merge import merge
from atlas.tasks.queue import Queue


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.graph = GraphStore(self.root)
        self.queue = Queue(self.root, self.store)
        docs = [Document(source="synthetic", **json.loads(line)) for line in
                Path("examples/synthetic_corpus/reading_notes.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.store.upsert(docs)
        self.graph.put("nodes", Node("demo-topic", "topic", "Synthetic reading"))
        self.evidence = [dict(doc_id=d.id, span=[0, len(d.text)],
                              quote_hash=hashlib.sha256(d.text.encode()).hexdigest()[:12]) for d in docs]
        self.prop = dict(prop_id="demo-prop", text="Synthetic reading preference", kind="preference",
                         subject_node_ids=["demo-topic"], evidence=self.evidence[:2], counter_evidence=[],
                         confidence=0.6, valid_from="2024-01-01", valid_to=None, status="proposed")

    def tearDown(self):
        self.graph.close()
        self.store.db.close()
        self.temp.cleanup()

    def task(self):
        return self.queue.make("gen_propositions", snapshot(self.graph, self.store, self.root, "demo-topic"))[0]

    def submit(self, task, ops):
        path = self.root / "output.json"
        path.write_text(json.dumps(dict(ops=ops)), encoding="utf-8")
        return self.queue.submit(task, path)

    def apply(self, op="ADD", prop=None, **extra):
        task = self.task()
        result = self.submit(task, [dict(op=op, prop=prop or self.prop, **extra)])
        self.assertEqual(result["state"], "accepted", result)
        merge(self.queue, self.graph, task)
        return task

    def test_confidence_update_and_idempotency(self):
        task = self.apply()
        before = self.graph.stats()
        self.assertEqual(merge(self.queue, self.graph, task)["state"], "noop")
        self.assertEqual(before, self.graph.stats())
        prop = dict(self.prop, confidence=0.8)
        self.apply("UPDATE", prop)
        self.assertEqual(self.graph.get("propositions", "demo-prop")["confidence"], 0.7)

    def test_wrong_stale_merge_and_new_identity(self):
        task = self.apply()
        stale = self.task()
        self.assertEqual(self.submit(stale, [dict(op="UPDATE", prop=dict(self.prop, confidence=0.9))])["state"], "accepted")
        correct(self.graph, self.root, "demo-prop", "wrong", "Synthetic correction")
        merge(self.queue, self.graph, task)
        merge(self.queue, self.graph, stale)
        self.apply("ADD", dict(self.prop, prop_id="new-id", text="  SYNTHETIC reading preference  "))
        prop = self.graph.get("propositions", "demo-prop")
        self.assertEqual(prop["status"], "rejected")
        self.assertTrue(prop["suppressed_by"])
        self.assertIsNone(self.graph.get("propositions", "new-id"))

    def test_journal_priority_replay_and_user_right(self):
        task = self.apply()
        row = dict(correction_id="demo-correction", prop_id="demo-prop", verdict="wrong",
                   note="Synthetic external correction", observed_at="2025-01-01")
        (self.root / "corrections.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        merge(self.queue, self.graph, task)
        self.assertEqual(self.graph.get("propositions", "demo-prop")["status"], "rejected")
        correct(self.graph, self.root, "demo-prop", "right")
        correct(self.graph, self.root, "demo-prop", "amend", "Synthetic qualification")
        before = self.graph.stats()
        sync_corrections(self.graph, self.root)
        self.assertEqual(before, self.graph.stats())
        self.apply("UPDATE", dict(self.prop, text="Agent replacement", confidence=0.7))
        prop = self.graph.get("propositions", "demo-prop")
        self.assertEqual(prop["status"], "confirmed")
        self.assertEqual(prop["text"], self.prop["text"])
        self.assertEqual(prop["user_note"], "Synthetic qualification")
        self.assertIsNone(prop["suppressed_by"])

    def test_validation_support_hash_counter_and_subject(self):
        task = self.task()
        for changes in (dict(evidence=self.evidence[:1]), dict(evidence=self.evidence[:1] * 2),
                        dict(confidence=1.1),
                        dict(counter_evidence=self.evidence[:1])):
            with self.subTest(changes=changes):
                result = self.submit(task, [dict(op="ADD", prop=dict(self.prop, **changes))])
                self.assertEqual(result["state"], "rejected")
        # Out-of-subgraph subjects are repaired (dropped; task node kept), not rejected.
        repaired = self.submit(task, [dict(op="ADD", prop=dict(self.prop, prop_id="demo-prop-2", subject_node_ids=["missing"]))])
        self.assertEqual(repaired["state"], "accepted")
        bad = copy.deepcopy(self.prop)
        bad["evidence"][0]["quote_hash"] = "000000000000"
        self.assertEqual(self.submit(task, [dict(op="ADD", prop=bad)])["state"], "rejected")

    def test_counter_retained_and_sensitive_inherited(self):
        doc = next(iter(self.store.all()))
        doc.meta["sensitive"] = True
        self.store.upsert([doc])
        # A separate non-overlapping source span provides synthetic counter evidence.
        counter = dict(doc_id=doc.id, span=[0, 1], quote_hash=hashlib.sha256(doc.text[:1].encode()).hexdigest()[:12])
        self.prop["counter_evidence"] = [counter]
        self.apply()
        self.assertTrue(self.graph.get("propositions", "demo-prop")["sensitive"])
        task = self.task()
        self.assertEqual(self.submit(task, [dict(op="UPDATE", prop=dict(self.prop, counter_evidence=[]))])["state"], "rejected")

    def test_supersede_and_atomic_rollback(self):
        self.apply()
        new = dict(self.prop, prop_id="replacement", valid_from="2025-01-01")
        self.apply("SUPERSEDE", new, supersedes="demo-prop")
        old = self.graph.get("propositions", "demo-prop")
        self.assertEqual((old["status"], old["valid_to"], old["superseded_by"]),
                         ("superseded", "2025-01-01", "replacement"))
        task = self.task()
        self.assertEqual(self.submit(task, [dict(op="ADD", prop=dict(new, prop_id="temporary")),
                         dict(op="UPDATE", prop=dict(new, prop_id="missing"))])["state"], "accepted")
        result = merge(self.queue, self.graph, task)
        self.assertEqual(result["deduplicated"], 1)
        self.assertIsNone(self.graph.get("propositions", "missing"))

    def test_invalid_correction_does_not_append(self):
        self.apply()
        for prop_id, verdict, note in (("missing", "wrong", ""), ("demo-prop", "amend", "")):
            with self.assertRaises(ValueError):
                correct(self.graph, self.root, prop_id, verdict, note)
        self.assertFalse((self.root / "corrections.jsonl").exists())
