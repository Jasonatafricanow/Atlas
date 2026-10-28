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
