"""Run M2 CLI acceptance using only shipped synthetic fixtures and a fresh temp dir."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.merge import records


def main():
    with tempfile.TemporaryDirectory(prefix="atlas-m2-synthetic-") as directory:
        env = dict(os.environ, ATLAS_DATA_DIR=directory, ATLAS_OUT_DIR=directory)

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "atlas", *args], cwd=ROOT,
                                    env=env, text=True, capture_output=True, check=True)
            print("atlas " + " ".join(args[:3]) + " -> " + result.stdout.strip())
            return json.loads(result.stdout)

        def submit(task, output):
            path = Path(directory) / "synthetic-output.json"
            path.write_text(json.dumps(output), encoding="utf-8")
            assert cli("tasks", "submit", task, "--file", str(path))["state"] == "accepted"

        graph = GraphStore(directory)
        store = Store(directory)
        try:
            documents = [Document(**json.loads(line)) for line in
                         (ROOT / "examples/synthetic_corpus/m2_relations.jsonl").read_text(encoding="utf-8").splitlines()]
            old_edge = None
            for index, doc in enumerate(documents):
                store.upsert([doc])
                task = cli("tasks", "make", "--kind", "extract_entities")[0]
                evidence = [{"doc_id": doc.id, "span": [0, len(doc.text)],
                             "quote_hash": hashlib.sha256(doc.text.encode()).hexdigest()[:12]}]
                entities = [
                    {"tmp_id": "probe", "type": "concept", "name": "Synthetic probe", "aliases": ["Demo probe"], "evidence": evidence},
                    {"tmp_id": "field", "type": "place", "name": "Fictional West Field" if index else "Fictional East Field",
                     "aliases": [], "evidence": evidence}]
                relation = {"src": "probe", "dst": "field", "type": "located_in", "valid_from": doc.ts, "evidence": evidence}
                if old_edge:
                    relation["supersedes"] = old_edge
                submit(task, {"entities": entities, "relations": [relation], "statements": []})
                merged = cli("tasks", "merge", task)
                before = graph.stats()
                assert cli("tasks", "merge", task)["state"] == "noop"
                assert before == graph.stats(), "repeat merge changed row counts"
                if index == 0:
                    old_edge = records(graph, "edges")[0]["edge_id"]
                    first_probe = merged["node_ids"]["probe"]
                    stats = cli("graph", "stats")
                    assert stats["nodes"] == 2 and stats["edges"] == 1
                else:
                    old = graph.get("edges", old_edge)
                    assert old["status"] == "superseded" and old["valid_to"] == doc.ts
                    assert graph.get("edges", old["superseded_by"])["dst"] == merged["node_ids"]["field"]
            candidate = dict(entities[0], node_id=merged["node_ids"]["probe"])
            payload = {"documents": [d.to_dict() for d in documents], "candidates": [candidate],
                       "nodes": [{key: n[key] for key in ("node_id", "type", "name")} for n in records(graph, "nodes")]}
            path = Path(directory) / "resolution.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            task = cli("tasks", "make", "--kind", "resolve_entities", "--input", str(path))[0]
            submit(task, {"ops": [{"op": "MERGE_INTO", "tmp_id": "probe", "node_id": first_probe,
                                   "reason": "Same synthetic probe across the location change"}]})
            cli("tasks", "merge", task)
            before = graph.stats()
            assert cli("tasks", "merge", task)["state"] == "noop"
            assert before == graph.stats()
            active = [e for e in records(graph, "edges") if e["status"] == "confirmed"]
            assert len(active) == 1 and active[0]["src"] == first_probe
            cli("graph", "stats")
            print("PASS: idempotency (all tables), node/edge counts, resolution, superseded + valid_to")
        finally:
            graph.close()
            store.db.close()


if __name__ == "__main__":
    main()
