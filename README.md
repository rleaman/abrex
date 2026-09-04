# Abbreviation Resolution Project

A modular framework for abbreviation resolution and expansion extraction in scientific text.

## Development

The project targets Python 3.13 and uses a `src/` layout. Create an environment and install the package with development tools:

```console
python -m pip install --upgrade pip
python -m pip install --editable ".[dev]"
```

Run the fast quality gate (format check, lint, type check, and unit/contract tests)
from the same Python environment used to install the project:

```console
python -m ruff format --check src tests; python -m ruff check src tests; python -m mypy; python -m pytest tests/unit tests/contract
```

On Windows, an unactivated environment can use the interpreter explicitly:

```console
.\env313\Scripts\python.exe -m ruff format --check src tests
.\env313\Scripts\python.exe -m ruff check src tests
.\env313\Scripts\python.exe -m mypy
.\env313\Scripts\python.exe -m pytest tests/unit tests/contract
```

The configured mypy scope is the full repository source and test tree, and
pre-commit runs that same scope. If its cache is read-only, set
`PRE_COMMIT_HOME` to a writable user-local directory before installing hooks;
see `docs/testing-and-quality.md`.

The development tool versions are pinned to the versions used by the
pre-commit hooks. Reinstall the development extra after changing environments:

```console
python -m pip install --editable ".[dev]"
```

Run the full test gate with coverage:

```console
python -m ruff format --check src tests; python -m ruff check src tests; python -m mypy; python -m pytest --cov --cov-report=term-missing
```

Resolve configuration layers and print the deterministic result:

```console
python -m abrex config resolve configs/base.yaml
```

Pre-commit runs the formatting, lint, and type checks locally:

```console
python -m pre_commit install
python -m pre_commit run --all-files
```

Task completion notes are stored under `docs/tasks/completed/` and record changes, verification commands, and unresolved issues. Scientific behavior is intentionally deferred to the numbered tasks that define it.
