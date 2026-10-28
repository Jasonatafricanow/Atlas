"""Rule-based entity candidates; never writes graph.sqlite or corpus.sqlite."""
from .index import index_mentions, suggest_merges

__all__ = ["index_mentions", "suggest_merges"]
