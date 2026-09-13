# T057 Freeze the development guidelines and challenge views

Status: Completed September 13, 2026. The final evidence bundle is frozen after
completion of the bounded human review and a separate acceptance audit.

## Delivered

- Added the dated scientific-model iteration
  [development challenge freeze](../../scientific-model/2026-09-12-development-challenge.md)
  without changing the September 10 iteration.
- Froze the versioned
  [T057-v1 development guideline supplement](../../annotation-guidelines/2026-09-12-development-supplement-v1.md),
  including strict inclusion, evidence fragments, reconstruction, source
  errors, lists/ratios, abbreviation-label boundaries, uncertainty, passage
  completeness and later-prediction handling.
- Added a deterministic typed materializer and reproduction script. They
  validate the T052 packet, both annotation states, exact source spans and the
  linked T053 inventory/audit identities before writing outputs. Accepted
  mechanical corrections are content-addressed, expected-value checked and
  recorded on the affected derived relations.
- Preserved the September 10 T052 baseline. The later user-returned state is a
  separately hashed input, not an in-place historical rewrite.

## Frozen evidence

The [T057 bundle](../../../evidence/T057/README.md) records:

- 60 ledgered cases and all 111 current relations;
- 20 T053-selected challenge cases;
- 72 relations in the challenge selection: 59 strict, 13 diagnostic and zero
  unresolved;
- all 20 challenge cases eligible under the complete-case policy; and
- six acceptance-audit repairs for evident span direction, boundary, overlap or
  duplicate-evidence mistakes, with the user annotation file left unchanged.

The initial small scoreable subset exposed a reviewer usability defect: the prior UI
reported support review as complete without requiring the three policy fields,
and it did not provide a clear bounded 20-passage completion route. The
corrected reviewer and [human review guide](../../t057-human-review-guide.md)
then supported completion of all 20 passages. The final checker result was
20/20 complete with zero remaining decisions.

The manifest identifies the T052 packet and baseline, the user's returned
annotation state (SHA-256
`15c8e59232041f0999290f426348e3777d15c3562a76eccf76b454e023a01533`),
both T053 inputs, guideline/model documents and every generated artifact.
The separate accepted-corrections file is also hashed and binds itself to that
exact annotation-state hash.

## Reproduction and checks

```powershell
.\env313\Scripts\python.exe scripts\build_t057_development_views.py
```

- Focused T054–T057 review-contract tests after final acceptance: **14 passed**.
- Ruff format and lint: **passed**.
- Mypy: **no issues in 177 source files**.
- Canonical fast gate: **368 passed**, with source-import, Ruff and mypy checks
  also passing.
- The full suite ran **372 tests successfully**. Its repository-wide coverage
  check remains at the pre-existing baseline of **87.44%**, below the configured
  95% target; the task-required fast gate is green and T057 introduced no test
  failure.
- `git diff --check`: **passed**; only existing Windows line-ending warnings
  were reported.

This bundle is assisted development evidence, not independent gold or an
untouched test set. No relaxed metric was invented and no method run was
started. T058 may proceed against the frozen named strict view; it must not turn
the diagnostic view or the 36 unresolved non-challenge relations into ordinary
metric denominators.
