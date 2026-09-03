# Abbreviation Resolution Project

A modular framework for abbreviation resolution and expansion extraction in scientific text.

## Development

The project targets Python 3.13 and uses a `src/` layout. Create an environment and install the package with development tools:

```console
python -m pip install --upgrade pip
python -m pip install --editable ".[dev]"
```

Run the fast quality gate (format check, lint, type check, and unit/contract tests):

```console
python -m ruff format --check src tests; python -m ruff check src tests; python -m mypy; python -m pytest tests/unit tests/contract
```

Run the full test gate with coverage:

```console
python -m ruff format --check src tests; python -m ruff check src tests; python -m mypy; python -m pytest --cov --cov-report=term-missing
```

Pre-commit runs the formatting, lint, and type checks locally:

```console
python -m pre_commit install
python -m pre_commit run --all-files
```

Task completion notes are stored under `docs/tasks/completed/` and record changes, verification commands, and unresolved issues. Scientific behavior is intentionally deferred to the numbered tasks that define it.
