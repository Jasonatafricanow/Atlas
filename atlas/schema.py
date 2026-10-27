"""Standard Document schema. Every adapter must emit these; lenses only read these."""
from dataclasses import dataclass, field, asdict

@dataclass
class Document:
    id: str                 # stable unique id (adapter-defined)
    source: str             # adapter name, e.g. "jsonl_notes"
    ts: str                 # ISO-8601 date or datetime
    text: str
    author: str = "me"      # "me" or a pseudonymous label; adapters decide
    channel: str = ""       # conversation / notebook / folder
    tags: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)   # sensitivity flags etc.

    def to_dict(self):
        return asdict(self)
