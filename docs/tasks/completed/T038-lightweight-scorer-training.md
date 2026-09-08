# T038 completion: lightweight scorer training

## Delivered

- Added the registry-backed `logistic_regression` scorer with typed learning
  rate, iteration, L2 and class-weight settings.
- Implemented deterministic CPU full-batch optimization without adding a
  runtime dependency, while reusing the existing scorer executor, calibration,
  selection and persistence contracts.
- Persisted learned weights, bias and feature-schema fingerprint; changed
  schemas and tampered model artifacts are rejected.
- Added the explicit smoke configuration and report at
  `configs/benchmarks/T038-logistic-regression.yaml` and
  `docs/artifacts/T038-logistic-regression-report.json`.

## Verification

- Tiny separable deterministic training test: passed.
- Save/load/predict and schema/tamper regression tests: 2 passed.
- Repository unit/contract fast gate: 301 passed.
- Ruff, strict mypy and diff checks: passed.

## Scientific limitations

The available T037 labels are provisional and too small for a credible
gold-only versus gold-plus-silver development comparison. The report records
candidate-recall ceiling, precision/recall, runtime and comparison fields as
pending rather than fabricating values. No final holdout data were used, and
the explicit 0.5 smoke threshold is not a scientifically selected threshold.

## Next ready task

T039 is ready to provide bounded controlled iteration, rollback and stopping
mechanics around the evidence and scorer components.
