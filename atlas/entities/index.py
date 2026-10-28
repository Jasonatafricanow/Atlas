"""Independent rebuildable mention index and non-executing merge suggestions."""
import hashlib
import itertools
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from ..web_data import ReadModel, connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_merge_suggestions(
 id TEXT PRIMARY KEY, a_node_id TEXT NOT NULL, b_node_id TEXT NOT NULL,
 rule TEXT NOT NULL, score REAL NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'suggested', UNIQUE(a_node_id,b_node_id,rule));
CREATE TABLE IF NOT EXISTS mentions_index(
 node_id TEXT NOT NULL, doc_id TEXT NOT NULL, offset INTEGER NOT NULL,
 length INTEGER NOT NULL, matched_alias TEXT NOT NULL, built_at TEXT NOT NULL,
 PRIMARY KEY(node_id,doc_id,offset,length,matched_alias));
CREATE INDEX IF NOT EXISTS mentions_doc ON mentions_index(doc_id,node_id);
"""


def normalize(name):
    return "".join(c for c in unicodedata.normalize("NFKC", name).casefold() if c.isalnum())


def names_by_node(rows):
    names = {n["node_id"]: {n["name"]} for n in rows["nodes"]}
    for alias in rows["aliases"]:
        if alias["node_id"] in names:
            names[alias["node_id"]].add(alias["name"])
    return names


def usable_alias(alias):
    clean = normalize(alias)
    return len(clean) >= (3 if clean.isascii() else 2)


def alias_matches(text, alias):
    # Exact source spelling preserves offsets and allows hash verification from
    # matched_alias alone. ASCII word boundaries avoid matching 'oak' in 'cloak'.
    if not usable_alias(alias):
        return
    pattern = re.escape(alias)
    if alias.isascii() and alias[0].isalnum():
        pattern = r"(?<![A-Za-z0-9_])" + pattern
    if alias.isascii() and alias[-1].isalnum():
        pattern += r"(?![A-Za-z0-9_])"
    for match in re.finditer(pattern, text):
        yield match.start()


def now():
    # Index production metadata only; never used as source/mention time.
    return datetime.now(timezone.utc).isoformat()


def index_mentions(data_dir):
    root = Path(data_dir).resolve()
    rows = ReadModel(root).snapshot()  # Always excludes sensitive nodes/dependencies.
    names = names_by_node(rows)
    count = documents = 0
    built = now()
    with closing(connect(root / "corpus.sqlite")) as corpus, closing(sqlite3.connect(root / "entities.sqlite")) as db:
        db.executescript(SCHEMA)
        with db:
            db.execute("DELETE FROM mentions_index")
            for doc_id, text, meta in corpus.execute("SELECT id,text,meta FROM documents ORDER BY id"):
                if json.loads(meta or "{}").get("sensitive"):
                    continue
                documents += 1
                for node_id, aliases in sorted(names.items()):
                    for alias in sorted(aliases):
                        for offset in alias_matches(text, alias):
                            db.execute("INSERT INTO mentions_index VALUES(?,?,?,?,?,?)",
                                       (node_id, doc_id, offset, len(alias), alias, built))
                            count += 1
    return {"nodes": len(names), "documents": documents, "mentions": count}


def mention_token(row):
    values = [row[k] for k in ("node_id", "doc_id", "offset", "length", "matched_alias")]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()[:24]


def mentions(data_dir, rows, node_id):
    """Read metadata only. Recheck current aliases and sensitivity after indexing."""
    root = Path(data_dir)
    if not (root / "entities.sqlite").is_file() or not (root / "corpus.sqlite").is_file():
        return []
    names = names_by_node(rows)
    if node_id not in names or next(n for n in rows["nodes"] if n["node_id"] == node_id).get("sensitive"):
        return []
    with closing(connect(root / "entities.sqlite")) as db, closing(connect(root / "corpus.sqlite")) as corpus:
        db.row_factory = sqlite3.Row
        result = []
        for raw in db.execute("SELECT * FROM mentions_index WHERE node_id=? ORDER BY doc_id,offset,length,matched_alias", (node_id,)):
            row = dict(raw)
            alias = row["matched_alias"]
            if alias not in names[node_id] or not usable_alias(alias):
                continue
            doc = corpus.execute("SELECT ts,meta FROM documents WHERE id=?", (row["doc_id"],)).fetchone()
            if not doc or json.loads(doc[1] or "{}").get("sensitive"):
                continue
            pointer = {"doc_id": row["doc_id"], "span": [row["offset"], row["offset"] + row["length"]],
                       "quote_hash": hashlib.sha256(alias.encode()).hexdigest()[:12]}
            result.append({"doc_id": row["doc_id"], "ts": doc[0], "pointer": pointer,
                           "token": mention_token(row)})
    return result


def suggest_merges(data_dir):
    root = Path(data_dir).resolve()
    rows = ReadModel(root).snapshot()
    nodes = {n["node_id"]: n for n in rows["nodes"]}
    # Reuse metadata-only visibility checks: stale sensitive docs/aliases never
    # contribute to co-occurrence, even if the index has not been rebuilt.
    docs = {nid: {m["doc_id"] for m in mentions(root, rows, nid)} for nid in nodes}
    created = now()
    candidates = []
    for a, b in itertools.combinations(sorted(nodes), 2):
        if nodes[a]["type"] != nodes[b]["type"]:
            continue
        left, right = normalize(nodes[a]["name"]), normalize(nodes[b]["name"])
        rules = []
        if left and left == right:
            rules.append(("normalized_name_equal", 1.0))
        elif min(len(left), len(right)) >= 4 and (left in right or right in left):
            rules.append(("name_contains", min(len(left), len(right)) / max(len(left), len(right))))
        shared, union = docs[a] & docs[b], docs[a] | docs[b]
        if len(shared) >= 3 and len(shared) / len(union) >= 0.5:
            rules.append(("cooccurrence", len(shared) / len(union)))
        for rule, score in rules:
            identifier = hashlib.sha256(json.dumps([a, b, rule]).encode()).hexdigest()[:24]
            candidates.append((identifier, a, b, rule, score, created))
    with closing(sqlite3.connect(root / "entities.sqlite")) as db:
        db.executescript(SCHEMA)
        with db:
            # Retain reviewed rows if another consumer adds decisions later.
            db.execute("DELETE FROM entity_merge_suggestions WHERE status='suggested'")
            db.executemany("INSERT OR IGNORE INTO entity_merge_suggestions(id,a_node_id,b_node_id,rule,score,created_at) VALUES(?,?,?,?,?,?)", candidates)
        count = db.execute("SELECT COUNT(*) FROM entity_merge_suggestions WHERE status='suggested'").fetchone()[0]
    return {"nodes": len(nodes), "suggestions": count}


def merge_suggestions(data_dir, rows, node_id):
    root = Path(data_dir)
    if not (root / "entities.sqlite").is_file():
        return []
    visible = {n["node_id"] for n in rows["nodes"] if not n.get("sensitive")}
    with closing(connect(root / "entities.sqlite")) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(
            "SELECT * FROM entity_merge_suggestions WHERE (a_node_id=? OR b_node_id=?) AND status='suggested' ORDER BY score DESC,id",
            (node_id, node_id)) if {r["a_node_id"], r["b_node_id"]} <= visible]
