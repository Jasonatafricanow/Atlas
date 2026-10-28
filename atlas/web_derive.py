"""Pure UI aggregates of already-visible records; no store writes or producers."""
import re
from pathlib import Path

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
    known = counts["supported"] + counts["contradicted"]
    reversals = sum(active(p["source"]) and any(a.get("shift") == "reverse" for a in p["annotations"])
                    for p in points[1:])
    return {"accuracy": counts["supported"] / known if known >= 3 else None,
            "known_count": known, "point_count": len(points),
            "accuracy_basis": f"已知 {known} / 共 {len(points)}",
            "reversal_count": reversals,
            "stability": 1 - reversals / (len(points) - 1) if len(points) >= 3 else None,
            "current_stance": stance or None,
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
            **({"accuracy": result["accuracy"], "accuracy_basis": result["accuracy_basis"],
                "pending_items": derive_pending(lines, propositions)} if lines or propositions else {}),
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


def derive_pending(lines, propositions):
    """Lexicographic priority: low known confidence, many lines, latest source time.

    Missing confidence and dates sort last within their tier. observed_at is only
    a fallback ranking timestamp, explicitly identified, never a new fact date.
    """
    template = (Path(__file__).parent / "templates" / "pending_question.txt").read_text(encoding="utf-8").strip()
    items = []
    for prop in propositions:
        if not active(prop) or prop.get("status") != "proposed":
            continue
        subjects = set(prop.get("subject_node_ids", []))
        affected = {line["topic_node_id"] for line in lines
                    if line["topic_node_id"] in subjects or any(
                        p["statement_id"] == prop["prop_id"] or subjects.intersection(
                            p["source"].get("about", p["source"].get("subject_node_ids", [])))
                        for p in line["timeline"])}
        field = next((f for f in ("ts", "observed_at") if time_key(prop.get(f))[0]), None)
        items.append({"prop_id": prop["prop_id"], "confidence": prop.get("confidence"),
                      "affected_line_ids": sorted(affected), "affected_line_count": len(affected),
                      "recency": prop.get(field) if field else None, "recency_field": field,
                      "question": template.format(text=prop.get("text", ""))})
    # Stable sorts avoid negating heterogeneous timestamp keys and keep unknowns last.
    items.sort(key=lambda p: p["prop_id"])
    items.sort(key=lambda p: time_key(p["recency"]), reverse=True)
    items.sort(key=lambda p: -p["affected_line_count"])
    items.sort(key=lambda p: (p["confidence"] is None, p["confidence"] or 0))
    return [dict(p, priority=i + 1) for i, p in enumerate(items)]
