"""M8 regressions using only fictional records and disposable local stores."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from atlas.graph.store import GraphStore
from atlas.lenses.judgment_lines import grouped_lines, similar_titles
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.lines import make_lines
from atlas.tasks.merge import merge, records
from atlas.tasks.queue import Queue, instructions_for, read_json
from atlas.tasks.validate import accept_items


def point(identifier, **kwargs):
    return dict(statement_id=identifier, shift="first", reason="Fictional source",
                outcome="unknown", outcome_statement_ids=[], outcome_reason="", **kwargs)


def line(identifier, points, topic="garden", title="Fictional garden"):
    return dict(line_id=identifier, topic=topic, topic_node_id=topic, title=title, timeline=points)


class LinesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.addCleanup(self.store.db.close)
        self.graph = GraphStore(self.root)
        self.addCleanup(self.graph.close)
        self.store.upsert([Document("fiction", "synthetic", "2024-01-01", "Fictional garden.")])
        self.queue = Queue(self.root, self.store)
        self.evidence = [dict(doc_id="fiction", span=[0, 17],
                              quote_hash=hashlib.sha256(b"Fictional garden.").hexdigest()[:12])]
        self.sources = [dict(statement_id=f"statement-long-{i}", ref=f"s{i+1}",
                             ts=f"2024-01-0{i+1}", speaker="Fictional gardener",
                             text="Fictional garden.", about=["garden"], evidence=[])
                        for i in range(4)]
        self.payload = dict(documents=[], statements=self.sources, propositions=[], existing_lines=[])

    def accept(self, points, extra=None):
        output = dict(lines=[dict(line_id="fiction", title="Fictional garden", topic="garden", timeline=points)])
        if extra:
            output["lines"].extend(extra)
        return accept_items("cluster_lens", output, self.payload, self.store)

    def test_short_refs_compact_pack_and_queue_roundtrip(self):
        self.graph.put("nodes", dict(node_id="garden", name="Fictional garden", type="topic"))
        for source in self.sources:
            record = dict(source, evidence=self.evidence)
            self.graph.put("statements", record)
        self.graph.put("propositions", dict(prop_id="fiction-prop", text="Fictional plan",
            subject_node_ids=["garden"], evidence=self.evidence, counter_evidence=[], kind="plan", confidence=.5, status="proposed"))
        task = make_lines(self.queue, self.graph)[0]
        path = self.queue.locate(task)[1]
        payload = read_json(path / "input.json")
        packed = payload["statements"] + payload["propositions"]
        self.assertEqual(len({s["ref"] for s in packed}), 5)
        self.assertEqual(payload["documents"], [{"id": "fiction"}])
        for source in packed:
            self.assertNotIn("evidence", source)
            self.assertEqual(source["about_names"], {"garden": "Fictional garden"})
        output = dict(lines=[dict(line_id="fiction", title="Fictional garden", topic="garden",
                                 timeline=[dict(ref=s["ref"], **{k: v for k, v in point("").items() if k != "statement_id"})
                                           for s in reversed(packed)])])
        response = self.root / "response.json"
        response.write_text(json.dumps(output), encoding="utf-8")
        result = self.queue.submit(task, response)
        self.assertEqual(result["state"], "accepted", result)
        self.assertEqual(result["counts"]["unassigned"], 0)
        self.assertIn(output, [read_json(p) for p in path.parent.parent.glob("accepted/*/attempts/*/output.json")])
        merge(self.queue, self.graph, task)
        self.assertEqual(len(records(self.graph, "lines")[0]["timeline"]), 5)
        self.assertEqual(merge(self.queue, self.graph, task)["state"], "noop")

    def test_repair_drops_points_orders_and_deduplicates_across_lines(self):
        extra = dict(line_id="other", title="Other fiction", topic="garden", timeline=[point("s1"), point("s4")])
        kept, errors, fatal, counts = self.accept([point("s3"), point("missing"), point("s1"), point("s1")], [extra])
        self.assertFalse(fatal, errors)
        self.assertEqual([p["statement_id"] for p in kept["lines"][0]["timeline"]],
                         [self.sources[i]["statement_id"] for i in (0, 2)])
        self.assertEqual([p["shift"] for p in kept["lines"][0]["timeline"]], ["first", "same"])
        self.assertEqual(len(kept["lines"][1]["timeline"]), 1)
        self.assertEqual(counts["unassigned"], 1)
        self.assertTrue(errors)

    def test_unknown_only_line_dropped_and_empty_task_rejected(self):
        bad = dict(line_id="bad", title="Fiction", topic="garden", timeline=[point("missing")])
        kept, errors, fatal, counts = self.accept([point("s1")], [bad])
        self.assertFalse(fatal, errors)
        self.assertEqual(counts, dict(accepted=1, dropped=1, unassigned=3))
        self.assertTrue(self.accept([point("missing")])[2])

    def test_outcomes_require_later_related_points_on_same_line(self):
        for support, outcome, reason in ((["s2"], "confirmed", "Fictional result"),
                                         (["missing"], "confirmed", "Fictional result"),
                                         (["s1"], "refuted", "Fictional result"),
                                         (["s4"], "mixed", "Fictional result"),
                                         (["s2"], "invalid", "Fictional result"),
                                         (["s2"], "confirmed", "")):
            first = point("s1")
            first.update(outcome=outcome, outcome_statement_ids=support, outcome_reason=reason)
            kept, errors, fatal, _ = self.accept([first, point("s2")])
            self.assertFalse(fatal, errors)
            actual = kept["lines"][0]["timeline"][0]
            valid = support == ["s2"] and outcome == "confirmed" and bool(reason)
            self.assertEqual(actual["outcome"], "confirmed" if valid else "unknown")
            self.assertEqual(actual["outcome_statement_ids"], [self.sources[1]["statement_id"]] if valid else [])
        self.sources[0]["ts"] = None
        first.update(outcome="confirmed", outcome_statement_ids=["s2"], outcome_reason="Fiction")
        self.assertEqual(self.accept([first, point("s2")])[0]["lines"][0]["timeline"][0]["outcome"], "unknown")

    def test_coverage_instructions(self):
        instructions = instructions_for("cluster_lens")
        for term in ("EVERY", "exactly one", ">= 3", "singletons", "sector", "person", "previous point",
                     "source language", "confirmed/refuted/mixed", "unassigned_count"):
            self.assertIn(term, instructions)

    def test_cross_batch_topics_titles_and_corrections(self):
        sources = copy.deepcopy(self.sources)
        sources[2]["about"] = ["other"]
        sources[3]["about"] = ["unrelated"]
        lines = [line("a", [point(sources[0]["statement_id"])]),
                 line("b", [point(sources[1]["statement_id"])], title="Garden plans"),
                 line("c", [point(sources[2]["statement_id"])], topic="other", title="Ｆｉｃｔｉｏｎａｌ Garden!"),
                 line("d", [point(sources[3]["statement_id"])], topic="unrelated", title="Fictional sailing")]
        graph = dict(nodes=[], statements=sources, propositions=[], lines=lines)
        result = grouped_lines(graph)
        self.assertEqual(sorted(len(l["timeline"]) for l in result), [1, 3])
        merged = next(l for l in result if len(l["timeline"]) == 3)
        self.assertEqual([p["shift"] for p in merged["timeline"]], ["first", None, None])
        first = lines[0]["timeline"][0]
        first.update(outcome="confirmed", outcome_statement_ids=[sources[1]["statement_id"]], outcome_reason="Fictional result")
        sources[1]["suppressed_by"] = "fiction-correction"
        self.assertEqual(grouped_lines(graph)[0]["timeline"][0]["outcome"], "unknown")
        self.assertTrue(similar_titles("abcdef", "abcde"))
        self.assertFalse(similar_titles("abcdef", "abc"))
        self.assertFalse(similar_titles("!", "?"))

    def test_fallback_hubs_and_empty_graph(self):
        sources = [dict(statement_id=f"fiction-{i}", text="Fictional note", ts=None,
                        about=["person", "hub", f"topic-{i}"], evidence=[]) for i in range(16)]
        graph = dict(nodes=[dict(node_id="person", type="person")], statements=sources, propositions=[], lines=[])
        result = grouped_lines(graph)
        self.assertEqual(len(result), 16)
        self.assertTrue(all(l["timeline"][0]["shift"] is None for l in result))
        self.assertEqual(grouped_lines(dict(nodes=[], statements=[], propositions=[], lines=[])), [])
