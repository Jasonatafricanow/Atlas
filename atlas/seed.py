"""Reference-only legacy imports, physically separate from the built graph."""
import hashlib
import json
import unicodedata

# Built relations are open verb-like strings; these are the generic canonical names.
RELATIONS = {"related_to", "knows", "located_in", "part_of", "works_on", "supports", "opposes", "owns", "uses"}
SYNONYMS = {"related": "related_to", "located at": "located_in", "member of": "part_of",
            "work on": "works_on", "support": "supports", "oppose": "opposes"}


def normalize(value):
    return "_".join("".join(c if c.isalnum() else " " for c in
                           unicodedata.normalize("NFKC", value).strip().lower()).split())


def reference_rows(graph):
    return {kind: [json.loads(r[0]) for r in graph.db.execute(
        f"SELECT data FROM legacy_{kind} ORDER BY id")] for kind in ("nodes", "edges")}


def import_seed(graph, payload, synonyms=None):
    if not isinstance(payload, dict) or not all(isinstance(payload.get(k), list) for k in ("nodes", "edges")):
        raise ValueError("seed requires nodes and edges arrays")
    mapping = {normalize(k): v for k, v in SYNONYMS.items()}
    for key, value in (synonyms or {}).items():
        if not isinstance(key, str) or value not in RELATIONS:
            raise ValueError("seed synonym targets must be canonical relations")
        mapping[normalize(key)] = value
    nodes, edges, ids = [], [], set()
    for node in payload["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"] or node["id"] in ids:
            raise ValueError("seed nodes require unique nonempty string ids")
        if any(not isinstance(node[k], str) for k in ("name", "type") if k in node):
            raise ValueError("seed node name/type must be strings")
        ids.add(node["id"])
        nodes.append(dict(node, source="legacy", status="reference"))
    mapped = unmapped = 0
    originals = set()
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or any(not isinstance(edge.get(k), str) for k in ("s", "t", "r")):
            raise ValueError("seed edges require string s, t, r")
        if edge["s"] not in ids or edge["t"] not in ids:
            raise ValueError("seed edge endpoint missing from nodes")
        if "date" in edge and edge["date"] is not None and not isinstance(edge["date"], str):
            raise ValueError("seed date must be a string or null")
        original = edge["r"]
        originals.add(original)
        relation = normalize(original)
        relation = mapping.get(relation, relation)
        known = relation in RELATIONS
        mapped += int(known)
        unmapped += int(not known)
        record = dict(s=edge["s"], t=edge["t"], r=relation if known else "related_to",
                      source="legacy", status="reference")
        if "date" in edge:
            record["date"] = edge["date"]
        if not known:
            record["legacy_relation"] = original
        identity = hashlib.sha256(json.dumps(edge, sort_keys=True).encode()).hexdigest()
        edges.append((identity, record))
    with graph.transaction():
        for kind, rows in (("nodes", [(n["id"], n) for n in nodes]), ("edges", edges)):
            graph.db.executemany(f"INSERT INTO legacy_{kind} VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                                 [(i, json.dumps(r, ensure_ascii=False)) for i, r in rows])
    return dict(nodes=len(nodes), edges=len(edges), mapped=mapped, unmapped=unmapped,
                distinct_original_relations=len(originals))
