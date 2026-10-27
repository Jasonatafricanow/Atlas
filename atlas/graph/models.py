"""Graph records contain evidence pointers, never copied source excerpts."""
from dataclasses import dataclass, field

NODE_TYPES = ("person", "concept", "place", "event", "instrument", "topic")


@dataclass
class Evidence:
    doc_id: str
    span: list[int]
    quote_hash: str


@dataclass
class Node:
    node_id: str
    type: str
    name: str
    evidence: list = field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None
    sensitive: bool = False


@dataclass
class Edge:
    edge_id: str
    src: str
    dst: str
    type: str
    evidence: list = field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None
    status: str = "confirmed"
    superseded_by: str | None = None
    sensitive: bool = False


@dataclass
class Proposition:
    prop_id: str
    text: str
    subject_node_ids: list[str]
    evidence: list
    counter_evidence: list = field(default_factory=list)
    confidence: float = 0.0
    kind: str = "fact"
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None
    status: str = "proposed"
    superseded_by: str | None = None
    suppressed_by: str | None = None
    sensitive: bool = False
