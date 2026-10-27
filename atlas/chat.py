"""Attribute evidence to a single source line, without guessing speakers or years."""
import re
from datetime import datetime, timezone


LINE = re.compile(r"^\[(?P<date>(?:\d{4}-)?\d{2}-\d{2}) (?P<time>\d{2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[^:：]+)[:：]")


def attribution(document, evidence):
    text = document["text"]
    start, end = evidence["span"]
    offset = 0
    matches = []
    for line in text.splitlines(keepends=True):
        if start < offset + len(line) and end > offset:
            matches.append(LINE.match(line))
        offset += len(line)
    fallback = {"speaker": document.get("author"), "ts": document.get("ts") or None}
    if len(matches) != 1 or matches[0] is None:
        # A multi-line quotation cannot identify one speaker/time safely.
        return fallback if not any(matches) else {"speaker": None, "ts": document.get("ts") or None}
    match = matches[0]
    result = dict(fallback, speaker=match["speaker"].strip())
    date = match["date"]
    if len(date) == 5:
        # Resolve a missing year only within the document's known time interval.
        try:
            first = datetime.fromisoformat(document["ts"])
            last = datetime.fromisoformat(document.get("meta", {}).get("ts_end") or document["ts"])
            candidates = [f"{year}-{date}" for year in range(first.year, last.year + 1)]
            candidates = [d for d in candidates if first.date() <= datetime.fromisoformat(d).date() <= last.date()]
            if len(candidates) != 1:
                return result
            date = candidates[0]
        except (ValueError, TypeError, KeyError):
            return result
    try:
        result["ts"] = datetime.fromisoformat(date + "T" + match["time"]).isoformat()
    except ValueError:
        pass
    return result


def statement_attribution(documents, evidence):
    values = [attribution(documents[e["doc_id"]], e) for e in evidence]
    return {key: values[0][key] if all(v[key] == values[0][key] for v in values) else None
            for key in ("speaker", "ts")}


def time_key(value):
    """Stable ordering key; explicit offsets compare in UTC, unknown sorts first.

    Naive timestamps retain their source wall-clock ordering. This does not add
    a timezone to stored source data or prove that naive/aware clocks agree.
    """
    try:
        moment = datetime.fromisoformat(value)
        moment = moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)
        return (1, moment.toordinal() * 86400 + moment.hour * 3600 + moment.minute * 60 + moment.second + moment.microsecond / 1000000)
    except (ValueError, TypeError, OverflowError):
        return (0, 0)
