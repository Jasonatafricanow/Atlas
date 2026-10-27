# M8 brief: judgment lines that light models can produce (generic, synthetic tests only)

Observed on a real small sample: cluster_lens outputs are rejected wholesale because fast models
cite non-existent statement_ids (long hashes), timelines are not in time order, or `first` is
misplaced; without accepted lines the lens fallback yields ~50 lines of which ~60% are single
points and almost no shift labels. Make it robust and the result denser:
1. Short refs: cluster_lens input gives every statement/proposition a short `ref` (s1, s2, ...)
   plus ts, speaker, text, about (node ids AND node names). Output timelines may cite `ref` or
   statement_id; ATLAS maps refs back. Keep the input compact (drop evidence detail not needed).
2. Repair instead of reject: unknown ids are dropped from a line (item-level), duplicates removed,
   timeline re-sorted by source time, the first point forced to shift `first`, later points with
   `first` become `same`; invalid outcomes are reset to unknown. A line is dropped only if fewer
   than 1 valid point remains; the task is rejected only if no line survives.
3. Coverage: instructions ask the agent to assign EVERY input statement to exactly one line,
   merging aggressively by underlying topic (a stock, a sector, a trading rule, a life plan,
   a person) so most lines have >= 3 points; singletons only when truly isolated; label each
   later point's shift vs the previous point on that line (same/strengthen/weaken/reverse/
   new_angle) with a short reason in the source language, and set outcome confirmed/refuted/mixed
   when a later statement on the line shows what happened. Report unassigned statements count.
4. Cross-batch merge: lines from different lines_batch tasks with the same topic node or
   near-identical titles (normalised bigram Jaccard >= 0.6) are merged in the lens.
5. Lens fallback (no accepted line) must ignore hub nodes (people / nodes on >25% of statements)
   — already present; keep it.
6. Tests for each item; update docs/AGENT_TASKS.md. Run unit tests and tools/leak_scan.py. Do
   not commit. Never read the private data directories. No network, no git push.