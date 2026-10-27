# Agent task workflow and M7 light models

ATLAS is an offline graph and correctable profile shell. Task work lives only in
`ATLAS_DATA_DIR/work/{pending,claimed,submitted,accepted,rejected}/<task_id>/`.
A task directory contains its envelope, input, output schema and instructions;
claiming adds a lease, submission adds output and validation errors when needed.
Use the task directory's schema as authority. Prefer `{doc_id, quote}` evidence:
copy an exact, nonblank excerpt of at most 60 Unicode characters. Agents need not
compute hashes. ATLAS converts quotes to `{doc_id, span: [start,end], quote_hash}`
using original character offsets (end exclusive) and the first 12 hexadecimal
characters of SHA-256 over the UTF-8 source span. Existing span/hash pointers remain valid.

| Kind | Contract | Current support |
| --- | --- | --- |
| extract_entities | entities, relations, statements; evidence must resolve | make, validate, merge entities/relations/statements |
| resolve_entities | one ADD/MERGE_INTO/NOOP per candidate; existing merge target | make with --input, validate, merge |
| gen_propositions | ADD/UPDATE/SUPERSEDE/NOOP; at least two support pointers; retain counter evidence | make with --node, validate, merge |
| cluster_lens | topic statements, explicit line identity and shift | make from persisted records, validate, merge |
| verify | confirmed/refuted/mixed/unknown with basis; unknown without data | schema only; no task execution/merge |

`tasks make|list|claim|submit|validate|merge|run|reap` manage the queue. Claim with
`--owner`; submit with `--file` and the same owner when claimed. Only accepted
outputs merge. Merges are idempotent by task identity and input hash. Superseded
history is retained. User corrections override agent output and rejected,
suppressed propositions cannot be revived by an agent.

Runner commands come from `[runners.<name>] cmd=[...]`. Use `--print-cmd` to
inspect templates; tests use only `examples/tasks_demo/fake_agent.py` with
`--runner cmd`. Do not invoke external agents or paid APIs during acceptance.
Credential matches are replaced with `[CREDENTIAL]`; logs report line numbers,
not matched values. This is separate from the repository leak scanner.

## Reproduce the fictional M5 page (PowerShell, repository root)

Use explicit disposable paths so an inherited real data path is never used:

```powershell
$env:ATLAS_DATA_DIR = "$PWD/_demo_out/m5-data"
$env:ATLAS_OUT_DIR = "$PWD/_demo_out/m5-site"
C:\Python314\python.exe -m examples.tasks_demo.seed_m5
C:\Python314\python.exe -m atlas all --config examples/atlas.config.example.toml
C:\Python314\python.exe -m unittest discover -s tests -v
C:\Python314\python.exe tools/leak_scan.py
```

The seed is an explicit frontend fixture using fictional example evidence; it
is not an extractor. It writes only `_demo_out/m5-data` when run as a module.
`atlas all` ingests documents and exports the existing graph; it does not invent
a graph or call an agent. Without merged records or a fixture the graph is empty.
Open `_demo_out/m5-site/index.html`. The companion `data.js` enables offline
file viewing; `atlas.json` contains `nodes`, `edges`, `propositions`, `lenses`.
This replaces the older `views` export key. Built-in lenses now project graph
propositions, not raw document text. Custom lenses receive `ctx.graph` as well
as the document argument. The judgment lens prefers accepted lines, then groups stored statements by shared
about nodes. Connected topics form one timeline. Fallback points have unassessed
shifts and unknown outcomes; no stance change is inferred. Legacy graphs without
statements can still display proposition history.
Unknown dates stay unknown.

## Review and correct

The graph tab offers type filtering and node details with directed relations,
validity/observation times, evidence pointers and propositions. The profile tab
shows confidence, validity, status, evidence and counter evidence. Judgment
lines and timeline are separate tabs. Sensitive nodes, linked relationships,
propositions and lens entries are hidden by default, with an explicit toggle.
The export still contains sensitive records: the toggle controls display, not
redaction or access control. Keep generated artifacts private in real use.

Click 对 / 不对 / 补充 to queue a correction (amend requires a note). Download the
JSONL fragment, review it and append its lines once to `corrections.jsonl` in
the same data directory. Do not replace the existing journal or import the same
correction ID twice. Run `atlas build --config <config>` to replay and display
corrections. A fragment has `correction_id`, `prop_id`, `verdict` (right, wrong,
amend), `note`, and `observed_at`. Superseded propositions are historical and
have no correction buttons. The static page does not write files or pretend
that an export has already changed the graph. Pending fragments exist only in
page memory until downloaded. Turning sensitive display off also excludes
sensitive queued corrections from preview and download.

