"""Backend-neutral API and evidence pointers; no source excerpts in refs."""
import re
from typing import Literal, Protocol, TypedDict, runtime_checkable


class CharSpanRef(TypedDict):
    kind: Literal["char_span"]
    doc_id: str
    start: int
    end: int
    quote_hash: str


class MessageParagraphsRef(TypedDict):
    kind: Literal["message_paragraphs"]
    record_id: str
    paragraphs: list[int]


EvidenceRef = CharSpanRef | MessageParagraphsRef


def validate_ref(ref: EvidenceRef) -> EvidenceRef:
    """Validate pointer shape only; each backend must verify its source content.

    Character offsets are zero-based, end-exclusive; paragraph indices are
    zero-based, distinct and ascending within a stable message record.
    """
    if ref.get("kind") == "char_span":
        valid = (isinstance(ref.get("doc_id"), str) and bool(ref["doc_id"])
                 and type(ref.get("start")) is int and type(ref.get("end")) is int
                 and 0 <= ref["start"] < ref["end"]
                 and isinstance(ref.get("quote_hash"), str)
                 and re.fullmatch(r"[0-9a-f]{12}", ref["quote_hash"]))
    elif ref.get("kind") == "message_paragraphs":
        paragraphs = ref.get("paragraphs")
        valid = (isinstance(ref.get("record_id"), str) and bool(ref["record_id"])
                 and isinstance(paragraphs, list) and bool(paragraphs)
                 and all(type(p) is int and p >= 0 for p in paragraphs)
                 and paragraphs == sorted(set(paragraphs)))
    else:
        valid = False
    if not valid:
        raise ValueError("invalid evidence ref")
    return ref


def char_span_ref(pointer) -> CharSpanRef:
    start, end = pointer["span"]
    return validate_ref(dict(kind="char_span", doc_id=pointer["doc_id"],
                             start=start, end=end, quote_hash=pointer["quote_hash"]))


@runtime_checkable
class Backend(Protocol):
    def toc(self, params: dict) -> dict: ...
    def home(self, params: dict) -> dict: ...
    def lines(self, params: dict) -> dict: ...
    def line(self, params: dict) -> dict: ...
    def entities(self, params: dict) -> dict: ...
    def entity(self, params: dict) -> dict: ...
    def search(self, params: dict) -> dict: ...
    def evidence(self, params: dict) -> dict: ...


ROUTES = ("toc", "home", "lines", "line", "entities", "entity", "search", "evidence")


def dispatch(backend: Backend, route: str, params: dict) -> dict:
    if route not in ROUTES:
        raise KeyError(route)
    return getattr(backend, route)(params)
