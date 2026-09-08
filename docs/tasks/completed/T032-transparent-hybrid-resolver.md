# T032 completion: transparent hybrid resolver

## Delivered

- Added the registry-backed `transparent_hybrid` resolver with typed child
  configuration, recursive composition, cache identity, and explicit child
  failure policy in `src/abrex/resolvers/hybrid.py`.
- Added `exact_union` and `priority_cascade` strategies, explicit
  `retain_all`/`abstain`/`priority` conflict handling, exact duplicate merge,
  shared-form conflict handling, raw child outputs and per-proposal fusion
  decisions.
- Preserved contributor provenance and named fusion metadata without averaging
  incomparable child confidence or score values.
- Added a reproducible matched development configuration and the tracked
  [`T032-transparent-hybrid-report.json`](../../artifacts/T032-transparent-hybrid-report.json)
  containing all 64 document-level decision traces and artifact fingerprints.

## Evidence

On the identical 64-document T022 smoke slice (143 exact-pair gold units),
the exact-union hybrid combining Schwartz--Hearst with cached native-offset
Ab3P produced 124 TP, 8 FP, 19 FN, precision 0.9394, recall 0.8671 and F1
0.9018. Native-offset Ab3P alone produced 121 TP, 4 FP, 22 FN and F1 0.9030.
The hybrid gained three true positives and recall, but lost precision and had
slightly lower F1. Native-offset Ab3P therefore remains the recommended
resolver for this exploratory slice; no unapproved promotion threshold was
invented.

## Verification

- T032 focused hybrid and resolver-contract tests — 20 passed.
- Strict mypy — passed for the changed resolver, test and report-builder
  files; the repository-wide invocation still reports seven pre-existing
  errors in `scripts/materialize_t022_smoke.py` and
  `scripts/audit_historical_corpora.py`.
- Ruff check and format — passed.
- Repository unit/contract fast gate — 289 passed; the mypy baseline issue is
  unrelated to T032 and was not modified.
- Matched WSL development experiment — 64 records, 0 child failures.
- Per-document report builder — 64 evidence records and 240 proposal decisions.

## Limitations and next task

The result is historical exploratory evidence, not a representative benchmark.
T030 contemporary labels remain provisional and were not used. Conflict and
child-abstention policies remain explicit scientific choices. T033 and T034
are dependency-ready; T034 additionally relies on the already complete T046.
