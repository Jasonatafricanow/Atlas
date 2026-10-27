"""M6 acceptance uses only fictional documents in disposable directories."""
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from atlas.chat import attribution
from atlas.cli import main, build
from atlas.graph.confidence import calibrate
from atlas.graph.models import Node
from atlas.graph.store import GraphStore
from atlas.lenses.judgment_lines import grouped_lines
from atlas.profile import snapshot, correct
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.lines import make_lines
from atlas.tasks.merge import merge, records
from atlas.tasks.propositions import same_claim
from atlas.tasks.queue import Queue, read_json


def pointer(doc, start=0, end=None):
    end = len(doc.text) if end is None else end
    return dict(doc_id=doc.id, span=[start, end], quote_hash=hashlib.sha256(doc.text[start:end].encode()).hexdigest()[:12])


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.graph = GraphStore(self.root)
        self.queue = Queue(self.root, self.store)
        self.docs = [Document(f"fiction-{i}", "synthetic", ts, text, author="虚构花园", meta={"sensitive": i == 1})
                     for i, (ts, text) in enumerate([
                         ("2024-01-01", "[01-01 09:00] 我: 我计划建设虚构花园。"),
                         ("2024-01-09", "[01-09 10:00] 虚构甲: 虚构花园已建成。"),
                         ("2024-01-10", "[01-10 11:00] 我: 我喜欢这座虚构花园。")])]
        self.store.upsert(self.docs)

    def tearDown(self):
        self.graph.close()
        self.store.db.close()
        self.temp.cleanup()

    def submit(self, task, output):
        path = self.root / "response.json"
        path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
        return self.queue.submit(task, path)

    def extraction(self):
        evidence = [pointer(self.docs[0])]
        return dict(entities=[dict(tmp_id="garden", type="topic", name="虚构花园", aliases=[], evidence=evidence),
                              dict(tmp_id="owner", type="person", name="我", aliases=[], evidence=evidence)],
                    relations=[dict(src="owner", dst="garden", type="虚构花园", evidence=evidence, confidence=0.95)],
                    statements=[dict(tmp_id=f"s{i}", kind="plan" if i == 0 else "fact", text=doc.text.split(": ")[1],
                                     about=["garden"], stance="支持", confidence=0.95, evidence=[pointer(doc)])
                                for i, doc in enumerate(self.docs)])

    def extract(self):
        task = self.queue.make()[0]
        self.assertEqual(self.submit(task, self.extraction())["state"], "accepted")
        return task, merge(self.queue, self.graph, task)

    def test_statements_attribution_calibration_idempotency(self):
        task, result = self.extract()
        statements = sorted(records(self.graph, "statements"), key=lambda s: s["ts"])
        self.assertEqual(len(statements), 3)
        self.assertEqual(statements[0]["speaker"], "我")
        self.assertEqual(statements[0]["ts"], "2024-01-01T09:00:00")
        self.assertEqual(statements[0]["about"], [result["node_ids"]["garden"]])
        self.assertTrue(statements[1]["sensitive"])
        self.assertEqual(statements[0]["raw_confidence"], 0.95)
        self.assertEqual(statements[0]["confidence"], 0.55)
        self.assertEqual(records(self.graph, "edges")[0]["confidence"], 0.55)
        before = self.graph.stats()
        self.assertEqual(merge(self.queue, self.graph, task)["state"], "noop")
        self.assertEqual(before, self.graph.stats())

    def test_attribution_fallback_and_ambiguous_multiline(self):
        doc = Document("fiction-fallback", "synthetic", "", "Plain fictional note", author="虚构甲")
        self.assertEqual(attribution(doc.to_dict(), pointer(doc)), {"speaker": "虚构甲", "ts": None})
        doc.text = "[02-30 12:00] 虚构甲: 不可能日期"
        self.assertEqual(attribution(doc.to_dict(), pointer(doc)), {"speaker": "虚构甲", "ts": None})
        doc.text = "[01-01 12:00] 虚构甲: 第一行\n[01-01 13:00] 虚构乙: 第二行"
        self.assertIsNone(attribution(doc.to_dict(), pointer(doc))["speaker"])
        doc.ts = "2023-12-31"
        doc.meta = {"ts_end": "2024-01-01"}
        start = doc.text.index("[01-01 13")
        self.assertEqual(attribution(doc.to_dict(), pointer(doc, start))["ts"], "2024-01-01T13:00:00")

    def test_partial_acceptance_drops_dependencies_and_preserves_raw(self):
        task = self.queue.make()[0]
        output = self.extraction()
        output["entities"][0]["type"] = "invalid"
        result = self.submit(task, output)
        self.assertEqual(result["state"], "accepted")
        self.assertTrue(result["partial"])
        self.assertEqual(result["counts"], {"accepted": 1, "dropped": 5})
        path = self.queue.locate(task)[1]
        self.assertEqual(read_json(path / "output.json"), output)
        self.assertTrue(any("relations[0]" in e for e in read_json(path / "errors.json")))
        merge(self.queue, self.graph, task)
        self.assertEqual(self.graph.stats()["nodes"], 1)
        self.assertEqual(self.graph.stats()["statements"], 0)
        self.assertTrue(self.queue.validate(task)["partial"])
        output["entities"][1]["evidence"][0]["quote_hash"] = "0" * 12
        self.assertEqual(self.submit(task, output)["state"], "rejected")

    def test_confidence_breadth_time_counter(self):
        docs = {d.id: d.to_dict() for d in self.docs}
        for count, cap in [(1, 0.55), (2, 0.7), (3, 0.9)]:
            record = dict(confidence=0.99, evidence=[pointer(d) for d in self.docs[:count]])
            self.assertEqual(calibrate(record, docs)["confidence"], cap)
            self.assertEqual(record["raw_confidence"], 0.99)
        docs[self.docs[0].id]["ts"] = "2024-01-09"
        record = dict(confidence=0.99, evidence=[pointer(d) for d in self.docs])
        self.assertEqual(calibrate(record, docs)["confidence"], 0.8)
        record["counter_evidence"] = [pointer(self.docs[0], 1, 3)]
        self.assertEqual(calibrate(record, docs)["confidence"], 0.4)

    def test_cross_node_dedup_and_correction_precedence(self):
        for node in ("a", "b"):
            self.graph.put("nodes", Node(node, "topic", "虚构花园"))
        base = dict(prop_id="p1", kind="preference", text="喜欢阅读虚构花园故事", subject_node_ids=["a"],
                    evidence=[pointer(d) for d in self.docs[:2]], counter_evidence=[], confidence=0.95,
                    status="proposed", valid_from=None, valid_to=None)
        for prop, node, expected in [(base, "a", 0), (dict(base, prop_id="p2", subject_node_ids=["b"], text="喜欢阅读虚构花园故事。"), "b", 1)]:
            task = self.queue.make("gen_propositions", snapshot(self.graph, self.store, self.root, node))[0]
            self.assertEqual(self.submit(task, {"ops": [{"op": "ADD", "prop": prop}]})["state"], "accepted")
            self.assertEqual(merge(self.queue, self.graph, task)["deduplicated"], expected)
        self.assertEqual(self.graph.stats()["propositions"], 1)
        self.assertEqual(set(self.graph.get("propositions", "p1")["subject_node_ids"]), {"a", "b"})
        self.assertFalse(same_claim(base, dict(base, kind="plan")))
        self.assertFalse(same_claim(base, dict(base, text="完全无关的航海计划", subject_node_ids=["b"])))
        correct(self.graph, self.root, "p1", "wrong", "虚构花园")
        task = self.queue.make("gen_propositions", snapshot(self.graph, self.store, self.root, "b"))[0]
        prop = dict(base, prop_id="p3", subject_node_ids=["b"])
        self.submit(task, {"ops": [{"op": "ADD", "prop": prop}]})
        merge(self.queue, self.graph, task)
        self.assertIsNone(self.graph.get("propositions", "p3"))

    def cluster_output(self):
        statements = sorted(records(self.graph, "statements"), key=lambda s: s["ts"])
        points = [dict(statement_id=s["statement_id"], shift="first" if i == 0 else "new_angle", reason="虚构来源说明",
                       outcome="unknown", outcome_statement_ids=[], outcome_reason="") for i, s in enumerate(statements)]
        points[0].update(outcome="confirmed", outcome_statement_ids=[statements[1]["statement_id"]], outcome_reason="喜欢阅读虚构花园故事。")
        return {"lines": [dict(line_id="garden-line", title="虚构花园", topic=statements[0]["about"][0], timeline=points)]}

    def test_cluster_pack_validate_merge_and_projection(self):
        self.extract()
        task = make_lines(self.queue, self.graph)[0]
        payload = read_json(self.queue.locate(task)[1] / "input.json")
        self.assertEqual(len(payload["statements"]), 3)
        good = self.cluster_output()
        for change in ("missing", "early", "order", "unsupported"):
            bad = copy.deepcopy(good)
            points = bad["lines"][0]["timeline"]
            if change == "missing": points[0]["statement_id"] = "missing"
            if change == "early": points[1].update(outcome="refuted", outcome_statement_ids=[points[0]["statement_id"]], outcome_reason="虚构花园")
            if change == "order": points.reverse()
            if change == "unsupported": points[0]["outcome_statement_ids"] = []
            self.assertEqual(self.submit(task, bad)["state"], "accepted", change)
        self.assertEqual(self.submit(task, good)["state"], "accepted")
        merge(self.queue, self.graph, task)
        before = self.graph.stats()
        self.assertEqual(before["avg_points_per_line"], 3)
        merge(self.queue, self.graph, task)
        self.assertEqual(before, self.graph.stats())
        graph = {t: records(self.graph, t) for t in ("nodes", "propositions", "statements", "lines")}
        lines = grouped_lines(graph)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["timeline"][0]["speaker"], "我")
        self.assertEqual(lines[0]["timeline"][0]["outcome"], "confirmed")
        self.assertTrue(lines[0]["timeline"][0]["sensitive"])
        graph["lines"] = []
        fallback = grouped_lines(graph)
        self.assertEqual(len(fallback), 1)
        self.assertEqual(len(fallback[0]["timeline"]), 3)
        self.assertTrue(all(p["outcome"] == "unknown" for p in fallback[0]["timeline"]))

    def test_batch_limits_instructions_stats_and_cli(self):
        queue = Queue(self.root, self.store, batch_docs=2, batch_chars=40)
        tasks = queue.make()
        self.assertEqual(len(tasks), 3)
        for task in tasks:
            text = (queue.locate(task)[1] / "INSTRUCTIONS.md").read_text(encoding="utf-8")
            for fragment in ("source language", "1.5", "speaker", "stance", "named exactly as shown"):
                self.assertIn(fragment, text)
        with patch.dict("os.environ", {"ATLAS_DATA_DIR": str(self.root), "ATLAS_OUT_DIR": str(self.root / "site")}):
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["tasks", "merge", "--all"]), 0)
                self.assertEqual(main(["tasks", "make", "--kind", "cluster_lens"]), 0)
        self.assertEqual(self.graph.stats()["active_nodes"], 0)
        self.assertEqual(self.graph.stats()["edges_per_node"], 0)
        self.assertEqual(sum(self.graph.stats()["proposition_confidence_histogram"].values()), 0)
        self.assertEqual(make_lines(queue, self.graph), [])

    def test_export_and_chinese_timeline_ui(self):
        self.extract()
        build(dict(data_dir=str(self.root), out_dir=str(self.root / "site"), config_dir=".", lenses=[dict(lens="judgment_lines")]), self.store)
        data = read_json(self.root / "site" / "atlas.json")
        self.assertEqual(len(data["statements"]), 3)
        self.assertEqual(len(data["lenses"][0]["view"]["lines"]), 1)
        html = (self.root / "site" / "index.html").read_text(encoding="utf-8")
        for label in ("如何阅读", "如何纠正", "发言者", "后续结果"):
            self.assertIn(label, html)
        self.assertNotIn('id="sensitive" type="checkbox" checked', html)
        self.assertNotIn("<table", html)


    def test_partial_bad_operation_and_relation_supersession(self):
        task = self.queue.make()[0]
        output = self.extraction()
        output["relations"][0].update(supersedes="missing-edge", valid_from="2024-02-01")
        result = self.submit(task, output)
        self.assertTrue(result["partial"])
        self.assertEqual(result["counts"], {"accepted": 5, "dropped": 1})
        mapping = merge(self.queue, self.graph, task)["node_ids"]
        node = mapping["garden"]
        prop = dict(prop_id="fiction-prop", text="虚构花园计划", kind="plan", subject_node_ids=[node],
                    evidence=[pointer(d) for d in self.docs[:2]], counter_evidence=[], confidence=0.95,
                    status="proposed", valid_from=None, valid_to=None)
        task = self.queue.make("gen_propositions", snapshot(self.graph, self.store, self.root, node))[0]
        result = self.submit(task, {"ops": [{"op": "UPDATE", "prop": dict(prop, prop_id="missing")}, {"op": "ADD", "prop": prop}]})
        self.assertTrue(result["partial"])
        self.assertEqual(result["counts"], {"accepted": 1, "dropped": 1})
        self.assertIn("ops[0]", result["errors"][0])
        merge(self.queue, self.graph, task)
        self.assertIsNotNone(self.graph.get("propositions", "fiction-prop"))
        task = make_lines(self.queue, self.graph)[0]
        self.assertEqual(len(read_json(self.queue.locate(task)[1] / "input.json")["propositions"]), 1)
        for kind in ("gen_propositions", "cluster_lens", "resolve_entities"):
            from atlas.tasks.queue import instructions_for
            self.assertIn("source language", instructions_for(kind))
        self.assertIn("different documents", instructions_for("gen_propositions"))

    def test_merge_all_nonempty_and_active_graph_statistics(self):
        self.queue = Queue(self.root, self.store, batch_docs=1)
        for task in self.queue.make():
            payload = read_json(self.queue.locate(task)[1] / "input.json")
            doc = next(d for d in self.docs if d.id == payload["documents"][0]["id"])
            output = {"entities": [dict(tmp_id="topic", type="topic", name="虚构主题", aliases=[], evidence=[pointer(doc)])], "relations": [], "statements": []}
            self.assertEqual(self.submit(task, output)["state"], "accepted")
        env = {"ATLAS_DATA_DIR": str(self.root), "ATLAS_OUT_DIR": str(self.root / "site")}
        with patch.dict("os.environ", env), redirect_stdout(StringIO()) as stream:
            self.assertEqual(main(["tasks", "merge", "--all"]), 0)
        self.assertEqual(len(json.loads(stream.getvalue())), 3)
        stats = self.graph.stats()
        self.assertEqual(stats["active_nodes"], 3)
        self.assertEqual(stats["isolated_nodes"], 3)
        with patch.dict("os.environ", env), redirect_stdout(StringIO()):
            self.assertEqual(main(["tasks", "merge", "--all"]), 0)
        self.assertEqual(stats, self.graph.stats())

    def test_clustering_chunks_and_transitive_topic_grouping(self):
        self.extract()
        queue = Queue(self.root, self.store, batch_chars=1)
        tasks = make_lines(queue, self.graph)
        self.assertEqual(len(tasks), 3)
        identifiers = []
        for task in tasks:
            payload = read_json(queue.locate(task)[1] / "input.json")
            self.assertEqual(len(payload["statements"]), 1)
            identifiers.append(payload["statements"][0]["statement_id"])
        self.assertEqual(len(set(identifiers)), 3)
        graph = {t: records(self.graph, t) for t in ("nodes", "propositions", "statements", "lines")}
        for record, about in zip(graph["statements"], (["a"], ["b"], ["a", "b"])):
            record["about"] = about
        lines = grouped_lines(graph)
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0]["timeline"]), 3)
        self.assertEqual(grouped_lines(dict(nodes=[], propositions=[], statements=[], lines=[])), [])

    def test_malformed_envelope_and_empty_output_reject(self):
        task = self.queue.make()[0]
        self.assertEqual(self.submit(task, dict(entities=[], relations=[], statements=[]))["state"], "rejected")
        self.assertEqual(self.submit(task, self.extraction())["state"], "accepted")
        path = self.queue.locate(task)[1]
        envelope = read_json(path / "task.json")
        envelope["input_hash"] = "0" * 64
        (path / "task.json").write_text(json.dumps(envelope), encoding="utf-8")
        result = self.queue.validate(task)
        self.assertEqual(result["state"], "rejected")
        self.assertFalse((self.queue.locate(task)[1] / "accepted.json").exists())


    def test_time_order_respects_offsets_and_unknown_dates(self):
        from atlas.chat import time_key
        from atlas.tasks.lines import validate_lines
        self.assertLess(time_key(None), time_key("2024-01-01"))
        self.assertLess(time_key("2024-01-01T10:00:00+08:00"), time_key("2024-01-01T03:00:00Z"))
        self.extract()
        output = self.cluster_output()
        statements = sorted(records(self.graph, "statements"), key=lambda s: s["ts"])
        statements[0]["ts"] = "2024-01-01T10:00:00+08:00"
        statements[1]["ts"] = "2024-01-01T03:00:00Z"
        self.assertEqual(validate_lines(output, {"statements": statements, "propositions": []}), [])
        statements[0]["ts"] = "unknown"
        self.assertEqual(validate_lines(output, {"statements": statements, "propositions": []}), [])
        self.assertEqual(output["lines"][0]["timeline"][0]["outcome"], "unknown")
