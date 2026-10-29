"""Validators for the digest experiment. Pure functions, standard library only."""
import re

STANCES = {"看多", "看空", "中性", "计划", "观察"}
SECTIONS = ("what", "view", "evolution", "record")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def validate_merge(out, line_ids):
    errs = []
    seen = []
    for m in out.get("merged", []):
        seen += m.get("member_line_ids", [])
    if sorted(seen) != sorted(line_ids):
        errs.append("member_line_ids must partition the input lines exactly once")
    return errs


def validate_digest(out, docs, allowed_extra=""):
    """docs: {doc_id: text}. allowed_extra: input text whose numbers may be used (dates/ts).
    Returns (errors, per_sentence) where per_sentence is a list of (index, ok, reasons)."""
    errs, per = [], []
    sents = out.get("sentences", [])
    for sec in SECTIONS:
        if not any(s.get("section") == sec for s in sents):
            errs.append(f"missing section {sec}")
    for i, s in enumerate(sents):
        why = []
        if s.get("section") not in SECTIONS:
            why.append("bad section")
        if s.get("section") == "view" and s.get("stance") not in STANCES:
            why.append("view needs stance")
        ev = s.get("evidence") or []
        if not ev:
            why.append("no evidence")
        quotes = ""
        for e in ev:
            text = docs.get(e.get("doc_id"))
            if text is None:
                why.append("unknown doc_id")
            elif _norm(e.get("quote")) not in _norm(text):
                why.append("quote not found in source")
            quotes += e.get("quote") or ""
        for n in _NUM.findall(s.get("text", "") + (s.get("ts") or "")):
            if n not in quotes and n not in allowed_extra:
                why.append(f"number {n} not in evidence")
        per.append((i, not why, why))
    return errs, per
