"""Package stored source records and validate referenced timeline judgments."""
from ..chat import statement_attribution, time_key


def source_records(graph, store):
    from .merge import records
    documents = {d.id: d.to_dict() for d in store.all()}
    statements = records(graph, "statements")
    props = []
    for prop in records(graph, "propositions"):
        if prop.get("status") not in ("proposed", "confirmed") or prop.get("suppressed_by"):
            continue
        props.append(dict(prop, statement_id=prop["prop_id"], about=prop["subject_node_ids"],
                          **statement_attribution(documents, prop["evidence"])))
    return documents, statements, props


def make_lines(queue, graph):
    from .merge import records
    documents, statements, props = source_records(graph, queue.store)
    # Bounded snapshots; the lens coalesces shared topics across batches.
    combined = [("statements", s) for s in statements] + [("propositions", p) for p in props]
    combined.sort(key=lambda pair: (time_key(pair[1].get("ts")), pair[1]["statement_id"]))
    batches, batch, size = [], [], 0
    for pair in combined:
        if batch and (len(batch) >= 200 or size + len(pair[1]["text"]) > queue.batch_chars):
            batches.append(batch)
            batch, size = [], 0
        batch.append(pair)
        size += len(pair[1]["text"])
    if batch:
        batches.append(batch)
    made = []
    for batch in batches:
        ids = {e["doc_id"] for _, r in batch for e in r.get("evidence", []) + r.get("counter_evidence", [])}
        payload = {"documents": [documents[i] for i in sorted(ids)],
                   "statements": [r for kind, r in batch if kind == "statements"],
                   "propositions": [r for kind, r in batch if kind == "propositions"],
                   "existing_lines": records(graph, "lines")}
        made.extend(queue.make("cluster_lens", payload))
    return made


def validate_lines(output, payload):
    sources = {s["statement_id"]: s for s in payload["statements"] + payload["propositions"]}
    errors = []
    seen = set()
    for line in output["lines"]:
        if line["line_id"] in seen:
            errors.append("duplicate line identity")
        seen.add(line["line_id"])
        ids = [p["statement_id"] for p in line["timeline"]]
        if len(set(ids)) != len(ids) or any(i not in sources for i in ids):
            errors.append("timeline needs unique input statement_ids")
            continue
        expected = sorted(ids, key=lambda i: (time_key(sources[i].get("ts")), i))
        if ids != expected:
            errors.append("timeline must be in source time order (unknown first)")
        if not any(line["topic"] in sources[i]["about"] for i in ids):
            # Repair instead of rejecting: anchor the line on its most frequent about node.
            counts = {}
            for i in ids:
                for n in sources[i]["about"]:
                    counts[n] = counts.get(n, 0) + 1
            if counts:
                line.setdefault("topic_label", line["topic"])
                line["topic"] = max(sorted(counts), key=counts.get)
        # Grouping is a semantic judgment by the agent; statements need not share an
        # about node (e.g. two different stocks discussed under one trading rule).
        for index, point in enumerate(line["timeline"]):
            source = sources[point["statement_id"]]
            if (index == 0) != (point["shift"] == "first"):
                errors.append("only the first point has shift first")
            support = point["outcome_statement_ids"]
            if point["outcome"] == "unknown":
                if support:
                    errors.append("unknown outcome must not claim supporting statements")
                continue
            if not support or not point["outcome_reason"].strip():
                errors.append("known outcome requires later support and an explanation")
            for identifier in support:
                later = sources.get(identifier)
                if (not later or not time_key(source.get("ts"))[0] or not time_key(later.get("ts"))[0]
                    or time_key(later["ts"]) <= time_key(source["ts"])
                    or not set(source["about"]).intersection(later["about"])):
                    errors.append("outcome support must be a later related input statement")
    return errors


def merge_lines(graph, payload, output, task_id):
    from .merge import identity
    sources = {s["statement_id"]: s for s in payload["statements"] + payload["propositions"]}
    for line in output["lines"]:
        record = dict(line, line_id=identity("line", task_id, line["line_id"]),
                      source_line_id=line["line_id"], topic_node_id=line["topic"],
                      about=sorted({n for p in line["timeline"] for n in sources[p["statement_id"]]["about"]}))
        record["sensitive"] = any(sources[p["statement_id"]].get("sensitive", False) or any(
            sources[i].get("sensitive", False) for i in p["outcome_statement_ids"]) for p in line["timeline"])
        graph.put("lines", record)
