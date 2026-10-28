# UI v2 Phase 1 acceptance

## Automated verification

- Canonical repository suite: **102 passed**, including 11 new API/server tests;
  pytest additionally reports **27 passed subtests**. No test skips.
- `node --test tests/ui_v2.test.mjs`: **4 passed**. Covers unknown fields and
  escaping, batch-boundary honesty, offline fCoSE layout, late evidence responses,
  drawer cleanup, page departure, keyboard focus and theme-only persistence.
- Unchanged `tools/leak_scan.py`: **0 hits** over the complete acceptance checkout.
- `git diff --check`: passed. No changes to the scanner or hooks.

The Python application uses only the standard library. The required pytest runner
was installed in an ignored disposable tools directory; it is not a runtime or
committed dependency. Graph distributions were fetched in one npm pack batch.
All fixtures and the running demo are fictional.

## Environment limits and verification scope

The original checkout denies reads of an existing tracked synthetic fixture.
To run the whole-repository scanner without exceptions, acceptance uses an
isolated local Git clone under ignored demo output, populated with the committed
baseline plus only this task's files. All 26 task files were compared byte for
byte with the original workspace. No protected working file is replaced.

**Local commit is blocked:** Git cannot create `.git/index.lock` in the acceptance
checkout because of filesystem permissions. Staging and commit both failed;
the pre-commit hook was not reached. It remains configured and unchanged, and
was not bypassed. No commit was created, the original branch was not advanced,
and no push occurred. All implementation changes remain in the original workspace.

The browser automation host is unavailable. Native Chrome access was explicitly
denied by the computer-use tool. Consequently **rendered light/dark/mobile visual
acceptance is not confirmed**. Source and reference images were reviewed; JS
tests exercise the controller with a simulated DOM and the graph headlessly.
Those checks do not substitute for a real browser render. The fictional demo
command in `ui_v2.md` is ready for that review.

## Delivered and deferred

Delivered: read-only local server/API, correction-aware projections, sensitive
filtering, Chinese shell, search, hash routes, theme preference, merged topic
timelines, evidence drawer, four home cards, entity graph and backlinks.

Absent semantic fields remain explicit empty states, catalogued in
`ui_v2_data_gaps.md`. Editing, full-text corpus search, topic hierarchy, multi-hop
controls and unsupported summary/accuracy/stability inference are outside Phase 1.

## Round 2 acceptance

Implemented the full Round 2 code and documentation scope on `ui-v2`, based on
`b9cdb3d`. No private stores were read, no agents/extraction jobs or paid APIs ran,
no dependencies were downloaded, and no store schemas or merge logic changed.
Existing vendored graph dependencies were sufficient. All new fixtures are fictional.

### Verification

- `C:/Python314/python.exe -m pytest -q`: **108 passed, 27 subtests passed**,
  no skips, failures or warnings in the final run (59.06 seconds).
  The existing ignored pytest installation is supplied through `PYTHONPATH`.
  `PYTEST_ADDOPTS` relocates only the unwritable cache to ignored demo output;
  no tests are excluded. Explicit demo environment paths are set.
- `node --test tests/ui_v2.test.mjs`: **9 passed**, no skips or failures.
  Covers calendar validation, common formatting, partial/long timeline positions,
  scroll and resize updates, observer cleanup, point-to-detail jumps, capped
  one/two-node graph configuration, derived-value escaping, warm CSS palette,
  offline graph layout, and evidence cleanup/theme-only persistence.
- Unchanged `tools/leak_scan.py`: **0 hits**, 0 denylist terms, in the complete
  local acceptance checkout `_demo_out/.ui-v2-r2-acceptance`.
- `git diff --check`: passed. Scanner and pre-commit files are unchanged.

The direct scanner in the original worktree cannot read the existing tracked
synthetic `examples/synthetic_corpus/life_notes.jsonl` (PermissionError). To run
it over the complete source tree without exceptions, a local clone of HEAD was
created in ignored demo output and overlaid with all 17 Round 2 files. Each task
file is byte-compared to the original after the final edits. This scan result
applies to that complete source snapshot; it does not claim that the original
worktree's inaccessible fixture was read. The protected file is unchanged.

### Delivery limits

**Local commit blocked:** `git add` failed with `Unable to create .git/index.lock:
Permission denied`. Staging failed before pre-commit could run; the hook remains
configured as `.githooks` and was not bypassed. No local commit or push was made.
All 17 files remain in the original worktree for review.

**Rendered visual acceptance unverified:** the browser access host is unavailable;
Computer Use also explicitly denied access to Google Chrome. No alternate browser
control was used to bypass that denial. DOM simulation and CSS assertions establish
logic/configuration coverage, not rendered desktop/mobile layout or visual quality.
The existing fictional demo commands in `ui_v2.md` remain usable for manual review.

### Changed files

- `atlas/web_data.py`, `atlas/web_derive.py`: labelled read-time aggregates and
  safe session-name fallback, after correction/sensitivity projection.
- `web/js/views.js`, `web/js/app.js`, `web/js/time.js`, `web/js/timeline.js`,
  `web/js/graph.js`, `web/theme.css`: shared time formatting, derived UI facts,
  timeline containment and position indicator, bounded graph zoom and warm theme.
- `tests/test_server.py`, `tests/test_web_derive.py`, `tests/ui_v2.test.mjs`:
  synthetic aggregate, API, empty-state, privacy, correction and UI regression tests.
