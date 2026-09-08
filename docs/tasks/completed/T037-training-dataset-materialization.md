# T037 completion: leakage-safe candidate training datasets

## Delivered

- Added typed `LabelConstructionConfig`, `CandidateLabel` and
  `TrainingDatasetArtifact` in `abrex.scorers.datasets`.
- Added deterministic materialization from candidate artifacts, canonical
  documents, corpus records and a configured feature set.
- Complete gold span pairs produce positive labels; unmatched candidates do
  not become negative under partial annotation. Optional binary silver labels
  require an explicit caller-owned map and preserve evidence IDs.
- Feature extraction is performed before and independently of label joining;
  document-level split assignment is supplied through `SplitManifest`.
- Dataset and candidate fingerprints plus feature schema and split metadata
  are retained on the materialized artifact.

## Verification

- Partial-gold and explicit-silver regression test: passed.
- Repository unit/contract fast gate: 299 passed.
- Targeted strict mypy, Ruff and diff checks: passed.

## Scientific limitations

The bounded T030 pilot remains provisional and does not certify training-label
quality. No final evaluation rows are repurposed by this tooling, but callers
must supply a correctly frozen T029-compatible split manifest and silver map.
No automatic negative mining, PLOD overlap correction, or article-group
inference is performed.

## Next ready task

T038 is ready to add and evaluate the explicitly requested lightweight scorer
on these materialized datasets.
