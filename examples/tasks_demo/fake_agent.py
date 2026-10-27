"""Offline synthetic extraction replay; never calls an external service."""
import argparse
import hashlib
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--task-dir", type=Path, required=True)
parser.add_argument("--stdout", action="store_true")
parser.add_argument("--mode", choices=["good", "bad", "fail", "missing", "sleep"], default="good")
args = parser.parse_args()
if args.mode == "fail":
    raise SystemExit(7)
if args.mode == "sleep":
    time.sleep(5)
if args.mode == "missing":
    raise SystemExit(0)
payload = json.loads((args.task_dir / "input.json").read_text(encoding="utf-8"))
doc = payload["documents"][0]
output = {"entities": [{"tmp_id": "synthetic", "type": "concept", "name": "Synthetic concept",
          "aliases": [], "evidence": [{"doc_id": doc["id"], "span": [0, len(doc["text"])],
          "quote_hash": hashlib.sha256(doc["text"].encode("utf-8")).hexdigest()[:12]}]}],
          "relations": [], "statements": []}
if args.mode == "bad":
    output["entities"][0]["evidence"][0]["quote_hash"] = "000000000000"
if args.stdout:
    print(json.dumps(output))
else:
    (args.task_dir / "output.json").write_text(json.dumps(output), encoding="utf-8")