For direct CLI corrections use:
`atlas profile correct <prop_id> --verdict wrong|right|amend --note <note>`
with an explicit demo data path or config. `atlas profile list` displays the
current projected state. The optional MCP server is separate from the M6 quality milestone.

## Real agent run on the fictional corpus (Windows)

Runners resolve `codex`/`agy`/`grok` via PATH, `ATLAS_RUNNER_PATH` and default
per-user install dirs (`%APPDATA%\npm`, `%LOCALAPPDATA%\agy\bin`, `~\.grok\bin`);
`.cmd` shims run through `cmd /c`, `.ps1` through PowerShell. Codex receives the
prompt on stdin (`-`), grok via `--prompt-file`, agy via a short `-p` pointing at
`PROMPT.md`. Codex has no `--output-schema` (strict mode rejects optional keys);
ATLAS validates output.json itself. Agent JSON wrappers (`structuredOutput`,
`result`, `response`...) are unwrapped. Encoding-corrupted output is rejected.

```powershell
$c = "examples/atlas.run.config.toml"
python -m atlas tasks make --kind extract_entities --config $c
python -m atlas tasks run --runner codex --timeout 1200 --config $c
python -m atlas tasks merge <task_id> --config $c
python -m atlas tasks make --kind gen_propositions --node <node_id> --config $c
python -m atlas tasks run --runner codex --parallel 4 --timeout 1200 --config $c
python -m atlas all --config $c   # -> _demo_out/run-site/index.html
```
## M6 quality contracts

M6 tasks used schema/prompt version 2; M7 tasks use version 3; existing task directories and their original
outputs are retained. Re-extraction under the new version is an explicit new task,
not a migration of previously merged graph records.

Extraction persists `statements` with task-scoped IDs, mapped `about` node IDs,
kind/text/stance, source evidence, speaker/time, sensitivity and calibrated confidence.
Chat `[MM-DD HH:MM] speaker: text` evidence is attributed only when it selects one
line. The year must be uniquely resolvable within the document date / `meta.ts_end`
interval. Plain text falls back to document author/time. Ambiguous multi-speaker
spans have unknown speaker; unknown dates are never replaced by processing time.

Validation retains independent valid entities, relations, statements, operations
and lines. `output.json` contains the normalized submission; `accepted.json` contains
only retained items. Agent originals are preserved under `attempts/*/output.json`. `errors.json` lists indexed reasons. `validation.json` and the
CLI response contain `partial`, accepted/dropped counts, and diagnostics. Missing
resolution operations are reported against candidate indices. Broken input or
envelope data, malformed outer output, or no valid items rejects the task.
Dropped entities also drop dependent relations/statements. Merge revalidates and
uses only accepted items, with a transaction and normalized-output hash for replay
idempotency. Live graph changes that make an accepted operation stale still abort
its transaction rather than silently overwrite newer state.

`tasks make --kind cluster_lens` snapshots persisted statements and active
propositions (with source IDs, short refs, time, speaker, text, about node IDs and names). It makes
batches of at most `[tasks].lines_batch` records (default 60, including propositions)
and the configured character target; one oversized
record remains intact. Empty graphs produce no tasks. Submit JSON of this shape:

```json
{"lines":[{"line_id":"fiction-line","title":"Fictional garden","topic":"input-node-id",
 "timeline":[{"statement_id":"input-statement-id","shift":"first","reason":"First input record",
 "outcome":"unknown","outcome_statement_ids":[],"outcome_reason":""}]}]}
```

Points reference input IDs or short refs, never agent-supplied dates or speakers. Shifts are
`first`, `same`, `strengthen`, `weaken`, `reverse`, `new_angle`; each needs a reason.
Known outcomes (`confirmed`, `refuted`, `mixed`) need an explanation and IDs of
strictly later related input statements. Otherwise use `unknown`. These checks
verify reference/time grounding, not the semantic truth of the agent's explanation.
Merged line IDs are task-scoped, and the display coalesces connected topics across
batches. A correction invalidating outcome support resets that outcome to unknown.

New propositions of the same kind fold into an active proposition when their
subject sets match or normalized character-bigram Jaccard similarity is at least
0.6. Evidence, counter evidence, subjects and sensitivity are combined; merge
reports `deduplicated`. Explicit SUPERSEDE operations retain their historical
meaning. User suppression takes precedence, including equivalent cross-node claims.
Same-subject folding is deliberately broad: inspect the retained claim and evidence.

Confidence retains `raw_confidence`. Caps are 0.55 for one source document, 0.7
for two, 0.8 for three or more, and 0.9 for three or more with at least three known
dates spanning seven days. Each distinct counter-evidence document divides the
capped score by `1 + counter_document_count`. Statements and scored relations use
the same calibration. Scores are evidence-breadth limits, not truth probabilities.

