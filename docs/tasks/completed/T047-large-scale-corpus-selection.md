# T047 completion note: bounded large-scale corpus selection proposal

Status: Complete for the deterministic selector and bounded metadata-frame
proposal. Final work-scale limits and scientific corpus approval remain open.

## Delivered

- Added typed corpus-frame, article-group, pool and work-scale-limit models in
  `src/abrex/literature/corpus_selection.py`.
- Added deterministic identifier/content grouping, source-version retention,
  eligibility/exclusion accounting, protected-group closure and seeded broad
  selection.
- Added a separately denominated enriched structure pool and explicit final
  tagged-release membership; enriched examples cannot be mistaken for broad
  population prevalence.
- Added `abrex literature select`, a YAML proposal, a local metadata-frame pilot
  and a frozen-manifest/report pair.

## Evidence and artifacts

The five-record pilot reconciles to four article groups: one broad 2018 group is
selected, one tagged 2014 full-text group is protected, one unavailable group is
excluded and two groups are outside the configured 2018--2024 range. The frame
contains abstract/full-text counterparts, and grouping keeps them together. The
manifest fingerprint is
`cb64eb2166c037fd7e5f8ac52bbbecee05045885aca29e321672de1129923e1f`.
See [T047-corpus-selection-report.json](../../artifacts/T047-corpus-selection-report.json).
The generated manifest remains ignored under `.artifacts/T047/`.

## Verification

- Focused suite: `2 passed`, covering deterministic replay, counterpart grouping,
  protected holdout closure, broad/enriched role separation and failure paths.
- Pilot command: `abrex literature select --config configs/literature/T047-corpus-selection.yaml`.
- No bulk retrieval or resolver processing was run.
- Repository-wide fast gate: `254 passed`; full gate: `258 passed`, total
  coverage `95.05%`; ruff format/check, mypy and `git diff --check` pass.

## Limitations and next decisions

This is a concrete proposal, not a production corpus freeze. The supplied frame
does not yet carry journal/domain, reliable reuse class or complete version and
structure metadata. The T030 evaluation fixture also needs identifier-level
reconciliation with the eventual final frame. Before T042, approve the snapshot,
years, inclusion/reuse rules, pool volumes and measured T041 cost envelope.

## Next ready task

T023 remains blocked by the missing PLODv2 runtime/dependencies. T031 is not
ready until T024 exists; T034 and later resource/training work should consume
this proposal only after T033/T046 and the remaining dependency chain is ready.
