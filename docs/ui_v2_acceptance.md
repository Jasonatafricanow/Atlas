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
