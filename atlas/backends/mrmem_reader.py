"""Read-only AML storage projection, versioned against MR-Mem bb0d296.

Never instantiate MemoryRuntime: constructors migrate stores and Search may compile.
This first reader uses literal semantic-text search, not provider retrieval ranking.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path


class MrMemReader:
    def __init__(self, root, user_id, search_service=None):
        if not user_id or not user_id.strip():
            raise ValueError("MR-Mem requires an explicit user ID")
        self.root, self.user_id = Path(root), user_id
        self.search_service = search_service
        for name in ("memory.sqlite", "aml_source.sqlite"):
            if not (self.root / name).is_file():
                raise ValueError("MR-Mem stores unavailable")

    def connect(self, name):
        db = sqlite3.connect((self.root / name).resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        return db

    def memories(self):
        with closing(self.connect("memory.sqlite")) as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM canonical_memory")]
        return {m["memory_id"]: m for m in rows
                if m["scope"].get("user_id") == self.user_id
                and m["scope"].get("domain") == "user" and m["lifecycle"] == "active"}

    def pointer(self, ref):
        return {k: ref.get(k) for k in
                ("source_namespace", "session_id", "record_id", "fingerprint")}

    def source(self, ref):
        if ref.get("source_namespace") != "aml" or not ref.get("fingerprint"):
            raise ValueError("unsupported or unversioned source")
        with closing(self.connect("aml_source.sqlite")) as db:
            row = db.execute("SELECT * FROM messages WHERE record_id=? AND user_id=? AND session_id=?",
                             (ref["record_id"], self.user_id, ref["session_id"])).fetchone()
        if row is None:
            raise KeyError("source unavailable")
        if (row["fingerprint"] != ref["fingerprint"] or
                hashlib.sha256(row["content"].encode("utf-8")).hexdigest() != ref["fingerprint"]):
            raise ValueError("source version changed")
        return row

    def item(self, memory):
        refs = memory["provenance"].get("source_refs", [])
        if not refs:
            raise ValueError("source-backed memory required")
        sources = [self.source(r) for r in refs]
        times = [r["occurred_at"] for r in sources if r["time_given"]]
        return {"id": memory["memory_id"], "text": memory["content"],
                "ts": min(times) if times else None,
                "evidence": [self.pointer(r) for r in refs]}

    def search(self, params):
        if self.search_service is not None:
            query = params.get('q', '').strip()
            if not query:
                return {'items': [], 'search_mode': 'mrmem_runtime', 'limit':100}
            found = self.search_service.search(self.user_id, query)
            current = self.memories()
            items = []
            for hit in found:
                identifier = hit['id']
                ids = [identifier] if identifier in current else []
                if identifier.startswith('line:') and identifier[5:] in current:
                    ids = [identifier[5:]]
                elif identifier.startswith('raw:'):
                    record = identifier[4:]
                    ids = [m['memory_id'] for m in current.values() if any(
                        r.get('record_id') == record for r in m['provenance'].get('source_refs', []))]
                elif identifier.startswith('thread:'):
                    with closing(self.connect('aml_source.sqlite')) as db:
                        ids = [r[0] for r in db.execute(
                            'SELECT memory_id FROM thread_members WHERE user_id=? AND thread_id=?',
                            (self.user_id, identifier[7:])) if r[0] in current]
                linked = []
                for mid in dict.fromkeys(ids):
                    try:
                        self.item(current[mid])
                    except (KeyError, ValueError):
                        continue
                    linked.append(mid)
                items.append({'id':identifier, 'text':hit['content'], 'score':hit.get('score'),
                              'ts':hit.get('created_at'), 'memory_ids':linked})
            return {'items':items, 'search_mode':'mrmem_runtime', 'limit':100}
        query = params.get("q", "").strip().casefold()
        items = []
        for memory in self.memories().values():
            if query and query not in memory["content"].casefold():
                continue
            try:
                items.append(self.item(memory))
            except (KeyError, ValueError):
                continue
        items.sort(key=lambda x: (x["ts"] is None, x["ts"] or "", x["id"]))
        return {"items": items[:100], "search_mode": "literal_semantic_text", "limit": 100}

    def detail(self, params):
        memory = self.memories()[params["id"]]
        item = self.item(memory)
        with closing(self.connect("aml_source.sqlite")) as db:
            segments = [dict(r) for r in db.execute(
                "SELECT t.thread_id,t.summary,t.last_seq FROM threads t JOIN thread_members m "
                "ON t.user_id=m.user_id AND t.thread_id=m.thread_id "
                "WHERE m.user_id=? AND m.memory_id=? AND t.summary<>'' ORDER BY t.last_seq", (self.user_id, item["id"]))]
        # Preserve version boundaries rather than inventing a whole-Line summary.
        current = self.memories()
        visible = []
        with closing(self.connect("aml_source.sqlite")) as db:
            for segment in segments:
                members = [r[0] for r in db.execute(
                    "SELECT memory_id FROM thread_members WHERE user_id=? AND thread_id=?",
                    (self.user_id, segment["thread_id"]))]
                try:
                    for member in members:
                        self.item(current[member])
                except (KeyError, ValueError):
                    continue
                visible.append(dict(segment, member_ids=members))
        item["segments"] = visible
        return item

    def evidence(self, params):
        memory = self.memories()[params["id"]]
        index = int(params["index"])
        refs = memory["provenance"]["source_refs"]
        if index < 0 or index >= len(refs):
            raise ValueError("invalid evidence index")
        ref = refs[index]
        row = self.source(ref)
        if params.get("fingerprint") != ref.get("fingerprint"):
            raise ValueError("evidence selection changed")
        return {"ref": self.pointer(ref), "quote": row["content"], "role": row["role"],
                "ts": row["occurred_at"] if row["time_given"] else None,
                "verification": "source_fingerprint_matched"}

    def unavailable(self, params):
        return {"backend":"mrmem", "message":"当前 MR-Mem 阅读合同未提供实体图谱与画像接口。记忆过程、原生搜索和来源证据可从左侧访问。"}

    def overview(self, params):
        items = []
        for memory in self.memories().values():
            try:
                items.append(self.item(memory))
            except (KeyError, ValueError):
                continue
        items.sort(key=lambda x: (x["ts"] is None, x["ts"] or "", x["id"]))
        visible = {m["id"] for m in items}
        with closing(self.connect("aml_source.sqlite")) as db:
            members = {}
            for row in db.execute("SELECT thread_id,memory_id FROM thread_members WHERE user_id=?", (self.user_id,)):
                members.setdefault(row[0], []).append(row[1])
            segments = [dict(row, member_ids=members.get(row["thread_id"], [])) for row in db.execute(
                "SELECT thread_id,summary,last_seq FROM threads WHERE user_id=? AND summary<>'' ORDER BY last_seq DESC", (self.user_id,))]
        segments = [s for s in segments if s["member_ids"] and set(s["member_ids"]) <= visible]
        return {"backend":"mrmem", "items":items[:100], "segments":segments[:100],
                "memory_count":len(items), "segment_count":len(segments), "lines":[], "nodes":[]}
