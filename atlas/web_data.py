"""Read-only projections for the local UI; never initializes or migrates a store."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .chat import time_key
from .profile import corrections


FIELDS = {
    "nodes": "node_id name type evidence valid_from valid_to observed_at sensitive",
    "edges": "edge_id src dst type evidence valid_from valid_to observed_at status superseded_by confidence sensitive",
    "aliases": "alias_id name node_id",
    "statements": "statement_id text about kind stance ts speaker evidence confidence sensitive",
    "propositions": "prop_id text subject_node_ids kind ts speaker evidence counter_evidence confidence valid_from valid_to observed_at status superseded_by suppressed_by user_note sensitive",
    "lines": "line_id title topic_node_id timeline sensitive",
}
POINT_FIELDS = "statement_id shift shift_source reason outcome outcome_reason outcome_statement_ids".split()


def project(row, fields):
    result = {key: row[key] for key in fields if key in row}
    for field in ("evidence", "counter_evidence"):
        if field in result:
            result[field] = [{key: pointer[key] for key in ("doc_id", "span", "quote_hash") if key in pointer}
                             for pointer in result[field]]
    return result


def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


class ReadModel:
    def __init__(self, data_dir, sensitive=False):
        self.root = Path(data_dir).resolve()
        self.sensitive = sensitive

    def snapshot(self):
        with closing(connect(self.root / "graph.sqlite")) as db:
            db.execute("BEGIN")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            rows = {table: [project(json.loads(r[0]), fields.split()) for r in
                           db.execute(f"SELECT data FROM {table} ORDER BY id")] if table in tables else []
                    for table, fields in FIELDS.items()}
        # Project the authoritative journal in memory; the server never replays writes.
        props = {p["prop_id"]: p for p in rows["propositions"]}
        for correction in corrections(self.root):
            prop = props.get(correction["prop_id"])
            if not prop or prop.get("status") == "superseded":
                continue
            if correction["verdict"] == "wrong":
                prop.update(status="rejected", suppressed_by=correction["correction_id"])
            elif correction["verdict"] == "right":
                prop.update(status="confirmed", suppressed_by=None)
            else:
                prop["user_note"] = correction["note"]
        hidden_docs = set()
        if not self.sensitive and (self.root / "corpus.sqlite").is_file():
            with closing(connect(self.root / "corpus.sqlite")) as db:
                hidden_docs = {r[0] for r in db.execute("SELECT id,meta FROM documents")
                               if json.loads(r[1] or "{}").get("sensitive")}

        def visible(row):
            return self.sensitive or not (row.get("sensitive") or any(
                e.get("doc_id") in hidden_docs for e in row.get("evidence", []) + row.get("counter_evidence", [])))

        rows["nodes"] = [n for n in rows["nodes"] if visible(n)]
        nodes = {n["node_id"] for n in rows["nodes"]}
        rows["edges"] = [e for e in rows["edges"] if visible(e) and {e["src"], e["dst"]} <= nodes]
        rows["aliases"] = [a for a in rows["aliases"] if a["node_id"] in nodes]
        rows["statements"] = [s for s in rows["statements"] if visible(s) and set(s.get("about", [])) <= nodes]
        rows["propositions"] = [p for p in rows["propositions"] if visible(p) and set(p["subject_node_ids"]) <= nodes]
        rows["lines"] = [l for l in rows["lines"] if visible(l) and l.get("topic_node_id") in nodes]
        return rows

    def lines(self, rows):
        sources = {s["statement_id"]: s for s in rows["statements"]}
        sources.update({p["prop_id"]: p for p in rows["propositions"]})
        groups = {}
        for line in rows["lines"]:
            topic = line["topic_node_id"]
            group = groups.setdefault(topic, {"topic_node_id": topic, "lines": [], "timeline": []})
            group["lines"].append(project(line, ("line_id", "title")))
            for raw in line.get("timeline", []):
                source = sources.get(raw["statement_id"])
                if not source:
                    continue
                point = project(raw, POINT_FIELDS)
                # Keep annotations with their original line. Conflicting annotations
                # remain inspectable instead of arbitrarily choosing a winning label.
                annotation = dict(point, line_id=line["line_id"])
                support = [sources.get(i) for i in point.get("outcome_statement_ids", [])]
                invalid = lambda s: not s or s.get("suppressed_by") or s.get("status") in ("rejected", "superseded")
                if invalid(source) or any(invalid(s) for s in support):
                    annotation.update(outcome="unknown", outcome_reason="", outcome_statement_ids=[])
                item = next((p for p in group["timeline"] if p["statement_id"] == point["statement_id"]), None)
                if item is None:
                    item = {"statement_id": point["statement_id"], "source": source, "annotations": []}
                    group["timeline"].append(item)
                item["annotations"].append(annotation)
        result = []
        for group in groups.values():
            if group["timeline"]:
                group["timeline"].sort(key=lambda p: (time_key(p["source"].get("ts")), p["statement_id"]))
                result.append(group)
        return sorted(result, key=lambda g: g["topic_node_id"])

    def evidence(self, rows, params):
        table = params.get("kind")
        if table not in ("nodes", "edges", "statements", "propositions"):
            raise KeyError
        identity = FIELDS[table].split()[0]
        record = next((r for r in rows[table] if r[identity] == params.get("id")), None)
        field = params.get("field", "evidence")
        if not record or field not in ("evidence", "counter_evidence"):
            raise KeyError
        try:
            index = int(params.get("index", "0"))
            if index < 0:
                raise ValueError
            pointer = record.get(field, [])[index]
        except (ValueError, IndexError):
            raise KeyError from None
        result = {"pointer": pointer}
        if not (self.root / "corpus.sqlite").is_file():
            return result
        with closing(connect(self.root / "corpus.sqlite")) as db:
            row = db.execute("SELECT text,ts,author,channel,meta FROM documents WHERE id=?", (pointer["doc_id"],)).fetchone()
        if not row:
            return result
        text, ts, author, channel, meta = row
        if not self.sensitive and json.loads(meta or "{}").get("sensitive"):
            raise KeyError
        start, end = pointer["span"]
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text)):
            raise ValueError("invalid evidence")
        quote = text[start:end]
        if hashlib.sha256(quote.encode()).hexdigest()[:12] != pointer["quote_hash"]:
            raise ValueError("invalid evidence")
        result.update(quote=quote, before=text[max(0, start-240):start], after=text[end:end+240],
                      ts=ts, author=author, channel=channel)
        return result

    def get(self, route, params):
        rows = self.snapshot()
        if route == "evidence":
            return self.evidence(rows, params)
        lines = self.lines(rows)
        nodes = {n["node_id"]: n for n in rows["nodes"]}
        if route == "toc":
            return {"lines": [{"topic_node_id": l["topic_node_id"], "name": nodes[l["topic_node_id"]]["name"]} for l in lines],
                    "nodes": [project(n, ("node_id", "name", "type")) for n in rows["nodes"]]}
        if route == "lines":
            return {"lines": lines, "nodes": list(nodes.values())}
        if route == "line":
            line = next((l for l in lines if l["topic_node_id"] == params.get("id")), None)
            if line is None:
                raise KeyError
            return {"line": line, "node": nodes[line["topic_node_id"]]}
        if route == "home":
            return {"lines": lines, "nodes": list(nodes.values()), "propositions": rows["propositions"]}
        if route == "entities":
            return {"nodes": list(nodes.values())}
        if route == "entity":
            node = nodes.get(params.get("id"))
            if node is None:
                raise KeyError
            identifier = node["node_id"]
            edges = [e for e in rows["edges"] if identifier in (e["src"], e["dst"])]
            neighborhood = {identifier} | {e[k] for e in edges for k in ("src", "dst")}
            return {"node": node, "nodes": [nodes[i] for i in sorted(neighborhood)], "edges": edges,
                    "aliases": [a for a in rows["aliases"] if a["node_id"] == identifier],
                    "statements": [s for s in rows["statements"] if identifier in s.get("about", [])],
                    "propositions": [p for p in rows["propositions"] if identifier in p["subject_node_ids"]],
                    "lines": [l for l in lines if l["topic_node_id"] == identifier or any(identifier in p["source"].get("about", p["source"].get("subject_node_ids", [])) for p in l["timeline"])]}
        if route == "search":
            query = params.get("q", "").strip().casefold()[:200]
            hits = []
            if query:
                alias_ids = {a["node_id"] for a in rows["aliases"] if query in a["name"].casefold()}
                for n in nodes.values():
                    if query in n["name"].casefold() or n["node_id"] in alias_ids:
                        hits.append({"node": project(n, ("node_id", "name", "type"))})
                for line in lines:
                    if any(query in title.get("title", "").casefold() for title in line["lines"]) or any(query in p["source"].get("text", "").casefold() for p in line["timeline"]):
                        hits.append({"line": {"topic_node_id": line["topic_node_id"], "name": nodes[line["topic_node_id"]]["name"]}})
                for prop in rows["propositions"]:
                    if query in prop["text"].casefold():
                        hits.append({"proposition": prop})
            return {"results": hits[:100], "truncated": len(hits) > 100}
        raise KeyError
