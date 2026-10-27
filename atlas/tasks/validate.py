"""Schema checks plus source-backed evidence checks, without dependencies."""
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def schema_for(name):
    return json.loads((SCHEMAS / (name + ".schema.json")).read_text(encoding="utf-8"))


def check_schema(value, schema, path="$", errors=None):
    """Validate the JSON Schema subset used by the shipped contracts."""
    errors = [] if errors is None else errors
    if "oneOf" in schema and sum(not check_schema(value, branch) for branch in schema["oneOf"]) != 1:
        errors.append(f"{path}: expected exactly one evidence form")
        return errors
    types = {"object": lambda x: isinstance(x, dict),
             "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str),
             "integer": lambda x: type(x) is int,
             "number": lambda x: type(x) in (int, float) and math.isfinite(x),
             "boolean": lambda x: type(x) is bool, "null": lambda x: x is None}
    expected = schema.get("type")
    if expected and not any(types[t](value) for t in ([expected] if isinstance(expected, str) else expected)):
        errors.append(f"{path}: invalid type, expected {expected}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value outside enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                check_schema(item, props[key], f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unexpected property")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(f"{path}: invalid item count")
        for index, item in enumerate(value):
            check_schema(item, schema.get("items", {}), f"{path}[{index}]", errors)
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            errors.append(f"{path}: invalid string length")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: pattern mismatch")
    elif type(value) in (int, float):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            errors.append(f"{path}: number outside range")
    return errors


