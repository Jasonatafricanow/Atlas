"""Conservative evidence-breadth calibration; raw agent scores remain inspectable."""
from datetime import datetime


def calibrate(record, documents):
    if "confidence" not in record:
        return record
    raw = record.get("raw_confidence", record["confidence"])
    ids = {e["doc_id"] for e in record.get("evidence", [])}
    dates = []
    for doc_id in ids:
        try:
            dates.append(datetime.fromisoformat(documents[doc_id]["ts"]).date())
        except (ValueError, TypeError, KeyError):
            pass
    cap = 0 if not ids else 0.55 if len(ids) == 1 else 0.7 if len(ids) == 2 else 0.8
    if len(ids) >= 3 and len(dates) >= 3 and (max(dates) - min(dates)).days >= 7:
        cap = 0.9
    counter = {e["doc_id"] for e in record.get("counter_evidence", [])}
    record.update(raw_confidence=raw, confidence=round(min(raw, cap) / (1 + len(counter)), 6))
    return record
