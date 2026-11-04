# Original full Atlas with MR-Mem

`--archive-file` selects the original paper-colored application. Existing serve
behavior is unchanged when that option is absent. Private archive data is loaded
from an explicit file and is never part of the web assets or source distribution.

The original lenses remain: review, graph, source reader, state → decision,
consistency, topic and portrait. Existing v4 lenses appear when their projections
are present. The separate sealed folio keeps original texts and prior versions
immutable; annotations save to a separate sidecar using revision checks.

MR-Mem views expose native Search ordering, canonical SBs and their source
pointers, Line membership/edges, mature segment versions, Thread/attention/
semantic relations, said/settled judgments, and lifecycle history. Missing native
structures stay empty. These are storage projections of the paired MR-Mem
contract, not new inference or fact certification.

For an already running native service, use `python -m atlas serve --help`.
Specify `--backend mrmem`, `--data-dir`, `--user-id`, `--mrmem-url`, and optionally
`--mrmem-token-env`, together with archive/folio/state paths. Native storage must
belong to the same instance and user scope as the configured service. Only
loopback HTTP is supported. Tokens are read server-side and never sent to the
browser. Writes require `--runtime-writes`, same-origin requests and the UI
session token. Add always uses the configured user; Flush affects **all pending
users of the native instance**, with an explicit acknowledgment in the UI.

## Preservation import

With the paired MR-Mem source on `PYTHONPATH`:

```powershell
python examples/import_legacy_archive.py --archive-file <archive.json> --out-dir <new-native-dir> --user-id <user>
python examples/serve_original.py --archive-file <archive.json> --folio-file <folio.json> --data-dir <new-native-dir> --state-dir <sidecar-dir> --user-id <user>
```

The destination must not exist. Import verifies the full archive chain, excludes
sensitive quote rows, preserves ordering and session grouping, and imports only
existing insight cards as explicitly labeled historical projections. A source
record is a **verified historical quote extract**, not an entire original chat
message. Day-only source precision remains day-only. `known_at` records the
native import commit; the old compile time remains unknown. No models run and
no Lines/Threads/relations are invented. This extension targets MR-Mem bb0d296;
it uses that version's source-store schema, so revalidate before upgrading.

The launcher starts a real native host and the UI. Its default preservation mode
uses native raw retrieval without embeddings, HyDE, decision calls or compile
before search. Mutations are disabled because no compiler is configured. To use
a production provider, pass an explicit `--runtime-config` file; enable writes
separately with `--runtime-writes`. Its configured native read policies may call
providers on explicit searches. The launcher generates a local authentication
token in memory. Do not point a second runtime writer at the same dataset.

## Validation

Python tests cover source scoping, fingerprint invalidation, date precision,
immutable originals, revision conflicts, and same-origin mutation protection.
The import test runs when paired MR-Mem source is available.

```powershell
python -m pytest -q -p no:cacheprovider
node --test tests/*.test.mjs
$env:ATLAS_TEST_BROWSER='1'
$env:ATLAS_TEST_PYTHON='python'
node --test tests/browser-original.test.mjs
```

The optional Chrome test starts its own fictional native runtime and exercises
all original lenses, real Add/Search/Flush protocol handling, source drawers,
mobile overflow, and annotation persistence. Its deterministic compiler validates
integration mechanics only; it does not measure model or retrieval quality.
