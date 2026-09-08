# T040 completion: research validation and ablation campaign

## Delivered

- Added the frozen T040 protocol at
  `configs/benchmarks/T040-campaign-protocol.yaml`, fixing the corpus,
  exact-pair metric, seeded bootstrap, holdout prohibition, budget and
  selection rule before campaign reporting.
- Added `scripts/build_t040_campaign_report.py`, which fingerprints the
  existing T031, T032, T034 and T038 evidence artifacts and emits a
  reproducible campaign audit.
- Added the tracked audit at
  `docs/artifacts/T040-campaign-audit.json` with standalone, hybrid, lexical
  and scorer statuses plus the release-candidate decision.

## Decision

The bounded T022 evidence retains native-offset Ab3P as the exploratory
release candidate: F1 0.9030 versus 0.9018 for the transparent hybrid,
0.8527 for Schwartz--Hearst and 0.7790 for PLODv2 pairing. T034 lexical
evidence produced no recall gain, and T038 remains a plumbing smoke. No
production improvement is supported.

## Limitations

T030 contemporary labels remain provisional; no approved independent,
adequately powered development/holdout set was available. The final holdout
was not accessed. Aggregate resource overlap and work-scale runtime remain
unknown, so this is an honest bounded campaign conclusion rather than a claim
of general resolver accuracy.

## Verification

- Campaign report generation and input fingerprinting: passed.
- Repository unit/contract fast gate: run before commit.
- Ruff, strict mypy and diff checks: passed.

## Next ready task

T042 is dependency-ready only after the required work-scale corpus and
validation decisions; T041 infrastructure is already complete. The remaining
T042–T045 work must preserve this no-promotion decision unless new approved
evidence is supplied.
