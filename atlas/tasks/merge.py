"""Atomic, source-checked merges of accepted graph tasks."""
from dataclasses import asdict

from ..graph.models import Node, Edge
from .queue import digest, read_json
from ..chat import statement_attribution
from ..graph.confidence import calibrate


def identity(prefix, *parts):
    return prefix + ":" + digest(parts)[:24]


def records(graph, table):
    return [graph.get(table, row[0]) for row in graph.db.execute(f"SELECT id FROM {table}")]


def merge(queue, graph, identifier):
    from ..profile import sync_corrections
    with queue.locked():
        sync_corrections(graph, queue.root.parent)
        with graph.transaction():
            result = _merge(queue, graph, identifier)
            sync_corrections(graph, queue.root.parent)
            return result


def _merge(queue, graph, identifier):
    with graph.transaction():
        state, path = queue.locate(identifier)
        if state != "accepted":
            raise ValueError("only accepted tasks can be merged")
        errors = queue._validate(path)
        if errors:
            raise ValueError("; ".join(errors))
        task, payload, output = [read_json(path / name) for name in
                                 ("task.json", "input.json", "output.json")]
        if task["kind"] not in ("extract_entities", "resolve_entities", "gen_propositions", "cluster_lens"):
            raise ValueError("unsupported merge kind")
        run_id = identity("run", identifier, task["input_hash"])
        previous = graph.get("task_runs", run_id)
        if previous:
            if previous["output_hash"] != digest(output):
                raise ValueError("already merged task has changed output")
            return {"task_id": identifier, "state": "noop", "node_ids": previous["node_ids"]}
        output = read_json(path / "accepted.json")
        mapping = {}
        deduplicated = 0
        documents = {d["id"]: d for d in payload["documents"]}

        def put_entity(entity, target=None):
            node_id = target or identity("node", identifier, task["input_hash"], entity["tmp_id"])
            node = graph.get("nodes", node_id)
            if target and (not node or node.get("status") == "superseded" or node["type"] != entity["type"]):
                raise ValueError("resolution target must be an active node of the same type")
            node = node or asdict(Node(node_id, entity["type"], entity["name"], observed_at=task["created_at"]))
            for evidence in entity["evidence"]:
                if evidence not in node["evidence"]:
                    node["evidence"].append(evidence)
            node["sensitive"] = node.get("sensitive", False) or any(
                documents[e["doc_id"]].get("meta", {}).get("sensitive", False) for e in entity["evidence"])
            graph.put("nodes", node)
            for name in dict.fromkeys([entity["name"], *entity["aliases"]]):
                graph.put("aliases", {"alias_id": identity("alias", node_id, name), "node_id": node_id, "name": name})
            for evidence in entity["evidence"]:
                graph.put("evidence", dict(evidence, evidence_id=identity("evidence", evidence)))
            mapping[entity["tmp_id"]] = node_id
            return node_id

        if task["kind"] == "extract_entities":
            for entity in output["entities"]:
                put_entity(entity)
            for index, relation in enumerate(output["relations"]):
                edge = asdict(Edge(identity("edge", identifier, task["input_hash"], index),
                                   mapping[relation["src"]], mapping[relation["dst"]], relation["type"],
                                   evidence=relation["evidence"], valid_from=relation.get("valid_from"),
                                   valid_to=relation.get("valid_to"), observed_at=task["created_at"]))
                edge["sensitive"] = any(graph.get("nodes", edge[k])["sensitive"] for k in ("src", "dst")) or any(
                    documents[e["doc_id"]].get("meta", {}).get("sensitive", False) for e in edge["evidence"])
                if "confidence" in relation:
                    edge["confidence"] = relation["confidence"]
                    calibrate(edge, documents)
                if relation.get("supersedes"):
                    old = graph.get("edges", relation["supersedes"])
                    if not old or old["type"] != edge["type"]:
                        raise ValueError("supersedes must reference an existing relation of the same type")
                    graph.supersede("edges", old["edge_id"], edge, edge["valid_from"])
                else:
                    graph.put("edges", edge)
                for evidence in edge["evidence"]:
                    graph.put("evidence", dict(evidence, evidence_id=identity("evidence", evidence)))
            for statement in output["statements"]:
                record = {k: v for k, v in statement.items() if k != "tmp_id"}
                record.update(statement_id=identity("statement", identifier, task["input_hash"], statement["tmp_id"]),
                              about=[mapping[i] for i in statement["about"]],
                              **statement_attribution(documents, statement["evidence"]))
                record["sensitive"] = any(graph.get("nodes", i).get("sensitive", False) for i in record["about"]) or any(
                    documents[e["doc_id"]].get("meta", {}).get("sensitive", False) for e in record["evidence"])
                graph.put("statements", calibrate(record, documents))
                for evidence in record["evidence"]:
                    graph.put("evidence", dict(evidence, evidence_id=identity("evidence", evidence)))
        elif task["kind"] == "cluster_lens":
            from .lines import merge_lines
            merge_lines(graph, payload, output, identifier)
        elif task["kind"] == "gen_propositions":
            from .propositions import merge_propositions
            deduplicated = merge_propositions(graph, payload, output, task["created_at"])
        else:
            candidates = {c["tmp_id"]: c for c in payload["candidates"]}
            for op in output["ops"]:
                candidate = candidates[op["tmp_id"]]
                source = candidate.get("node_id")
                if source:
                    existing = graph.get("nodes", source)
                    if not existing or existing.get("status") == "superseded" or existing["type"] != candidate["type"]:
                        raise ValueError("candidate node must exist and be active with the same type")
                if op["op"] == "NOOP":
                    if source:
                        mapping[op["tmp_id"]] = source
                    continue
                if op["op"] == "ADD" and source:
                    raise ValueError("ADD requires a candidate without an existing node_id")
                target = put_entity(candidate, op.get("node_id") if op["op"] == "MERGE_INTO" else None)
                if source and source != target:
                    target_node = graph.get("nodes", target)
                    target_node["sensitive"] |= existing.get("sensitive", False)
                    for evidence in existing["evidence"]:
                        if evidence not in target_node["evidence"]:
                            target_node["evidence"].append(evidence)
                    graph.put("nodes", target_node)
                    for alias in records(graph, "aliases"):
                        if alias["node_id"] == source:
                            graph.put("aliases", dict(alias, node_id=target))
                    for edge in records(graph, "edges"):
                        if edge["status"] != "superseded" and source in (edge["src"], edge["dst"]):
                            for key in ("src", "dst"):
                                if edge[key] == source:
                                    edge[key] = target
                            edge["sensitive"] = edge.get("sensitive", False) or graph.get("nodes", target)["sensitive"]
                            graph.put("edges", edge)
                    for statement in records(graph, "statements"):
                        if source in statement["about"]:
                            statement["about"] = list(dict.fromkeys(target if i == source else i for i in statement["about"]))
                            statement["sensitive"] |= target_node.get("sensitive", False)
                            graph.put("statements", statement)
                    for line in records(graph, "lines"):
                        if source in line.get("about", []):
                            line["about"] = list(dict.fromkeys(target if i == source else i for i in line["about"]))
                            if line["topic_node_id"] == source:
                                line.update(topic_node_id=target, topic=target)
                            graph.put("lines", line)
                    existing.update(status="superseded", superseded_by=target, valid_to=task["created_at"])
                    graph._write("nodes", existing, "SUPERSEDE")
        graph.put("task_runs", {"task_id": run_id, "source_task_id": identifier,
                               "input_hash": task["input_hash"], "output_hash": digest(read_json(path / "output.json")),
                               "node_ids": mapping, "deduplicated": deduplicated})
        return {"task_id": identifier, "state": "merged", "node_ids": mapping, "deduplicated": deduplicated}
