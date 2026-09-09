# T050 Repair source verification and isolate release checks

Status: Ready and authorized. Implementer: GPT-5.6 Luna.

## Outcome and dependencies

Make the documented gate reliably test the current source checkout and restore its required 95% coverage. Read [current work](../CURRENT_WORK.md), [September 8 audit](../project-status-review-2026-09-08.md), `scripts/quality_gate.py`, `pyproject.toml`, the CI workflow and relevant testing/release docs. Preserve unrelated work.

## Implementation

1. Add a regression test for source-versus-installed-wheel import identity. Make both gate subprocesses and any nested test subprocesses use the intended checkout explicitly; print/verify package origin. Do not merely hide duplicate files from coverage.
2. Repair meaningful uncovered behavior with focused tests, including failure paths where useful. The audit's source run passed 311 tests but had 94.18% coverage. Do not lower the threshold, add broad exclusions or claim the mixed-install 52.15% as actual source coverage.
3. Keep wheel installation/smoke in a separate disposable environment; never overwrite the development package to test the release. Verify local document resolution, a documented offline experiment and resource query as supported by existing fixtures. Resolve prerequisites through the current environment or bounded dependency setup, not unrelated environment rewrites.
4. Update canonical testing/release commands and current status. Do not rewrite historical results or claim research release completion.

## Acceptance and verification

- Canonical fast and full source gates pass from the normal documented invocation, even when an installed wheel exists. Report tested package path and actual counts/coverage.
- Separate wheel smoke runs against the wheel, not editable source, without changing development import identity.
- Regression tests substantiate the import isolation fix. Ruff formatting/lint, strict mypy, fast gate, full coverage gate and diff checks pass.

## Deliverables

Scoped code/tests/docs and `completed/T050-source-verification-repair.md` with exact commands/results. Update task index. Then continue to T051 under the existing authorization. Other audit findings are not prerequisites to this task.
