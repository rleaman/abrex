# T039 completion: controlled evidence and model iteration

## Delivered

- Added typed iteration limits and development guards in
  `abrex.experiments.iteration`.
- Added immutable stage records for evidence, dictionary, pattern, label and
  model outputs, including payload fingerprints, parent identities and
  evidence lineage.
- Added deterministic checkpoint manifests, input-snapshot invalidation,
  idempotent resume, duplicate/self-support rejection, no-gain stopping and
  best-iteration rollback.
- Added a two-iteration fixture covering self-support rejection, checkpoint
  readback and changed-input invalidation.

## Verification

- Focused controller tests: 2 passed.
- Repository unit/contract fast gate: run before commit.
- Ruff, strict mypy and diff checks: passed.

## Scientific limitations

The controller smoke demonstrates guard and lineage mechanics only. It does
not claim that iteration improves resolution, and it does not select from
locked final labels. Real dictionary/pattern/model stage builders must supply
their own immutable payload artifacts and T029-compatible development policy.

## Next ready task

T040 is ready for the research validation and ablation campaign, using the
explicit baselines and stopping/rollback mechanics now available.
