# T050 source verification and release checks

Status: Engineering implementation complete and verified; research/reviewer
acceptance remains separate.

The source gate now verifies the imported `abrex` origin before formatting,
linting, typing and tests. Child processes receive the checkout `src`
directory explicitly. `scripts/verify_wheel.py` builds and tests a wheel in a
disposable environment, then verifies that the development checkout still
imports from its source tree. Regression coverage for source versus installed
package identity is in `tests/unit/test_quality_gate.py`.

Verification checkpoint, September 9, 2026:

- `env313/Scripts/python.exe scripts/quality_gate.py --python <absolute env313 python>`:
  source import verification, Ruff format/lint, strict mypy and the fast gate
  pass (350 tests).
- Separate wheel smoke passes: the wheel imports from its disposable
  environment, resolves a local document, runs the offline experiment fixture,
  queries the SQLite resource fixture, and the development checkout still
  imports from `src/abrex` afterward.
- The full coverage gate is still below the repository's 95% floor (87.77%,
  356 tests) because the new bounded pilot/reviewer orchestration modules have
  substantial unexecuted branches. This is recorded rather than hidden with a
  threshold or broad exclusion.

The root agent should retain the exact command output and decide whether a
separate coverage-focused task is warranted before release.
