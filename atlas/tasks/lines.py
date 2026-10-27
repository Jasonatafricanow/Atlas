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
        if batch and (len(batch) >= queue.lines_batch or size + len(pair[1]["text"]) > queue.batch_chars):
            batches.append(batch)
            batch, size = [], 0
        batch.append(pair)
        size += len(pair[1]["text"])
    if batch:
        batches.append(batch)
    nodes = {n["node_id"]: n["name"] for n in records(graph, "nodes")}
    made = []
    for batch in batches:
        ids = {e["doc_id"] for _, r in batch for e in r.get("evidence", []) + r.get("counter_evidence", [])}
        payload = {"documents": [{"id": i} for i in sorted(ids)], "statements": [], "propositions": [],
                   "existing_lines": [{k: line[k] for k in ("line_id", "title", "topic_node_id")}
                                      for line in records(graph, "lines")]}
        for index, (kind, record) in enumerate(batch, 1):
            compact = {key: record.get(key) for key in ("statement_id", "ts", "speaker", "text", "about")}
            compact.update(ref=f"s{index}", about_names={n: nodes.get(n, n) for n in record["about"]},
                           sensitive=record.get("sensitive", False))
            payload[kind].append(compact)
        made.extend(queue.make("cluster_lens", payload))
    return made


def repair_lines(output, payload):
    """Normalize model references and repair points without inventing source facts."""
    if not isinstance(output, dict) or not isinstance(output.get("lines"), list):
        return []
    sources = {s["statement_id"]: s for s in payload["statements"] + payload["propositions"]}
    refs = {s["ref"]: i for i, s in sources.items() if s.get("ref")}
    def resolve(value):
        return value if isinstance(value, str) and value in sources else refs.get(value) if isinstance(value, str) else None
    diagnostics = []
    assigned = set()
    for number, line in enumerate(output["lines"]):
        if not isinstance(line, dict) or not isinstance(line.get("timeline"), list):
            continue
        points = []
        for index, point in enumerate(line["timeline"]):
            identifier = resolve(point.get("statement_id", point.get("ref"))) if isinstance(point, dict) else None
            if not identifier or identifier in assigned:
                diagnostics.append(f"$.lines[{number}].timeline[{index}]: unknown or duplicate reference dropped")
                continue
            point.pop("ref", None)
            point["statement_id"] = identifier
            points.append(point)
            assigned.add(identifier)
        points.sort(key=lambda p: (time_key(sources[p["statement_id"]].get("ts")), p["statement_id"]))
        line["timeline"] = points
        ids = {p["statement_id"] for p in points}
        for index, point in enumerate(points):
            point["shift_source"] = "repaired" if point.get("shift_source") == "repaired" else "model"
            if index == 0:
                if point.get("shift") != "first":
                    point["shift_source"] = "repaired"
                point["shift"] = "first"
            elif point.get("shift") not in ("same", "strengthen", "weaken", "reverse", "new_angle", "unclear"):
                point["shift"] = "unclear"
                point["shift_source"] = "repaired"
                diagnostics.append(f"$.lines[{number}].timeline[{index}]: shift repaired to unclear")
            source = sources[point["statement_id"]]
            support = point.get("outcome_statement_ids", [])
            support = [resolve(i) for i in support] if isinstance(support, list) else [None]
            valid = (point.get("outcome") in ("confirmed", "refuted", "mixed")
                     and isinstance(point.get("outcome_reason"), str) and point["outcome_reason"].strip()
                     and support and all(i in ids and time_key(source.get("ts"))[0]
                         and time_key(sources[i].get("ts")) > time_key(source.get("ts"))
                         and set(source["about"]) & set(sources[i]["about"]) for i in support))
            if valid:
                point["outcome_statement_ids"] = list(dict.fromkeys(support))
            else:
                point.update(outcome="unknown", outcome_statement_ids=[], outcome_reason="")
        if points and not any(line.get("topic") in sources[i]["about"] for i in ids):
            counts = {}
            for i in ids:
                for node in sources[i]["about"]:
                    counts[node] = counts.get(node, 0) + 1
            if counts:
                line["topic"] = max(sorted(counts), key=counts.get)
    return diagnostics


def validate_lines(output, payload):
    repair_lines(output, payload)
    return ["line needs at least one valid point" for line in output["lines"] if not line["timeline"]]


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
