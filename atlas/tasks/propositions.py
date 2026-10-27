"""Merge proposition operations while preserving user authority."""
import json
from dataclasses import asdict

from ..graph.models import Proposition
from ..profile import propositions


def same_claim(left, right):
    return (set(left["subject_node_ids"]) == set(right["subject_node_ids"])
            and " ".join(left["text"].casefold().split()) == " ".join(right["text"].casefold().split()))


def merge_propositions(graph, payload, output, observed_at):
    documents = {d["id"]: d for d in payload["documents"]}
    for operation in output["ops"]:
        prop = operation["prop"]
        old = graph.get("propositions", operation.get("supersedes", prop["prop_id"]))
        suppressed = next((p for p in propositions(graph) if p.get("suppressed_by") and
                           (p["prop_id"] == prop["prop_id"] or same_claim(p, prop))), None)
        if suppressed or (old and old.get("suppressed_by")):
            graph._write("propositions", suppressed or old, "NOOP")
            continue
        if operation["op"] == "NOOP":
            if not old:
                raise ValueError("NOOP requires an existing proposition")
            graph._write("propositions", old, "NOOP")
            continue
        if operation["op"] == "ADD" and old:
            raise ValueError("ADD requires a new proposition identity")
        if operation["op"] in ("UPDATE", "SUPERSEDE") and not old:
            raise ValueError("operation requires an existing proposition")
        if old and any(e not in prop["counter_evidence"] for e in old.get("counter_evidence", [])):
            raise ValueError("live counter_evidence must be retained")
        nodes = [graph.get("nodes", i) for i in prop["subject_node_ids"]]
        if any(not n or n.get("status") == "superseded" for n in nodes):
            raise ValueError("proposition subjects must be active nodes")
        record = asdict(Proposition(**prop, observed_at=observed_at))
        record["sensitive"] = any(n.get("sensitive") for n in nodes) or any(
            documents[e["doc_id"]].get("meta", {}).get("sensitive", False)
            for e in prop["evidence"] + prop["counter_evidence"])
        if old:
            record["sensitive"] |= old.get("sensitive", False)
            if old.get("user_note"):
                record["user_note"] = old["user_note"]
        # Confirmed user judgments remain authoritative over subsequent agent output.
        verdicts = [r[0] for r in graph.db.execute("SELECT data FROM corrections")]
        verdicts = [json.loads(r) for r in verdicts]
        if old and any(r["prop_id"] == old["prop_id"] and r["verdict"] == "right" for r in verdicts):
            if operation["op"] == "SUPERSEDE":
                graph._write("propositions", old, "NOOP")
                continue
            record["status"] = "confirmed"
            # An UPDATE cannot silently rewrite a user-confirmed claim.
            record["text"] = old["text"]
            record["subject_node_ids"] = old["subject_node_ids"]
        if operation["op"] == "SUPERSEDE":
            graph.supersede("propositions", old["prop_id"], record, record["valid_from"])
        else:
            graph.put("propositions", record)
