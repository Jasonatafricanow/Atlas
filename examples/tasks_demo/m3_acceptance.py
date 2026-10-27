"""M3 CLI acceptance: shipped synthetic corpus, isolated temporary data only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from atlas.schema import Document
from atlas.store import Store


def main():
    with tempfile.TemporaryDirectory(prefix="atlas-m3-synthetic-") as directory:
        env = dict(os.environ, ATLAS_DATA_DIR=directory, ATLAS_OUT_DIR=directory)

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "atlas", *args], cwd=ROOT,
                                    env=env, text=True, capture_output=True, check=True)
            print("atlas " + " ".join(args[:3]) + " -> " + result.stdout.strip())
            return json.loads(result.stdout)

        store = Store(directory)
        try:
            docs = [Document(source="synthetic", **json.loads(line)) for line in
                    (ROOT / "examples/synthetic_corpus/reading_notes.jsonl").read_text(encoding="utf-8").splitlines() if line]
            store.upsert(docs)
        finally:
            store.db.close()
        task = cli("tasks", "make", "--kind", "extract_entities")[0]
        cli("tasks", "submit", task, "--file", str(ROOT / "examples/tasks_demo/extract_entities.good.json"))
        node = cli("tasks", "merge", task)["node_ids"]["e1"]
        task = cli("tasks", "make", "--kind", "gen_propositions", "--node", node)[0]
        prop = dict(prop_id="synthetic-reading", text="Synthetic reading preference", kind="preference",
                    subject_node_ids=[node], confidence=0.6, status="proposed", valid_from=None, valid_to=None,
                    counter_evidence=[], evidence=[dict(doc_id=d.id, span=[0, len(d.text)],
                    quote_hash=hashlib.sha256(d.text.encode()).hexdigest()[:12]) for d in docs[:2]])
        path = Path(directory) / "output.json"
        path.write_text(json.dumps(dict(ops=[dict(op="ADD", prop=prop)])), encoding="utf-8")
        assert cli("tasks", "submit", task, "--file", str(path))["state"] == "accepted"
        cli("tasks", "merge", task)
        assert cli("profile", "list")[0]["status"] == "proposed"
        cli("profile", "correct", prop["prop_id"], "--verdict", "wrong", "--note", "Synthetic correction")
        assert cli("tasks", "merge", task)["state"] == "noop"
        rejected = cli("profile", "list")[0]
        assert rejected["status"] == "rejected" and rejected["suppressed_by"]
        # Regeneration from the corrected snapshot must not overwrite the verdict.
        task = cli("tasks", "make", "--kind", "gen_propositions", "--node", node)[0]
        prop["confidence"] = 0.9
        path.write_text(json.dumps(dict(ops=[dict(op="UPDATE", prop=prop)])), encoding="utf-8")
        assert cli("tasks", "submit", task, "--file", str(path))["state"] == "accepted"
        cli("tasks", "merge", task)
        assert cli("profile", "list")[0] == rejected
        print("PASS: wrong correction survives repeat merge and regenerated output")


if __name__ == "__main__":
    main()
