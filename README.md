# ATLAS core

MR-Mem AML stores can be opened through the separate, read-only
[MR-Mem reader](docs/mrmem_reader.md):
`python -m atlas serve --backend mrmem --data-dir <directory> --user-id <user> --mrmem-url http://127.0.0.1:8000`.
Search uses the running MR-Mem service's native retrieval and ranking, with source-backed memory
details, stored segment versions and verified whole-message evidence.

A **data-free** framework for turning a personal text corpus into browsable "lenses"
(judgment lines, timelines, correctable claim lists...). This repository contains
**no personal data and no default data paths**. Your corpus, private adapters,
private lenses and corrections live in a separate directory/repo you point to.

```
python -m atlas all --config examples/atlas.config.example.toml   # fictional demo
# open _demo_out/index.html
```

## Concepts
- **Document** (`atlas/schema.py`): the only data contract. `id, source, ts, text, author, channel, tags, meta`.
- **Adapter**: raw export -> Documents. Core ships only `jsonl_notes`. Chat-app exporters are private adapters.
- **Store**: `corpus.sqlite` inside `data_dir` (set via config or `ATLAS_DATA_DIR`).
- **Lens**: plugin `build(docs) -> JSON view`. All vocabularies/rules/prompts come from lens config files.
- **LLM**: `atlas.llm.Pipeline(provider, presend=[...])`; default `NullProvider` is offline.
  Redaction / sensitivity veto are optional `PreSend` hooks.
- **Frontend**: `web/index.html`, static, reads generated `data.js`. Holds no data.
- **Corrections**: `data_dir/corrections.jsonl` (`{"correction_id":..,"prop_id":..,"verdict":"wrong","note":..,"observed_at":..}`), shown on cards.

## Private setup (sketch)
```
my-atlas-private/            # private git repo, never public
  atlas.config.toml          # paths -> D:/atlas-data
  adapters/my_chat_export.py # class MyChatAdapter(atlas.adapters.Adapter)
  lenses/trade_ledger.py     # personal lenses
  lens_configs/*.json        # personal vocabularies
  run_daily.ps1              # python -m atlas all --config atlas.config.toml
```

## Leak safety
`git config core.hooksPath .githooks` enables `tools/leak_scan.py` before every commit.
Put private names in a denylist file outside the repo and set `ATLAS_LEAK_DENYLIST`.

## M1 offline graph storage and task queue

M1 provides graph storage primitives and auditable supersession, task contracts,
and an offline extraction queue. M2 adds the merge workflow described below.

PowerShell synthetic-only acceptance setup (run from the repository root):

```powershell
$env:ATLAS_DATA_DIR = Join-Path $PWD '_demo_out/m1-data'
$env:ATLAS_OUT_DIR = Join-Path $PWD '_demo_out'
C:\Python314\python.exe -m unittest discover -s tests -v
C:\Python314\python.exe -m atlas tasks make --kind extract_entities --config examples\atlas.config.example.toml
C:\Python314\python.exe -m atlas tasks list --json
# Replace <id> with the ID returned by make/list.
C:\Python314\python.exe -m atlas tasks submit <id> --file examples\tasks_demo\extract_entities.good.json
C:\Python314\python.exe -m atlas tasks submit <id> --file examples\tasks_demo\extract_entities.bad_evidence.json
C:\Python314\python.exe -m atlas graph stats
C:\Python314\python.exe tools\leak_scan.py
```

A valid submission exits 0 and moves to `accepted`. The bad-evidence fixture
exits 1 and moves to `rejected`; `errors.json` identifies the quote_hash mismatch.
Re-submissions preserve previous outputs and diagnostics under `attempts/`.
Graph statistics remain zero until `tasks merge` writes accepted outputs.
Without `--config`, queue and graph commands require an
explicit `ATLAS_DATA_DIR`; they do not discover private configuration or data.

Workers use `tasks claim <id> --owner demo-worker --lease-seconds 300`, then
`tasks submit <id> --file output.json --owner demo-worker`. `tasks reap` returns
expired claims to pending. `tasks validate <id>` rechecks a submitted result
against the document Store. All queue mutations use an exclusive lock.

