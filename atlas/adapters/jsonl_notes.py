import json, os, hashlib
from . import Adapter
from ..schema import Document

class JsonlNotesAdapter(Adapter):
    """Generic adapter: one JSON object per line with at least ts + text."""
    name = "jsonl_notes"
    def read(self):
        path = self.options["path"]
        for i, line in enumerate(open(path, encoding="utf-8")):
            if not line.strip():
                continue
            o = json.loads(line)
            did = o.get("id") or hashlib.sha1(f"{path}:{i}:{o['text']}".encode()).hexdigest()[:16]
            yield Document(id=did, source=self.name, ts=o["ts"], text=o["text"],
                           author=o.get("author", "me"), channel=o.get("channel", os.path.basename(path)),
                           tags=o.get("tags", []), meta=o.get("meta", {}))