def validate_output(kind, output, task_input, store):
    from .evidence import normalize_output
    quote_errors = normalize_output(output, task_input, store)
    if kind == "cluster_lens":
        from .lines import repair_lines
        repair_lines(output, task_input)
    errors = check_schema(output, schema_for(kind + ".output"))
    if errors:
        return errors
    errors.extend(quote_errors)
    allowed = {d["id"] for d in task_input.get("documents", [])}

    def walk(value, path="$", evidence=False):
        if isinstance(value, dict):
            if evidence:
                doc_id = value["doc_id"]
                row = store.db.execute("SELECT text FROM documents WHERE id=?", (doc_id,)).fetchone()
                start, end = value["span"]
                if doc_id not in allowed or row is None:
                    errors.append(f"{path}.doc_id: missing or outside task input")
                elif not 0 <= start < end <= len(row[0]):
                    errors.append(f"{path}.span: outside document bounds")
                elif hashlib.sha256(row[0][start:end].encode("utf-8")).hexdigest()[:12] != value["quote_hash"]:
                    errors.append(f"{path}.quote_hash: mismatch")
            else:
                for key, item in value.items():
                    walk(item, f"{path}.{key}", key in ("evidence", "counter_evidence"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]", evidence)
    walk(output)
    if kind == "cluster_lens":
        from .lines import validate_lines
        walk(task_input["statements"])
        walk(task_input["propositions"])
        errors += validate_lines(output, task_input)
    if kind == "gen_propositions":
        nodes = {n["node_id"] for n in task_input["subgraph"].get("nodes", [])}
        existing = {p["prop_id"]: p for p in task_input["propositions"]}
        seen = set()
        for operation in output["ops"]:
            prop = operation["prop"]
            if prop["prop_id"] in seen:
                errors.append("$.ops: duplicate proposition identity")
            seen.add(prop["prop_id"])
            if task_input["node_id"] not in prop["subject_node_ids"] or not set(prop["subject_node_ids"]) <= nodes:
                errors.append("$.ops.prop.subject_node_ids: outside subgraph")
            support = {json.dumps(e, sort_keys=True) for e in prop["evidence"]}
            counter = {json.dumps(e, sort_keys=True) for e in prop["counter_evidence"]}
            if len(support) < 2 or support & counter:
                errors.append("$.ops.prop.evidence: two distinct supports, disjoint from counter_evidence required")
            old = existing.get(operation.get("supersedes", prop["prop_id"]))
            if old and any(e not in prop["counter_evidence"] for e in old.get("counter_evidence", [])):
                errors.append("$.ops.prop.counter_evidence: existing counter evidence must be retained")
            if operation["op"] == "SUPERSEDE":
                if not operation.get("supersedes") or not prop.get("valid_from"):
                    errors.append("$.ops: SUPERSEDE requires supersedes and valid_from")
            elif "supersedes" in operation:
                errors.append("$.ops: supersedes only applies to SUPERSEDE")
            if prop.get("valid_from") and prop.get("valid_to") and prop["valid_to"] < prop["valid_from"]:
                errors.append("$.ops.prop: valid_to precedes valid_from")
            if operation["op"] == "SUPERSEDE" and old and (prop["prop_id"] in existing or (old.get("valid_from") and prop.get("valid_from") and prop["valid_from"] < old["valid_from"])):
                errors.append("$.ops: supersession requires a new identity and a valid transition date")
            if prop["status"] == "superseded" or prop.get("superseded_by"):
                errors.append("$.ops.prop: supersession is managed by the store")
    if kind == "resolve_entities":
        walk(task_input["candidates"])
        candidates = {c["tmp_id"]: c for c in task_input["candidates"]}
        ids = [op["tmp_id"] for op in output["ops"]]
        if len(candidates) != len(task_input["candidates"]) or len(ids) != len(set(ids)) or set(ids) != set(candidates):
            errors.append("$.ops: exactly one operation per unique candidate required")
        nodes = {node["node_id"]: node for node in task_input["nodes"]}
        for op in output["ops"]:
            if op["op"] == "ADD" and candidates.get(op["tmp_id"], {}).get("node_id"):
                errors.append("$.ops: ADD requires a candidate without an existing node_id")
            if op["op"] == "MERGE_INTO":
                node = nodes.get(op.get("node_id"))
                if not node or node["type"] != candidates.get(op["tmp_id"], {}).get("type"):
                    errors.append("$.ops.node_id: existing same-type target required")
            elif "node_id" in op:
                errors.append("$.ops.node_id: only MERGE_INTO accepts a target")
    if kind == "extract_entities":
        ids = [e["tmp_id"] for e in output["entities"]]
        statement_ids = [s["tmp_id"] for s in output["statements"]]
        if len(set(ids + statement_ids)) != len(ids + statement_ids):
            errors.append("$.tmp_id: duplicate identity")
        for relation in output["relations"]:
            if relation["src"] not in ids or relation["dst"] not in ids:
                errors.append("$.relations: unknown entity reference")
        for statement in output["statements"]:
            if any(term.casefold() in statement["text"].casefold() for term in task_input.get("forbidden_terms", [])):
                errors.append("$.statements.text: prohibited absolute wording")
            if not set(statement["about"]) <= set(ids):
                errors.append("$.statements.about: unknown entity reference")
    return errors


def accept_items(kind, output, task_input, store, edges=None):
    """Keep independently valid items; return indexed diagnostics and counts."""
    from .evidence import normalize_output
    quote_errors = normalize_output(output, task_input, store)
    if kind == "cluster_lens":
        from .lines import repair_lines
        quote_errors += repair_lines(output, task_input)
    schema = schema_for(kind + ".output")
    groups = {"extract_entities": ["entities", "relations", "statements"],
              "resolve_entities": ["ops"], "gen_propositions": ["ops"],
              "cluster_lens": ["lines"]}.get(kind)
    if groups is None:
        errors = validate_output(kind, output, task_input, store)
        return output, errors, bool(errors), {"accepted": int(not errors), "dropped": int(bool(errors))}
    # Check the outer shape separately from individual records.
    import copy
    outer = copy.deepcopy(schema)
    for group in groups:
        outer["properties"][group]["items"] = {}
    errors = check_schema(output, outer)
    if errors:
        return {}, errors, True, {"accepted": 0, "dropped": 0}
    kept = {**output, **{group: [] for group in groups}}
    errors = list(quote_errors)
    seen = set()
    for group in groups:
        items = output[group]
        identities = []
        for item in items:
            identities.append(item.get("tmp_id") if isinstance(item, dict) else None)
        for index, item in enumerate(items):
            reasons = check_schema(item, schema["properties"][group]["items"])
            if not reasons and kind == "extract_entities" and group in ("relations", "statements"):
                ids = {entity["tmp_id"] for entity in kept["entities"]}
                names = {}
                for entity in kept["entities"]:
                    for name in [entity["name"], *entity["aliases"]]:
                        names.setdefault(name, set()).add(entity["tmp_id"])
                def reference(value):
                    candidates = names.get(value, set())
                    return value if value in ids or len(candidates) != 1 else next(iter(candidates))
                if group == "relations":
                    item["src"], item["dst"] = reference(item["src"]), reference(item["dst"])
                else:
                    item["about"] = list(dict.fromkeys(reference(value) for value in item["about"]))
            if not reasons:
                probe = {**kept, **{g: [] for g in groups}}
                probe[group] = [item]
                context = task_input
                if kind == "extract_entities":
                    if group != "entities":
                        probe["entities"] = kept["entities"]
                    identity = item.get("tmp_id")
                    if identity and (identity in seen or identities.count(identity) > 1):
                        reasons.append("duplicate identity")
                if kind == "resolve_entities":
                    context = dict(task_input, candidates=[c for c in task_input["candidates"] if c["tmp_id"] == item["tmp_id"]])
                    if identities.count(item["tmp_id"]) > 1:
                        reasons.append("duplicate operation for candidate")
                if kind == "cluster_lens" and item["line_id"] in seen:
                    reasons.append("duplicate line identity")
                if kind == "gen_propositions":
                    identity = item["prop"]["prop_id"]
                    if identity in seen:
                        reasons.append("duplicate proposition identity")
                    existing = {p["prop_id"]: p for p in task_input["propositions"]}
                    old = existing.get(item.get("supersedes", identity))
                    if item["op"] in ("UPDATE", "SUPERSEDE", "NOOP") and not old:
                        reasons.append("operation requires an existing proposition")
                    if item["op"] == "ADD" and old:
                        reasons.append("ADD requires a new proposition identity")
                    if old and old.get("status") == "superseded":
                        reasons.append("superseded records are immutable")
                reasons += validate_output(kind, probe, context, store)
                if group == "relations" and item.get("supersedes"):
                    old = (edges or {}).get(item["supersedes"])
                    if not old or old["type"] != item["type"] or not item.get("valid_from"):
                        reasons.append("supersedes requires an existing same-type edge and valid_from")
                    elif old.get("valid_from") and item["valid_from"] < old["valid_from"]:
                        reasons.append("supersession precedes old valid_from")
                if group == "relations" and item.get("valid_from") and item.get("valid_to") and item["valid_to"] < item["valid_from"]:
                    reasons.append("valid_to precedes valid_from")
            if reasons:
                errors.extend(f"$.{group}[{index}]: {reason}" for reason in reasons)
            else:
                kept[group].append(item)
                identity = item.get("tmp_id") or item.get("line_id") or (item.get("prop") or {}).get("prop_id")
                if identity:
                    seen.add(identity)
    if kind == "resolve_entities":
        supplied = {item.get("tmp_id") for item in output["ops"] if isinstance(item, dict)}
        for index, candidate in enumerate(task_input["candidates"]):
            if candidate["tmp_id"] not in supplied:
                errors.append(f"$.candidates[{index}]: missing operation")
    accepted = sum(len(kept[g]) for g in groups)
    total = sum(len(output[g]) for g in groups)
    if not accepted and not errors:
        errors.append("$: no valid items")
    counts = {"accepted": accepted, "dropped": total - accepted}
    if kind == "cluster_lens":
        counts["shift_repairs"] = sum("shift repaired to unclear" in issue for issue in quote_errors)
        assigned = {p["statement_id"] for line in kept["lines"] for p in line["timeline"]}
        counts["unassigned"] = len({s["statement_id"] for s in task_input["statements"] + task_input["propositions"]} - assigned)
        kept["unassigned_count"] = counts["unassigned"]
    return kept, errors, not accepted, counts
