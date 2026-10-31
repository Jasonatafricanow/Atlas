"""Validators for the digest experiment. Pure functions, standard library only."""
import re
import unicodedata
from decimal import Decimal

STANCES = {"看多", "看空", "中性", "计划", "观察"}
SECTIONS = ("what", "view", "evolution", "record")
_DOUBLED_FUNCTION = re.compile(r"([的是了在])\1+")


def lint_digest(out):
    """Advisory only: one warning per repeated run in a title or sentence.

    Do not inspect evidence, repair text, or change validation decisions.
    Diagnostics identify locations without copying source content.
    """
    if not isinstance(out, dict):
        return []
    fields = [("title", out.get("title"))]
    sentences = out.get("sentences")
    if isinstance(sentences, list):
        fields.extend((f"sentences[{i}].text", s.get("text"))
                      for i, s in enumerate(sentences) if isinstance(s, dict))
    return [{"field": field, "offset": match.start(), "code": "doubled_function_character"}
            for field, text in fields if isinstance(text, str)
            for match in _DOUBLED_FUNCTION.finditer(text)]

# Consume the whole numeric run, including malformed grouping, so a suffix
# cannot accidentally authorize a smaller number. NFKC handles width only;
# quotation matching below still checks the actual source characters.
_NUM = re.compile(r"(?<![\d.])[-+]?(?:\d+(?:[,.]\d+)*|\.\d+)(?:\s*[万亿])?(?:\s*(?:%|percent\b))?", re.I)
_VALUE = re.compile(r"([-+]?(?:\d{1,3}(?:,\d{3})+|\d+|(?=\.))(?:\.\d+)?)([万亿]?)(%?)")


def numbers(text):
    result = set()
    for match in _NUM.finditer(unicodedata.normalize("NFKC", text).replace("−", "-")):
        raw = re.sub(r"\s+", "", match.group()).lower().replace("percent", "%")
        parsed = _VALUE.fullmatch(raw)
        if not parsed:
            result.add(("unparsed", raw))
            continue
        value, scale, unit = parsed.groups()
        number = Decimal(value.replace(",", ""))
        sign, digits, exponent = number.as_tuple()
        number = Decimal((sign, digits, exponent + {"": 0, "万": 4, "亿": 8}[scale]))
        result.add((number, unit))
    return result


def normalize_sentence(sentence):
    """Null optional metadata means absent; required facts are never filled in."""
    if not isinstance(sentence, dict):
        return sentence
    normalized = {k: v for k, v in sentence.items()
                  if v is not None or k not in ("ts", "stance", "outcome")}
    if isinstance(normalized.get("evidence"), list):
        unique = []
        for ref in normalized["evidence"]:
            if ref not in unique:
                unique.append(ref)
        normalized["evidence"] = unique
    return normalized


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def validate_merge(out, line_ids):
    if not isinstance(out, dict) or not isinstance(out.get("merged"), list):
        return ["merged must be a list"]
    seen = []
    for group in out["merged"]:
        if (not isinstance(group, dict) or not isinstance(group.get("member_line_ids"), list)
                or not group["member_line_ids"]
                or any(not isinstance(lid, str) for lid in group["member_line_ids"])):
            return ["invalid merge membership"]
        seen.extend(group["member_line_ids"])
    if sorted(seen) != sorted(line_ids):
        return ["member_line_ids must partition the input lines exactly once"]
    return []


def validate_digest(out, docs, allowed_extra=""):
    """Validate each sentence independently, retaining indexed failure reasons.

    Only cited quotes authorize body numbers. Source timestamp numbers in
    allowed_extra may additionally authorize ts, never a claim's price/count.
    """
    errs, per = [], []
    if not isinstance(out, dict) or not isinstance(out.get("sentences"), list):
        return ["sentences must be a list"], []
    sents = out["sentences"]
    for sec in SECTIONS:
        if not any(isinstance(s, dict) and s.get("section") == sec for s in sents):
            errs.append(f"missing section {sec}")
    for i, raw in enumerate(sents):
        s = normalize_sentence(raw)
        if not isinstance(s, dict):
            per.append((i, False, ["sentence must be an object"]))
            continue
        why = []
        if s.get("section") not in SECTIONS:
            why.append("bad section")
        if (s.get("section") == "view" or "stance" in s) and s.get("stance") not in tuple(STANCES):
            why.append("invalid or missing stance")
        if "outcome" in s and s["outcome"] not in ("confirmed", "refuted", "mixed", "unknown"):
            why.append("bad outcome")
        text, ts = s.get("text"), s.get("ts", "")
        if not isinstance(text, str) or not text.strip():
            why.append("missing text")
            text = ""
        if not isinstance(ts, str):
            why.append("bad timestamp")
            ts = ""
        ev = s.get("evidence")
        if not isinstance(ev, list) or not ev:
            why.append("no evidence")
            ev = []
        supported = set()
        for e in ev:
            if not isinstance(e, dict) or not isinstance(e.get("doc_id"), str):
                why.append("bad evidence")
                continue
            source, quote = docs.get(e["doc_id"]), e.get("quote")
            if not isinstance(quote, str) or not _norm(quote):
                why.append("empty quote")
            elif not isinstance(source, str):
                why.append("unknown doc_id")
            elif _norm(quote) not in _norm(source):
                why.append("quote not found in source")
            else:
                # Union per quote: duplicates and quote boundaries add no numbers.
                supported.update(numbers(quote))
        if numbers(text) - supported:
            why.append("number not in evidence")
        if numbers(ts) - supported - numbers(allowed_extra):
            why.append("timestamp number not in evidence or input timestamps")
        per.append((i, not why, why))
    return errs, per
