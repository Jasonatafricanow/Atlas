"""Request-scoped, read-only access to validated digest experiment outputs."""
import hashlib
import json
import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from experiments.digest.validate import lint_digest, normalize_sentence, validate_digest
from ..tasks.validate import check_schema
from ..web_data import connect

LOG = logging.getLogger(__name__)
SCHEMAS = Path(__file__).resolve().parents[2] / "experiments/digest/schemas"


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        LOG.info("Digest file unavailable or invalid")
        return None


class DigestSource:
    """Only visible, current sources may authorize a digest or its drawer refs.

    No cache survives an HTTP request. Input contexts are never returned or
    trusted as corpus text. Diagnostics contain counts/reasons, never content.
    """
    def __init__(self, digest_dir, model):
        self.root = Path(digest_dir)
        self.model = model
        self._loaded = False
        self._lines, self._entities, self._merged = {}, {}, {}

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        rows = self.model.snapshot()
        self._line_ids = {line["line_id"] for line in rows["lines"]}
        self.sources = {s["statement_id"]: s for s in rows["statements"]}
        self.sources.update({p["prop_id"]: p for p in rows["propositions"]})
        self.docs = {}
        try:
            with closing(connect(self.model.root / "corpus.sqlite")) as db:
                for identifier, text, meta in db.execute("SELECT id,text,meta FROM documents"):
                    if self.model.sensitive or not json.loads(meta or "{}").get("sensitive"):
                        self.docs[identifier] = text or ""
        except (sqlite3.Error, OSError, ValueError):
            LOG.info("Digest corpus unavailable")
            return
        self.sentence_schema = read_json(SCHEMAS / "digest.schema.json")["properties"]["sentences"]["items"]
        merged = read_json(self.root / "A_merged.json")
        merge_schema = read_json(SCHEMAS / "merge_lines.schema.json")
        if merged is not None and not check_schema(merged, merge_schema):
            members = [lid for m in merged["merged"] for lid in m["member_line_ids"]]
            lines = {l["line_id"]: l for l in rows["lines"]}
            for k, group in enumerate(merged["merged"], 1):
                ids = group["member_line_ids"]
                if any(members.count(lid) != 1 or lid not in lines for lid in ids):
                    LOG.info("Digest merge membership unavailable or ambiguous")
                    continue
                allowed = {p["statement_id"] for lid in ids for p in lines[lid]["timeline"]}
                digest = self._read(f"B_line{k}", "points", allowed)
                if digest:
                    digest.update(title=group["title"], merged_title=group["title"], member_line_ids=ids,
                                  source={"route": "line", "id": ids[0], "title": group["title"]})
                    digest["validation"]["warnings"] = len(lint_digest(digest))
                    self._merged[f"B_line{k}"] = digest
                    for lid in ids:
                        self._lines[lid] = digest
        for output in sorted(self.root.glob("C_entity*.json")):
            if not re.fullmatch(r"C_entity[1-9][0-9]*", output.stem):
                continue
            inp = read_json(self.root / output.stem / "input.json")
            if not isinstance(inp, dict):
                continue
            matches = [n for n in rows["nodes"] if n["name"] == inp.get("name") and n["type"] == inp.get("type")]
            if len(matches) != 1:
                LOG.info("Digest entity name/type unmatched or ambiguous")
                continue
            node = matches[0]
            allowed = {sid for sid, s in self.sources.items()
                       if node["node_id"] in s.get("about", s.get("subject_node_ids", []))}
            digest = self._read(output.stem, "statements", allowed, inp)
            if digest:
                digest.update(title=node["name"], source={"route": "entity", "id": node["node_id"], "title": node["name"]})
                digest["validation"]["warnings"] = len(lint_digest(digest))
                # Multiple outputs targeting one node are ambiguous, not last-write-wins.
                if node["node_id"] in self._entities:
                    LOG.info("Duplicate entity digests ignored")
                    self._entities[node["node_id"]] = None
                else:
                    self._entities[node["node_id"]] = digest

    def _read(self, stem, field, allowed, inp=None):
        inp = inp if inp is not None else read_json(self.root / stem / "input.json")
        out = read_json(self.root / (stem + ".json"))
        if (not isinstance(inp, dict) or not isinstance(inp.get(field), list)
                or not inp[field] or not isinstance(out, dict) or set(out) != {"sentences"}
                or not isinstance(out["sentences"], list) or len(out["sentences"]) < 4):
            return None
        points = inp[field]
        if any(not isinstance(p, dict) or not isinstance(p.get("ref"), str) for p in points):
            return None
        refs = {p["ref"] for p in points}
        if not refs <= allowed or not refs <= self.sources.keys():
            return None
        sources = [self.sources[sid] for sid in refs]
        if any(s.get("suppressed_by") or s.get("user_note") or s.get("status") in ("rejected", "superseded") for s in sources):
            LOG.info("Digest corrected sources withheld")
            return None
        # The merged digest covers exactly its input members; changed coverage is stale.
        if field == "points" and refs != allowed:
            return None
        docs = {e["doc_id"] for s in sources for e in s.get("evidence", [])}
        mentions = inp.get("mentions") or []
        if not isinstance(mentions, list) or any(not isinstance(m, dict) or not isinstance(m.get("doc_id"), str) for m in mentions):
            return None
        docs.update(m["doc_id"] for m in mentions)
        if not docs <= self.docs.keys():
            return None
        # Reject stale input text/time and changed source pointers, without trusting input context.
        for p in points:
            source = self.sources[p["ref"]]
            if any(key in p and p[key] != source.get(key) for key in ("text", "ts")):
                return None
        for source in sources:
            for e in source.get("evidence", []):
                start, end = e["span"]
                text = self.docs[e["doc_id"]]
                if not 0 <= start < end <= len(text) or hashlib.sha256(text[start:end].encode()).hexdigest()[:12] != e["quote_hash"]:
                    return None
        normalized = [normalize_sentence(s) for s in out["sentences"]]
        candidates = [s for s in normalized if not check_schema(s, self.sentence_schema)]
        extra = json.dumps([s.get("ts") for s in sources])
        _, checks = validate_digest({"sentences": candidates}, {d: self.docs[d] for d in docs}, extra)
        sentences = [s for s, (_, ok, _) in zip(candidates, checks) if ok and
                     all(e["quote"].strip() for e in s["evidence"])]
        total = len(out["sentences"])
        if total != len(sentences):
            LOG.info("Digest sentences dropped: %d/%d", total - len(sentences), total)
        if not sentences:
            return None
        return {"sentences": sentences, "statement_count": len(refs),
                "validation": {"valid": len(sentences), "total": total, "dropped": total - len(sentences)}}

    def for_line(self, line_id):
        self._load()
        if line_id in self._line_ids:
            return self._lines.get(line_id)
        return self._merged.get(line_id)

    def for_entity(self, node_id):
        self._load()
        return self._entities.get(node_id)

    def home_views(self, limit=16):
        self._load()
        result, seen = [], set()
        for digest in [*self._lines.values(), *self._entities.values()]:
            if not digest or id(digest) in seen:
                continue
            seen.add(id(digest))
            result.extend(dict(sentence=s, source=digest["source"]) for s in digest["sentences"]
                          if s["section"] in ("view", "evolution", "record"))
        return result[:max(0, limit)]

    def evidence(self, params):
        """Authorize doc_id+quote against a currently valid digest, then use the drawer."""
        digest = (self.for_line(params.get("id")) if params.get("kind") == "digest_line"
                  else self.for_entity(params.get("id")))
        ref = {"doc_id": params.get("doc_id"), "quote": params.get("quote")}
        if not digest or not any(ref in s["evidence"] for s in digest["sentences"]):
            raise KeyError
        text = self.docs[ref["doc_id"]]
        # The experiment validator ignores whitespace. Retain original offsets.
        offsets = [i for i, c in enumerate(text) if not c.isspace()]
        normalized = "".join(text[i] for i in offsets)
        needle = "".join(ref["quote"].split())
        start = normalized.find(needle)
        if start < 0 or not needle:
            raise ValueError("digest quote unavailable")
        a, b = offsets[start], offsets[start + len(needle) - 1] + 1
        pointer = {"doc_id": ref["doc_id"], "span": [a, b],
                   "quote_hash": hashlib.sha256(text[a:b].encode()).hexdigest()[:12]}
        return self.model.read_evidence(pointer)
