# M10 brief (generic; synthetic tests; no private data; no network; do not commit)
Observed: a fast model cited invented document ids (e.g. "doc_x_001") with otherwise sensible line
ranges, so gen_propositions tasks were rejected; lens-fallback lines carry null shifts.
1. Short document refs: in extract_entities and gen_propositions inputs give every document a
   short `ref` (d1, d2, ...) shown at the head of its numbered_text ("[d3] L1: ...") and in the
   document object. Evidence may use doc_id = ref or the real id; ATLAS maps refs back. Drop the
   duplicate raw `text` field from task inputs when numbered_text is present (keep input small).
   Instructions: "cite documents only by their ref, e.g. {doc_id: "d3", lines: [2, 4]}".
2. If an evidence doc_id is unknown but exactly one input document exists, map to it; otherwise drop
   the item as now.
3. Lens fallback lines: first point shift "first", later points "unclear" (never null), so every
   displayed point has a label; stats report how many were model-labelled vs repaired/fallback.
4. Tests; docs; run unit tests and tools/leak_scan.py until green.