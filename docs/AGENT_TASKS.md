# Agent task workflow and M5 frontend

ATLAS is an offline graph and correctable profile shell. Task work lives only in
`ATLAS_DATA_DIR/work/{pending,claimed,submitted,accepted,rejected}/<task_id>/`.
A task directory contains its envelope, input, output schema and instructions;
claiming adds a lease, submission adds output and validation errors when needed.
Use the task directory's schema as authority. Never copy source excerpts into
an evidence pointer: use `{doc_id, span: [start,end], quote_hash}` with the first
12 hexadecimal characters of SHA-256 over the UTF-8 source span.

| Kind | Contract | Current support |
| --- | --- | --- |
| extract_entities | entities, relations, statements; evidence must resolve | make, validate, merge entities/relations |
| resolve_entities | one ADD/MERGE_INTO/NOOP per candidate; existing merge target | make with --input, validate, merge |
| gen_propositions | ADD/UPDATE/SUPERSEDE/NOOP; at least two support pointers; retain counter evidence | make with --node, validate, merge |
| cluster_lens | topic statements, explicit line identity and shift | schema only; no task execution/merge |
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
as the document argument. The judgment lens groups propositions by topic node;
shift stays `none` because no stance-change classification has been accepted.
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
current projected state. M6/MCP is not part of this milestone.

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