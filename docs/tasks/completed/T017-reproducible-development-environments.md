# T017 completion note

## Changed

- Added `requirements-dev.lock`, an exact Python 3.13 development snapshot
  captured from `env313`, plus `scripts/update_dependency_lock.py` for reviewed
  regeneration.
- Added `scripts/quality_gate.py`, a cross-platform fail-fast gate that creates
  `.pytest-tmp` before pytest and preserves each child command's exit status.
  Its `--self-test` exercises the failure path.
- Added unit coverage for temporary-parent creation and stop-on-first-failure.
- Added `.github/workflows/quality.yml` for the offline core package matrix on
  Windows and Linux. It installs only the lock and editable core package;
  Ab3P/model jobs remain separate and optional.
- Updated the README and testing documentation with the locked install and
  canonical gate commands. Reconciled historical-build documentation so
  unavailable BADREX variants are not presented as current configurations.
  Applied the same clarification to the historical download documentation.
- Generated temporary pytest output under `.pytest-tmp/`; it is ignored and
  is not a deliverable.

## Verification

All commands below used `env313\Scripts\python.exe` (Python 3.13.14):

- `env313\Scripts\python.exe -c "import abrex; print(abrex.__name__)"` — passed.
- `env313\Scripts\python.exe -m abrex --help` — passed.
- `env313\Scripts\python.exe scripts/quality_gate.py --self-test` — passed;
  the child returned 17 and the gate reported success for the expected failure.
- `env313\Scripts\python.exe scripts/quality_gate.py` — passed: Ruff format,
  Ruff lint, mypy over 109 files, and 167 unit/contract tests.
- `env313\Scripts\python.exe scripts/quality_gate.py --full` — passed: 171
  tests and 95.72% coverage, above the configured 95% floor.
- `git diff --check` — passed.

The locked verification versions include Ruff 0.11.13, mypy 1.15.0, pytest
8.4.2, pytest-cov 6.3.0, coverage 7.16.0, and pydantic 2.13.5. No dataset,
model, Ab3P executable, or neural dependency was installed or run.

## Artifacts and unresolved validation

- Dependency artifact: [`requirements-dev.lock`](../../requirements-dev.lock).
- Gate and lock workflows: [`scripts/quality_gate.py`](../../scripts/quality_gate.py)
  and [`scripts/update_dependency_lock.py`](../../scripts/update_dependency_lock.py).
- CI workflow: [`quality.yml`](../../.github/workflows/quality.yml).

The clean-environment install and the Windows/Linux matrix are documented and
configured but were not independently replayed in this local Windows session;
hosted CI remains the required cross-platform confirmation. Scientific
validation is unchanged: this task provides no real Ab3P, corpus, or model
evidence. Historical BADREX run counts and local-data claims remain historical
evidence only, consistent with the state audit.

## Next task

T018 is ready: build and verify the real Ab3P runtime in the existing Ubuntu
WSL environment.
