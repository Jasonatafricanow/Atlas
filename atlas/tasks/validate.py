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
    errors = check_schema(output, schema_for(kind + ".output"))
    if errors:
        return errors
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
