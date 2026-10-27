"""Transactional SQLite graph records and append-only operation history."""
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

from .models import NODE_TYPES

TABLES = {"nodes": "node_id", "edges": "edge_id", "aliases": "alias_id",
          "evidence": "evidence_id", "propositions": "prop_id",
          "corrections": "correction_id", "task_runs": "task_id",
          "statements": "statement_id", "lines": "line_id"}


class GraphStore:
    def __init__(self, data_dir):
        if not data_dir:
            raise ValueError("data_dir must be explicitly configured")
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(data_dir) / "graph.sqlite")
        for table in TABLES:
            self.db.execute(f"CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS ops_log(seq INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, op TEXT NOT NULL, table_name TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT, after_json TEXT)")
        for kind in ("nodes", "edges"):
            self.db.execute(f"CREATE TABLE IF NOT EXISTS legacy_{kind}(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.db.commit()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        """Nest graph operations inside one atomic task merge."""
        if self.db.in_transaction:
            yield
        else:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                yield

    def get(self, table, record_id):
        if table not in TABLES:
            raise ValueError("unknown graph table")
        row = self.db.execute(f"SELECT data FROM {table} WHERE id=?", (record_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _write(self, table, record, op):
        record_id = record[TABLES[table]]
        before = self.get(table, record_id)
        after = json.dumps(record, ensure_ascii=False, sort_keys=True)
        self.db.execute(f"INSERT INTO {table} VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (record_id, after))
        self.db.execute("INSERT INTO ops_log VALUES(NULL,?,?,?,?,?,?)", (
            datetime.now(timezone.utc).isoformat(), op, table, record_id,
            json.dumps(before) if before else None, after))

    def _prepare(self, table, record):
        if table not in TABLES:
            raise ValueError("unknown graph table")
        record = dict(record) if isinstance(record, dict) else asdict(record)
        if table == "nodes" and record.get("type") not in NODE_TYPES:
            raise ValueError("invalid node type")
        if table == "propositions" and not 0 <= record.get("confidence", -1) <= 1:
            raise ValueError("invalid confidence")
        previous = self.get(table, record[TABLES[table]])
        if previous and previous.get("status") == "superseded" and previous != record:
            raise ValueError("superseded records are immutable")
        if table in ("edges", "propositions"):
            if record.get("status") not in ("proposed", "confirmed", "rejected", "superseded"):
                raise ValueError("invalid record status")
            if record.get("valid_from") and record.get("valid_to") and record["valid_to"] < record["valid_from"]:
                raise ValueError("valid_to precedes valid_from")
        if table == "propositions" and record.get("kind") not in ("fact", "opinion", "plan", "preference"):
            raise ValueError("invalid statement kind")
        return record, "NOOP" if previous == record else "UPDATE" if previous else "ADD"

    def put(self, table, record):
        record, op = self._prepare(table, record)
        with self.transaction():
            self._write(table, record, op)
        return op

    def supersede(self, table, old_id, replacement, valid_to):
        if table not in ("edges", "propositions") or not valid_to:
            raise ValueError("supersede requires an edge/proposition and valid_to")
        replacement = dict(replacement) if isinstance(replacement, dict) else asdict(replacement)
        old = self.get(table, old_id)
        new_id = replacement[TABLES[table]]
        if not old or old.get("status") == "superseded" or new_id == old_id or self.get(table, new_id):
            raise ValueError("supersede requires an active old record and a new identity")
        replacement, op = self._prepare(table, replacement)
        if replacement.get("status") == "superseded":
            raise ValueError("replacement must be active")
        if old.get("valid_from") and valid_to < old["valid_from"]:
            raise ValueError("valid_to precedes valid_from")
        old.update(status="superseded", valid_to=valid_to, superseded_by=new_id)
        with self.transaction():
            self._write(table, replacement, op)
            self._write(table, old, "SUPERSEDE")

    def stats(self):
        counts = {table: self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in (*TABLES, "ops_log")}
        rows = {table: [json.loads(r[0]) for r in self.db.execute(f"SELECT data FROM {table}")]
                for table in ("nodes", "edges", "propositions", "lines", "statements")}
        nodes = {n["node_id"] for n in rows["nodes"] if n.get("status") not in ("superseded", "rejected")}
        edges = [e for e in rows["edges"] if e.get("status") in ("proposed", "confirmed") and e["src"] in nodes and e["dst"] in nodes]
        connected = {e[k] for e in edges for k in ("src", "dst")}
        histogram = {"0-0.55": 0, "0.55-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1": 0}
        for prop in rows["propositions"]:
            if prop.get("status") not in ("proposed", "confirmed"):
                continue
            key = next(label for label, cap in zip(histogram, (0.55, 0.7, 0.8, 0.9, 1)) if prop["confidence"] <= cap)
            histogram[key] += 1
        counts.update(active_nodes=len(nodes), active_edges=len(edges), isolated_nodes=len(nodes - connected),
                      edges_per_node=len(edges) / len(nodes) if nodes else 0,
                      avg_points_per_line=sum(len(l["timeline"]) for l in rows["lines"]) / len(rows["lines"]) if rows["lines"] else 0,
                      proposition_confidence_histogram=histogram)
        from ..lenses.judgment_lines import grouped_lines, shift_stats
        counts["displayed_shift_labels"] = shift_stats(grouped_lines(rows))
        return counts
