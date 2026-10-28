# UI v2 · Phase 1

## Boundary and evidence

Implement the requested local read-only web application on `ui-v2`. Keep the
existing offline export and correction workflow intact. No extraction, migration,
paid APIs, private fixtures, or remote publication. References remain excluded
through `.git/info/exclude`. Only schema/field inventories were inspected in the
two authorized stores; the fuller store has persisted judgment lines. The old
page was inspected for structure and CSS, without exporting its embedded content.

## Implementation slices

1. Add a stdlib read-only SQLite reader, explicit response projections, API and
   `atlas serve`. Test synthetic data, correction precedence, sensitivity,
   missing records, evidence integrity, cache headers and write rejection.
2. Build the paper/ink shell, dark theme, server search, hash routes, merged
   topic timelines, vertical detail narrative and on-demand evidence drawer.
   Keep all fetches in one module and only theme preference in localStorage.
3. Add four honest home question cards and an entity page with local relations
   and backlinks. Vendor graph dependencies if the complete local graph fits;
   otherwise document it as next phase. Show missing fields explicitly.
4. Verify light/dark rendering and interactions with fictional data, run the
   full pytest suite and unchanged leak scanner, then make one local commit.

## Decisions

- Reuse persisted judgments, but group only by exact topic identity. Do not
  infer new themes, summaries, stance transitions or correctness totals.
- Unknown dates stay unknown. Preserve source IDs, evidence hashes, stored
  labels and correction precedence; disclose unresolved cross-batch transitions.
- Serve only explicit static assets and API routes. No data-directory browsing,
  source excerpts in list responses, request-body logs or browser content cache.
- Preserve `web/index.html` for offline exports; serve the v2 shell separately.
- Only synthetic fixtures and aggregate schema conclusions enter this repository.

## Round 2

1. Add pure read-time derivations after sensitivity and correction projection:
   latest dated stance, point outcome counts, stored shift counts, dated span,
   safe session names and home aggregates. Preserve ambiguous/unknown values;
   do not write graph tables or execute producers. Verify with fictional fixtures.
2. Centralize display time formatting; contain the horizontal timeline with a
   live visible-position indicator; cap graph zoom and retain fixed node sizes.
   Replace cool dark colors with warm paper/ink colors and amber focus glow.
3. Document every data gap, independent future module contracts and unexecuted
   producer templates. Run full Python/Node acceptance and the unchanged scanner,
   inspect fictional browser renders if available, and attempt one local commit.