- `docs/ui_v2.md`, `docs/ui_v2_plan.md`, `docs/ui_v2_data_gaps.md`,
  `docs/ui_v2_gap_plan.md`, `docs/ui_v2_task_templates.md`,
  `docs/ui_v2_acceptance.md`: behavior, every-gap decisions, independent module
  proposal, unexecuted producer contracts and this acceptance record.

Derived fields: latest dated stance and its source IDs, supported/contradicted/
unknown counts, explicit shift count, known time span, safe source-session display
name, and home line/point/confirmed/pending counts. Summaries, topic hierarchy,
fixed stance vocabulary, accuracy, stability and other semantic gaps remain
unproduced as required; their plans and text task templates are delivered.


## Round 4 acceptance

Implemented on `ui-v2`, baseline `f10d761`. No MR-Mem workspace was opened or
connected, no agent/LLM jobs or paid APIs ran, and no dependencies were downloaded.
Round 2 functionality, documents and templates remain. Source fixtures are fictional.

### Implemented scope and changed files

- `atlas/backends/{__init__,base,atlas_sqlite,mrmem}.py`, `atlas/server.py`:
  eight-method read-only protocol and dispatch, ATLAS wrapper, unconnected MR-Mem
  skeleton, validated char_span/message_paragraphs types and fake-backend coverage.
- `atlas/web_data.py`: additive refs in evidence payloads; entity metadata
  backlinks and suggestions; token-bound mention requests share the verified drawer
  slice path. Existing linked statements, propositions and relationships remain.
- `atlas/web_derive.py`, `atlas/templates/pending_question.txt`, `web/js/views.js`:
  labelled accuracy/stability, pending priority and template questions, counts,
  empty states and lazy mention actions. No new graph facts or semantic tables.
- `atlas/entities/{__init__,index}.py`, `atlas/cli.py`: explicit-path, count-only
  CLI commands; independent mentions/suggestions tables. Names/aliases only in
  matched_alias; no corpus body/context columns. Suggestions never perform merges.
- `tests/test_backends.py`, `tests/test_entities.py`, `tests/test_web_derive.py`,
  `tests/ui_v2.test.mjs`: route parity, injected paragraph backend over HTTP,
  derived thresholds/order/corrections, index privacy/Unicode/short-name guards,
  unchanged graph/corpus bytes, stale evidence rejection, CLI and rendering tests.
- `docs/for_mrmem_requirements.md`: all eight Chinese requirements with UI usage,
  temporary substitute and desired interface shapes, including both supplied
  LCE design conflicts. No MR-Mem implementation or architectural decisions.
- `docs/ui_v2.md`, `docs/ui_v2_plan.md`, `docs/ui_v2_data_gaps.md`,
  `docs/ui_v2_gap_plan.md`, `docs/ui_v2_task_templates.md`, this acceptance file:
  current contracts and explicit supersession notes preserving historical proposals.

### Automated results

- `C:/Python314/python.exe -m pytest -q tests`: **121 passed, 27 subtests passed**,
  no failures or skips; 62.81 seconds in the final full run. Existing ignored pytest
  installation supplied via PYTHONPATH; cache and demo environment paths explicitly
  point to ignored demo output. No new runtime dependencies.
- `node --test tests/ui_v2.test.mjs`: **12 passed**, no failures/skips.
- Unchanged leak scanner: **0 hits**, 0 denylist terms, across the complete source
  acceptance snapshot. Original worktree scan fails on PermissionError reading the
  pre-existing tracked `examples/synthetic_corpus/life_notes.jsonl`. Snapshot is
  a Git archive of committed HEAD with all 23 changed/new task files overlaid and
  byte-compared. Every snapshot source file is passed to the unchanged scanner;
  nothing is excluded to obtain the clean result. Protected working fixture is
  untouched. Snapshot is `_demo_out/ui-v2-r4-acceptance`.
- `git diff --check`: passed. Hooks and leak scanner unchanged.
- Fictional CLI smoke using `seed_ui_v2`: index reports **2 nodes, 3 documents,
  0 mentions**; suggestions reports **2 nodes, 0 suggestions**. The seed's full
  entity names/alias do not occur verbatim in its corpus. The separate entity test
  fixture exercises nonempty output: **6 visible nodes, 3 documents, 18 mentions**,
  all three suggestion rules, and idempotent counts with graph/corpus byte equality.

### Incomplete environment-dependent acceptance

The designated sample-copy directory already existed, so the original sample
was not copied again or written. Both requested CLI commands were attempted on
that copy. Both failed with SQLite **SQLITE_CANTOPEN** at the explicit writable
connection for `entities.sqlite` (index.py, not graph/corpus). The directory is
outside this session's writable roots. No sample counts were produced; fictional
smoke counts above are not replacements for those requested sample counts.
No private content was printed or copied into this repository.

**Local commit blocked:** named-file staging failed with
`Unable to create .git/index.lock: Permission denied`. Pre-commit was not reached;
no hooks were disabled or bypassed, no commit was created and no push occurred.
All changes remain in the original worktree for review.

**Rendered visual acceptance unverified:** opening the local fictional demo with
the browser tool returned “The browser access host is unavailable”. JS rendering,
controller and offline graph tests pass, but no desktop/mobile screenshot is
claimed. The documented demo is available for a later browser review.
