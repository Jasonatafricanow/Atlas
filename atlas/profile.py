"""User-owned correction journal and its replayable graph projection."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def propositions(graph):
    return [json.loads(row[0]) for row in graph.db.execute("SELECT data FROM propositions ORDER BY id")]


def snapshot(graph, store, data_dir, node_id):
    rows = sync_corrections(graph, data_dir)
    node = graph.get("nodes", node_id)
    if not node or node.get("status") == "superseded":
        raise ValueError("generation requires an active node")
    edges = [json.loads(r[0]) for r in graph.db.execute("SELECT data FROM edges")]
    edges = [e for e in edges if node_id in (e["src"], e["dst"])]
    ids = {node_id} | {e[k] for e in edges for k in ("src", "dst")}
    return dict(node_id=node_id, subgraph=dict(nodes=[graph.get("nodes", i) for i in sorted(ids)], edges=edges),
                propositions=[p for p in propositions(graph) if node_id in p["subject_node_ids"]],
                corrections=rows, documents=sorted((d.to_dict() for d in store.all()), key=lambda d: d["id"]))


def corrections(data_dir):
    path = Path(data_dir) / "corrections.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in
                ("correction_id", "prop_id", "observed_at")) or row.get("verdict") not in ("wrong", "right", "amend")
                or not isinstance(row.get("note"), str) or row["correction_id"] in ids):
            raise ValueError("invalid or duplicate correction journal record")
        if row["verdict"] == "amend" and not row["note"].strip():
            raise ValueError("amend requires a note")
        ids.add(row["correction_id"])
    return rows


def sync_corrections(graph, data_dir):
    rows = corrections(data_dir)
    with graph.transaction():
        projected = {}
        for row in rows:
            previous = graph.get("corrections", row["correction_id"])
            if previous and previous != row:
                raise ValueError("correction journal is append-only")
            if not previous:
                graph.put("corrections", row)
            prop = projected.get(row["prop_id"]) or graph.get("propositions", row["prop_id"])
            if not prop or prop.get("status") == "superseded":
                continue
            if row["verdict"] == "wrong":
                prop.update(status="rejected", suppressed_by=row["correction_id"])
            elif row["verdict"] == "right":
                prop.update(status="confirmed", suppressed_by=None)
            else:
                prop["user_note"] = row["note"]
            projected[row["prop_id"]] = prop
        for prop in projected.values():
            if prop != graph.get("propositions", prop["prop_id"]):
                graph.put("propositions", prop)
    return rows


def correct(graph, data_dir, prop_id, verdict, note=""):
    sync_corrections(graph, data_dir)
    prop = graph.get("propositions", prop_id)
    if not prop or prop["status"] == "superseded":
        raise ValueError("correction requires an existing active proposition")
    if verdict not in ("wrong", "right", "amend") or (verdict == "amend" and not note.strip()):
        raise ValueError("invalid verdict or empty amendment")
    row = dict(correction_id="correction:" + uuid4().hex, prop_id=prop_id, verdict=verdict,
               note=note, observed_at=datetime.now(timezone.utc).isoformat())
    with (Path(data_dir) / "corrections.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_corrections(graph, data_dir)
    return graph.get("propositions", prop_id)
