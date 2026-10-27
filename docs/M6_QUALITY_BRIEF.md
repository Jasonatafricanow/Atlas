# M6 quality brief (generic, no private data)

Context: ATLAS core (this repo) is a data-free shell. A private repo feeds it chat-segment
Documents whose text is lines like `[MM-DD HH:MM] <speaker>: <message>` (speaker `我` = the owner),
with `meta.speakers`, `meta.ts_end`, `meta.sensitive`. A real small-sample run exposed these
problems; fix them generically, with tests using ONLY synthetic/fictional data. Never read
real chat-export directories, real data directories, or private adapter repositories. No network, no git push.

Problems seen: few relations (most nodes isolated); extraction `statements` are discarded at merge;
judgment lines are single points with shift=none; duplicate propositions across nodes;
confidence ~0.9 everywhere; one bad op rejects a whole task; occasional English output.

Required changes
1. Statements persisted: extraction merge stores each statement in a new graph table
   `statements` (id, kind, text, stance, about node ids via the task mapping, speaker, ts taken
   from the evidence line timestamp when parseable else document ts, evidence, confidence,
   sensitive). Speaker attribution: generic helper (e.g. `atlas/chat.py`) that, for chat-formatted
   documents, maps an evidence span to the line's speaker and time; fall back to doc author.
2. Partial acceptance: validation checks each entity/relation/statement/op individually. Valid
   items are kept, invalid ones listed in errors.json with index and reason; task state is
   `accepted` (with `partial: true` and counts) if anything valid remains, `rejected` only if
   nothing valid or the envelope/input is broken. Relations whose endpoints were dropped are
   dropped too. Merge uses only accepted items. Keep idempotency.
3. Judgment lines that are real: implement task kind `cluster_lens` (schemas exist; adapt if
   needed): input = persisted statements (+propositions) with ids, ts, speaker, text, about;
   output = lines {title, topic, statement_ids in time order, per-point shift
   (first/same/strengthen/weaken/reverse/new_angle) with reason, outcome (confirmed/refuted/
   mixed/unknown) only when later statements in the input support it}. `tasks make --kind
   cluster_lens` packages all statements (chunk if large). Merge writes `lines` table. The
   judgment_lines lens prefers merged lines; without them falls back to grouping statements by
   shared topic/about node in time order (never a 1-point line unless nothing else; merge
   lines that share nodes). Each point shows when, who, what was said, shift, later outcome.
4. Cross-node proposition dedup at merge: same kind + high normalized-text similarity (e.g. char
   bigram Jaccard >= 0.6, tune with tests) or same subject set -> fold evidence into the
   existing active proposition instead of adding. Report dedup counts.
5. Confidence calibration at merge (store `raw_confidence`): cap by evidence breadth, e.g.
   1 distinct doc <=0.55, 2 <=0.7, >=3 docs <=0.8, >=3 docs spanning >=7 days <=0.9;
   counter evidence lowers it. Same for statements/relations where a confidence exists.
6. Agent instructions (INSTRUCTIONS.md per kind): write all text fields in the source language
   (Chinese for Chinese input); relation density: connect every entity to at least one other
   (speaker person node included; 我 = owner as a person entity), target >= 1.5 relations per
   entity, generic verb-like relation types; one statement per distinct opinion/prediction/
   plan/preference with speaker-relevant stance; gen_propositions: each prop needs >=2 distinct
   support pointers from different docs when possible, else lower confidence; be calibrated.
7. Scale: `[tasks].batch_docs` (default 50) and `[tasks].batch_chars` (default ~40000) for
   extract batching; `atlas tasks merge --all` merges every accepted task; `atlas graph stats`
   also reports active nodes/edges, isolated-node count, edges per node, statements, lines,
   avg points per line, proposition confidence histogram.
8. Frontend (web/index.html) self-explanatory: a short "how to read / how to correct" intro on
   each tab; judgment lines rendered as one vertical timeline per topic (date, speaker, what was
   said, shift badge, outcome) — no fragmented per-case tables; sensitive items hidden by
   default behind a toggle; Chinese UI labels (source file must stay valid UTF-8).
9. Update docs/AGENT_TASKS.md and README; add tests for every item; run
   `C:\Python314\python.exe -m unittest discover -s tests` and `C:\Python314\python.exe tools\leak_scan.py`.
   Keep the core free of personal data and default data paths. Do not commit; leave changes in
   the working tree and print a summary of files changed and test results.