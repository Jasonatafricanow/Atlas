# M7 brief: make light/fast models succeed (generic, synthetic tests only)

Light models (fast/flash tiers) fail extraction because they cannot compute character spans and
SHA-256 quote hashes: most items are dropped with `quote_hash: mismatch`, and the run ends with
almost nothing. Fix generically:
1. Evidence may be given as `{doc_id, quote}` (short exact excerpt, <= 60 chars) instead of
   `{doc_id, span, quote_hash}` in every output schema that has evidence. On submit/validate, ATLAS
   resolves the quote against the stored document text: exact match first, then whitespace/
   full-width-punctuation-normalised match mapped back to original offsets; if several matches,
   pick the first not already used by the same item, else first. Then it rewrites the pointer to
   `{doc_id, span, quote_hash}` (the quote text is NOT kept in output.json/graph; store the
   normalised output as output.json and keep the agent original under attempts/). Unresolvable
   quotes drop only that evidence; an item with no evidence left is dropped (partial acceptance).
   Span/hash pointers keep working unchanged. Leak scan / credential guard still apply.
2. Instructions (INSTRUCTIONS.md / PROMPT.md for all kinds) tell agents to prefer the quote form
   and not to compute hashes; keep them short so small models follow them. State clearly: entity
   tmp_ids referenced by relations/statements must exist in entities.
3. Unknown entity references in relations/statements: if the reference equals an entity name or
   alias (instead of tmp_id), map it; otherwise drop the item.
4. cluster_lens batches: configurable `[tasks].lines_batch` (default 60 statements) so each task
   is small.
5. Tests for all of the above; update docs. Run unit tests and tools/leak_scan.py. Do not commit.
Never read real chat exports, real ATLAS data directories, or private ATLAS projects.
No network, no git push.
