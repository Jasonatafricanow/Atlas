"""Pure UI aggregates of already-visible records; no store writes or producers."""
import re

from .chat import time_key


SHIFT_LABELS = {"strengthen", "weaken", "reverse", "new_angle", "refine"}
OUTCOMES = {"confirmed": "supported", "supported": "supported",
            "refuted": "contradicted", "contradicted": "contradicted"}


def active(source):
    return not source.get("suppressed_by") and source.get("status") not in ("rejected", "superseded")


def point_outcome(point):
    """Count each source once; mixed, missing or conflicting labels stay unknown."""
    labels = {OUTCOMES.get(a.get("outcome"), "unknown") for a in point["annotations"]}
    return labels.pop() if active(point["source"]) and len(labels) == 1 else "unknown"


def shifted(point):
    # Count existing annotations, never compare free-text stances or batch starts.
    return active(point["source"]) and any(a.get("shift") in SHIFT_LABELS for a in point["annotations"])


def derive_line(points):
    dated = sorted((p for p in points if time_key(p["source"].get("ts"))[0]),
                   key=lambda p: time_key(p["source"]["ts"]))
    latest = [p for p in dated if time_key(p["source"]["ts"]) == time_key(dated[-1]["source"]["ts"])] if dated else []
    stances = {p["source"].get("stance") if active(p["source"]) else None for p in latest}
    stance = next(iter(stances)) if len(stances) == 1 else None
    counts = {key: 0 for key in ("supported", "contradicted", "unknown")}
    for point in points:
        counts[point_outcome(point)] += 1
    return {"current_stance": stance or None,
            "stance_source_ids": [p["statement_id"] for p in latest],
            "outcome_counts": counts,
            "shift_count": sum(shifted(p) for p in points),
            "time_span": {"first": dated[0]["source"]["ts"], "last": dated[-1]["source"]["ts"]} if dated else None}


def derive_home(lines, propositions):
    # A source may occur under more than one topic. Count it once on the home page.
    points = {}
    for line in lines:
        for point in line["timeline"]:
            item = points.setdefault(point["statement_id"], dict(point, annotations=[]))
            item["annotations"].extend(point["annotations"])
    result = derive_line(list(points.values()))
    return {"point_count": len(points), "line_count": len(lines),
            "outcome_counts": result["outcome_counts"], "shift_count": result["shift_count"],
            "confirmed_count": sum(active(p) and p.get("status") == "confirmed" for p in propositions),
            "pending_count": sum(active(p) and p.get("status") == "proposed" for p in propositions)}


def session_name(channel, meta):
    """Only explicit display metadata; never source paths, filenames or IDs."""
    meta = meta if isinstance(meta, dict) else {}
    for value in (channel, *(meta.get(k) for k in ("session_display_name", "display_name", "session_name", "title"))):
        if not isinstance(value, str):
            continue
        name = value.strip()
        if (name and not re.search(r"[/\\\x00-\x1f]|^[A-Za-z]:|^~", name)
                and not re.search(r"\.(?:jsonl?|txt|md|sqlite|db|html?|csv|log|zip)$", name, re.I)):
            return name
    return "未命名会话"
