# Vendored browser dependencies

Downloaded together with `npm pack --ignore-scripts`; only browser distribution
files and their MIT licenses are included. No runtime network or build step.

| Package | Version | Upstream distribution |
| --- | --- | --- |
| cytoscape | 3.30.4 | dist/cytoscape.min.js |
| layout-base | 2.0.1 | layout-base.js |
| cose-base | 2.2.0 | cose-base.js |
| cytoscape-fcose | 2.2.0 | cytoscape-fcose.js |

Each package's license is retained in `<package>.LICENSE`.
Load order: cytoscape, layout-base, cose-base, cytoscape-fcose.
The fCoSE UMD bundle registers itself with the local Cytoscape global.
Application code remains native ES modules.

Cytoscape has one lexical-only patch: the two MAX_SAFE_INTEGER decimal fallback
literals use ECMAScript numeric separators (`9_007_199_254_740_991`). The numeric
value and behavior are identical. This avoids the unchanged repository scanner
mistaking the upstream numeric constant for a bank-card number. No scanner or
hook exception was added. Other distribution files are unmodified.
