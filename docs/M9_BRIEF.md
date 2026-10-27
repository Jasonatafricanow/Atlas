# M9 brief (generic; synthetic tests only; never read private data dirs; no network; do not commit)

1. Line-range evidence for extract_entities (and gen_propositions): the task input shows each
   document's text with stable line numbers (L1, L2, ...). Agents may cite evidence as
   {"doc_id": ..., "lines": [start, end]} (1-based, inclusive, max 6 lines) instead of quoting.
   ATLAS resolves it to the canonical {doc_id, span, quote_hash}. Out-of-range or unknown-doc
   evidence is dropped per item (item rejected only if it has no valid evidence); the task is
   rejected only if nothing valid remains. Keep the existing quote/span forms working.
   Statement `text` is the speaker's position in the agent's own words (source language), not a
   copy. Update the extract instructions: prefer line ranges; extract EVERY opinion, judgment,
   prediction, plan, decision or preference by any speaker (aim for >= 1 per 3-4 substantive
   messages); give speaker exactly as shown in the line. Keep the prompt short.
2. Guard false positives: credential/card/ID filtering must not alter identifier fields. In
   sanitize(), skip dict values whose key is an identifier key (id, ids, *_id, *_ids, msg_ids,
   doc_id ...). Text is still filtered. Add a counter API (no values logged) and make ingest log a
   single summary line "credential filter: N lines in M documents" instead of one line per hit.
3. Shift coverage: in cluster_lens output every non-first point must carry shift from
   same/strengthen/weaken/reverse/new_angle/unclear (schema-required); instructions say so
   explicitly with one-line definitions. Validation repairs a missing/invalid shift to "unclear"
   and counts repairs in the task result. UI shows "unclear" as 未判明.
4. Legacy seeds: a generic command `atlas seed import --file <json> --config <cfg>` reading
   {nodes:[{id,name?,type?}], edges:[{s,t,r,date?}]} stores them with source="legacy",
   status="reference". They never overwrite or merge into built nodes/edges, are excluded from
   graph stats/lines and from task inputs, and render in a separate collapsible "旧版参考" section.
   Relation names are normalised to the built vocabulary via a small configurable synonym map
   plus normalisation (strip, lowercase, punctuation); unmapped ones become relation
   "related_to" with the original kept in attr `legacy_relation` (also counted). Report counts:
   nodes, edges, mapped, unmapped, distinct original relations. Legacy Documents (source=legacy)
   are reference only: excluded from extract task batches by default ([tasks] include_legacy=false).
5. Tests for every item; update docs. Run unit tests and tools/leak_scan.py until green.