# ATLAS core

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
- **Corrections**: `data_dir/corrections.jsonl` (`{"doc_id":..,"verdict":"wrong","note":..}`), shown on cards.

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
and an offline extraction queue. It does not merge task outputs into the graph,
run external agents, generate profiles, or change the frontend.

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
Graph statistics remain zero until graph records are written; accepted outputs
are not merged in M1. Without `--config`, queue and graph commands require an
explicit `ATLAS_DATA_DIR`; they do not discover private configuration or data.

Workers use `tasks claim <id> --owner demo-worker --lease-seconds 300`, then
`tasks submit <id> --file output.json --owner demo-worker`. `tasks reap` returns
expired claims to pending. `tasks validate <id>` rechecks a submitted result
against the document Store. All queue mutations use an exclusive lock.

Task workspaces live under `ATLAS_DATA_DIR/work/<state>/`. Logical IDs contain a
colon; directory names encode it as `__` for Windows compatibility. Extract tasks
contain at most 50 documents. Repeating make reuses unchanged tasks. Changed
content under the same document IDs is rejected as a collision; new source
versions must receive new document IDs. Evidence spans are Unicode character
indices with an exclusive end, and hashes use UTF-8. The built-in validator
covers the JSON Schema subset used by all shipped contracts without dependencies.
`[tasks].forbidden_terms` can override the extraction wording blacklist; the
selected terms are captured in each task input.