Task workspaces live under `ATLAS_DATA_DIR/work/<state>/`. Logical IDs contain a
colon; directory names encode it as `__` for Windows compatibility. Extract tasks
default to at most 50 documents and a 40000-character target (configurable). Repeating make reuses unchanged tasks. Changed
content under the same document IDs is rejected as a collision; new source
versions must receive new document IDs. Evidence spans are Unicode character
indices with an exclusive end, and hashes use UTF-8. The built-in validator
covers the JSON Schema subset used by all shipped contracts without dependencies.
`[tasks].forbidden_terms` can override the extraction wording blacklist; the
selected terms are captured in each task input.

## M2 extraction and entity resolution

`atlas tasks merge <id>` merges an accepted extraction or resolution task. Each
task is revalidated against the source Store before merging. Graph changes,
aliases, evidence pointers, operation history and the task marker commit in one
SQLite transaction. Repeating the same `task_id + input_hash` leaves every table's
row count unchanged, including `ops_log`. A changed output for an already merged
task is refused. Extraction statements are persisted with source-attributed speaker/time and
calibrated confidence; profile generation remains a separate task.

Extracted nodes have task-scoped identities: names and aliases alone do not prove
identity. Use `tasks make --kind resolve_entities --input <file>` to package a
resolution input containing `candidates`, existing `nodes` summaries, and source
`documents`. Candidate evidence is checked against the Store. Candidate `node_id`
optionally identifies a node previously extracted into the graph. Output requires
exactly one `ADD`, `MERGE_INTO`, or `NOOP` operation per candidate. `MERGE_INTO`
requires a same-type target in the input snapshot and an active target in the live
graph. It preserves evidence and aliases, redirects active edges, and retains the
source node with `status: superseded` and `superseded_by`. Historical superseded
edges remain unchanged. `ADD` creates a new node; `NOOP` leaves the candidate alone.
Resolution task prompt versions include the input snapshot digest so changed
candidate sets can be packaged independently.

Relations can explicitly identify a contradictory predecessor through the optional
`supersedes` edge ID and must provide `valid_from` as the transition time. The old
edge is retained with `status: superseded`, `valid_to` equal to that time, and
`superseded_by` pointing to the new edge. Both relations must have the same type.
Different targets alone do not imply contradiction: without `supersedes`, both
relations are retained. The caller is responsible for the semantic assertion of
contradiction; M2 validates the references and temporal bounds.

Run all M2 acceptance checks with the specified interpreter:

```powershell
C:\Python314\python.exe -m unittest discover -s tests -v
C:\Python314\python.exe examples\tasks_demo\m2_acceptance.py
C:\Python314\python.exe tools\leak_scan.py
```

The acceptance script uses only `examples/synthetic_corpus/m2_relations.jsonl`
in a fresh temporary data directory. It executes `tasks make`, `tasks submit`,
two `tasks merge` calls per task, and `graph stats`; checks all table counts;
and verifies an explicit location contradiction and subsequent entity resolution.
Initial statistics are 2 nodes / 1 edge. Final statistics are 4 retained nodes /
2 retained edges (including superseded history), with 3 active nodes / 1 active edge.

## M6 quality workflow

Extraction now preserves statements and accepts valid items from partially invalid
agent output. Inspect indexed `errors.json`, retained `accepted.json`, and the
partial/count report in `validation.json`. Cross-node proposition deduplication
folds evidence into existing active claims, respecting corrections. Confidence is
capped by source breadth and keeps the original score as `raw_confidence`.

After extraction and proposition merges, make `cluster_lens` tasks from persisted
records, submit their outputs, then run `tasks merge --all`. The judgment lens
shows chronological topic timelines with speaker, statement, assessed shift and
later evidence-backed outcome. Without accepted clustering, it groups statements
without inventing shifts or outcomes. Every Chinese UI tab explains reading and
correction; sensitive content is hidden by default.

`[tasks].batch_docs` defaults to 50 and `batch_chars` to 40000. Graph statistics
include density, isolation, statement/line counts and confidence distribution.
See [task contracts and offline acceptance](docs/AGENT_TASKS.md#m6-quality-contracts)
for schemas, calibration, limitations and the synthetic-only test commands.
This quality milestone does not add the optional MCP server.

## Local UI v2

Run `python -m atlas serve --data-dir <explicit-data-directory>` to read an
existing graph through the new local, read-only UI. It includes Chinese topic
timelines, on-demand evidence, search, light/dark themes and entity relations.
See [UI v2 usage](docs/ui_v2.md) and [data gaps](docs/ui_v2_data_gaps.md).
The existing offline `build/all` export remains available.
