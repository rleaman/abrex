# Reproducible development environments

ABREX targets Python 3.13. The checked-in
[`requirements-dev.lock`](../requirements-dev.lock) is an exact snapshot of
the runtime and development packages used for verification. It deliberately
does not include the editable `abrex` checkout itself.

## Fresh Windows or Linux setup

From the repository root, create an environment and install the snapshot:

```console
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install --requirement requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --editable .
```

Linux:

```bash
.venv/bin/python -m pip install --requirement requirements-dev.lock
.venv/bin/python -m pip install --no-deps --editable .
```

Using `--no-deps` for the editable install ensures the lock, rather than the
open-ended ranges in `pyproject.toml`, determines installed versions. The
lock contains only cross-platform core/development tooling; optional Flair or
other neural dependencies are not required to import or test `abrex`.

## Quality gates

The same fail-fast Python runner works on Windows and Linux:

```console
python scripts/quality_gate.py --self-test
python scripts/quality_gate.py
python scripts/quality_gate.py --full
```

The runner creates `.pytest-tmp` before pytest starts and returns the first
failing command's nonzero status. It runs only offline unit, contract,
regression, and package checks; live Ab3P and model jobs remain separate,
explicitly skippable workflows/tasks.

## Regenerating the snapshot

After intentionally changing dependencies, install the editable development
extra in the environment being recorded, then run:

```console
python -m pip install --editable ".[dev]"
python scripts/update_dependency_lock.py
```

Review the resulting diff, verify both supported operating systems, and keep
the lock and `pyproject.toml` changes together. The current verification
snapshot used Python 3.13.14, Ruff 0.11.13, mypy 1.15.0, pytest 8.4.2,
pytest-cov 6.3.0, and coverage 7.16.0.

## Data and historical claims

Historical corpus files and generated outputs stay outside version control.
The older BADREX completion notes describe historical local states; the
current BADREX URLs are unavailable and no BADREX configs are present in the
current checkout. Do not treat old run counts or local-data claims as current
verification, and do not install datasets for the core quality gate.