```toml
[tasks]
batch_docs = 50
batch_chars = 40000
lines_batch = 60
```

Extraction respects both batch limits; a single oversized document remains intact
so evidence offsets stay valid. All per-kind instructions require source-language
text, calibrated confidence, and source-backed relations (density is a target,
not permission to invent edges).

Use `atlas tasks merge --all` to merge all accepted tasks, including idempotent
replays. `atlas graph stats` reports retained table counts, active nodes/edges,
isolated nodes, active edges per active node, stored statements/lines, average
points per stored line and an active-proposition confidence histogram. Histogram
bins include their upper bound. Empty denominators yield zero.

The Chinese frontend includes reading/correction guidance on each tab, a vertical
per-topic timeline with speaker/text/shift/outcome, and sensitivity filtering off
by default. Sensitive outcome support also hides its derived point. Generated
JSON remains a private full export; this display filter is not access control.

Offline checks (no agents or paid APIs):

```powershell
C:\Python314\python.exe -m unittest discover -s tests
C:\Python314\python.exe tools/leak_scan.py
```

## M7 quote resolution and reference repair

Quotes resolve only against task-scoped documents in the canonical, credential-filtered
store. Exact matches take precedence. Otherwise ATLAS ignores whitespace and folds
full-width punctuation, mapping the result back to original offsets. Repeated quotes
select the first occurrence not already used by the same item (across support and
counter evidence, including supplied span pointers), then fall back to the first.
No case folding, fuzzy text repair, or invented source text is used.

Unresolvable quotes remove only that evidence, with indexed diagnostics that omit
quote text. Items left without required evidence are dropped. Propositions still
need two distinct supports, disjoint counter evidence, and retention of known counter
evidence; correction precedence is unchanged. Quote text is removed from normalized
output and never stored in graph evidence. Revalidation checks normalized pointers
against the source again. Original submissions remain in attempts, including rejected
submissions; these task workspaces are private runtime artifacts, never repository data.

Relations and statements must reference entity tmp_ids from the same output. A unique
exact entity name or alias is repaired to its tmp_id. Unknown or ambiguous references,
and references to dropped entities, drop the dependent item. Existing tmp_ids take
precedence over names. Empty graphs still produce no cluster tasks. `lines_batch`
must be a positive integer; character limits still apply and oversized single records
stay intact. Existing task directories are not rewritten when new version-3 tasks
are created; no historical graph migration is performed.


## M8 compact judgment lines and repair

New `cluster_lens` tasks use schema/prompt version 4; other task kinds remain at
version 3. Existing task directories are preserved. Each batch assigns unique
`s1`, `s2`, ... refs across statements AND propositions. Inputs retain canonical
`statement_id`, `ts`, `speaker`, `text`, `about` node IDs, an `about_names` mapping
and sensitivity. Documents contain only IDs and existing lines contain only
identity/title/topic summaries; evidence pointers remain in the graph and are
projected from source records at display time.

Timeline points may use `ref` instead of `statement_id`, or put the short ref in
`statement_id`. Outcome support IDs also accept short refs. Canonical IDs take
precedence. ATLAS resolves these before schema validation, drops unknown points,
keeps the first occurrence of each source across lines, sorts by source time
(unknown first, canonical ID as tie-break), forces the first shift to `first`,
and changes later `first` labels to `same`. A line with no retained points is
dropped; a task with no surviving lines is rejected. Malformed envelopes and
structurally invalid line metadata still fail their existing schema checks.

Invalid outcomes become `unknown` with empty support and explanation. Known
outcomes require an explanation and strictly later, related input records on the
same line; unknown dates cannot establish support. These checks establish source
reference and time grounding, not semantic truth. Corrections still invalidate
outcome support at display time. Original submissions remain in attempts.

Instructions request EVERY input record exactly once, aggressive grouping by
underlying topic, normally at least three points per line, and singletons only
when isolated. Later shifts compare with the previous point and give a short
reason in the source language. Outcomes should be labeled when later records
show what happened. Density is a prompt target, never permission to invent facts.
The optional agent `unassigned_count` is not trusted: `accepted.json` receives the
computed count, and CLI / `validation.json` report it as `counts.unassigned`,
including propositions. Missing coverage does not reject otherwise valid lines.

The lens coalesces accepted lines across batches when topic node IDs match or
normalized character-bigram title Jaccard similarity is at least 0.6 (Unicode
NFKC, case folding, alphanumeric characters only). Points are deduplicated and
sorted again. Batch-boundary shifts not evaluated by an agent stay unknown.
Fallback hub exclusion is unchanged: people and nodes above the existing
`max(3, 25% of source records)` threshold do not join fallback groups. Empty
graphs remain empty. All M8 tests use fictional local records without network
or external agents; run the unit suite and leak scanner with the commands above.
