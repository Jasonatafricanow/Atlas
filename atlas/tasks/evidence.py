"""Resolve short agent quotations to canonical source pointers."""
import hashlib
import unicodedata


def normalized(text):
    """Ignore whitespace and fold full-width punctuation, retaining source offsets."""
    chars, offsets = [], []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        if unicodedata.category(char).startswith("P") and unicodedata.east_asian_width(char) == "F":
            char = unicodedata.normalize("NFKC", char)
        chars.append(char)
        offsets.extend([index] * len(char))
    return "".join(chars), offsets


def matches(text, quote):
    start = text.find(quote)
    while start >= 0:
        yield start, start + len(quote)
        start = text.find(quote, start + 1)


def resolve_quote(pointer, documents, used):
    quote = pointer.get("quote")
    doc_id = pointer.get("doc_id")
    text = documents.get(doc_id) if isinstance(doc_id, str) else None
    if (set(pointer) != {"doc_id", "quote"} or not isinstance(quote, str)
            or not 1 <= len(quote) <= 60 or not quote.strip() or text is None):
        return None
    spans = list(matches(text, quote))
    if not spans:
        folded, offsets = normalized(text)
        needle, _ = normalized(quote)
        if needle:
            spans = [(offsets[a], offsets[b - 1] + 1) for a, b in matches(folded, needle)]
    if not spans:
        return None
    doc_id = pointer["doc_id"]
    start, end = next((s for s in spans if (doc_id, *s) not in used), spans[0])
    used.add((doc_id, start, end))
    return dict(doc_id=doc_id, span=[start, end],
                quote_hash=hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:12])


def numbered_text(text):
    """Display-only labels; canonical text and offsets stay unchanged."""
    return "\n".join(f"L{i}: {line}" for i, line in enumerate(text.splitlines(), 1))


def resolve_lines(pointer, documents):
    doc_id, bounds = pointer.get("doc_id"), pointer.get("lines")
    text = documents.get(doc_id) if isinstance(doc_id, str) else None
    if (set(pointer) != {"doc_id", "lines"} or text is None
            or not isinstance(bounds, list) or len(bounds) != 2
            or not all(type(n) is int for n in bounds)):
        return None
    lines = text.splitlines(keepends=True)
    first, last = bounds
    if not 1 <= first <= last <= len(lines) or last - first >= 6:
        return None
    start = sum(map(len, lines[:first - 1]))
    end = sum(map(len, lines[:last]))
    return dict(doc_id=doc_id, span=[start, end],
                quote_hash=hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:12])


def normalize_output(output, task_input, store):
    """Mutate evidence only; diagnostics never contain source quotations."""
    documents = {}
    for doc in task_input.get("documents", []):
        row = store.db.execute("SELECT text FROM documents WHERE id=?", (doc["id"],)).fetchone()
        if row is not None:
            documents[doc["id"]] = row[0]
    issues = []

    def walk(value, path="$"):
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, dict):
            used = set()
            for key in ("evidence", "counter_evidence"):
                for pointer in value.get(key, []) if isinstance(value.get(key), list) else []:
                    if isinstance(pointer, dict) and isinstance(pointer.get("span"), list):
                        span = pointer["span"]
                        if len(span) == 2 and all(type(n) is int for n in span):
                            if isinstance(pointer.get("doc_id"), str):
                                used.add((pointer["doc_id"], *span))
            for key, items in value.items():
                if key in ("evidence", "counter_evidence") and isinstance(items, list):
                    kept = []
                    for index, pointer in enumerate(items):
                        if isinstance(pointer, dict) and "lines" in pointer:
                            pointer = resolve_lines(pointer, documents)
                            if pointer is None:
                                issues.append(f"{path}.{key}[{index}]: invalid line range removed")
                                continue
                        if isinstance(pointer, dict) and "quote" in pointer:
                            pointer = resolve_quote(pointer, documents, used)
                            if pointer is None:
                                issues.append(f"{path}.{key}[{index}]: unresolved quote removed")
                                continue
                        if isinstance(pointer, dict) and "span" in pointer:
                            doc_id, span = pointer.get("doc_id"), pointer["span"]
                            text = documents.get(doc_id) if isinstance(doc_id, str) else None
                            if (text is None or not isinstance(span, list) or len(span) != 2
                                    or not all(type(n) is int for n in span)
                                    or not 0 <= span[0] < span[1] <= len(text)):
                                issues.append(f"{path}.{key}[{index}]: invalid source span removed")
                                continue
                        kept.append(pointer)
                    value[key] = kept
                else:
                    walk(items, f"{path}.{key}")
    walk(output)
    return issues
