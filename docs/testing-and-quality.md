# Testing and Quality Gate

## Repository-wide fast gate

The exact commands may differ by tooling, but provide a single documented command that runs:

- formatting check;
- linting;
- type checking;
- fast unit and contract tests.

The repository pins mypy and Ruff to the versions used by the pre-commit hooks.
Run all checks through the same interpreter that installed the development
extra, for example `python -m mypy` rather than an unrelated global `mypy`
executable. On Windows, use `.\env313\Scripts\python.exe -m mypy` when the
environment is not activated.

## Environment consistency

Run repository checks through the same Python environment that installed the
development extra. On Windows, either activate `env313` first or use the
explicit interpreter form for every command:

```powershell
.\env313\Scripts\python.exe -m pip install --editable ".[dev]"
.\env313\Scripts\python.exe -m ruff format --check src tests
.\env313\Scripts\python.exe -m ruff check src tests
.\env313\Scripts\python.exe -m mypy
.\env313\Scripts\python.exe -m pytest tests/unit tests/contract
```

The repository mypy configuration intentionally checks both `src` and
`tests`. The pre-commit mypy hook uses `pass_filenames: false` so a commit
containing only a subset of files cannot pass while the full repository fails.
After Ruff applies an automatic fix, inspect `git status` and stage the changed
files before committing.

If pre-commit reports that its SQLite cache is read-only, configure its cache
under a user-writable directory and rerun installation/checks. For example:

```powershell
$env:PRE_COMMIT_HOME = "$env:LOCALAPPDATA\pre-commit"
New-Item -ItemType Directory -Force $env:PRE_COMMIT_HOME | Out-Null
python -m pre_commit install --install-hooks
python -m pre_commit run --all-files
```

This cache setting is machine-local and should not be committed. The project
quality gate itself does not depend on pre-commit's cache location.

A second full gate may include integration/regression tests and coverage.

The repository-wide coverage gate requires at least 95% statement coverage.
This floor keeps the fast gate meaningful while allowing defensive boundary
branches that require unavailable external tools or unusual filesystem
failures; coverage output still reports those branches and component tests
cover the normal and failure contracts.

## Target tooling

Recommended defaults:

- Python 3.13;
- pytest;
- pytest-cov;
- ruff;
- mypy;
- pre-commit;
- build/hatchling or another minimal PEP 517 backend;
- tox or nox only if it adds concrete value.

## Coverage

Do not chase a vanity global percentage. Set a meaningful floor for core pure-Python modules and require tests for new behavior. Critical matching, span, registry, config, and normalization logic should be exhaustively exercised.

## Contract tests

For every plugin protocol, create reusable contract tests that concrete implementations can opt into.

Examples:

- a `Resolver` returns objects with valid document IDs and spans;
- a `CorpusAdapter` yields deterministic record ordering or documents its ordering contract;
- a `Reporter` does not mutate its input result object;
- a `MatchingPolicy` is deterministic and order-invariant if the policy claims to be.

## Golden tests

Use small human-readable fixtures for high-value behavior. Golden outputs should be reviewed rather than generated and blindly accepted.

Appropriate golden targets include:

- canonical serialization for a handful of corpus records;
- Ab3P parsed output for representative constructions;
- exact evaluator match outcomes for difficult multi-pair cases;
- HTML/JSON report structure where stable.

## Property-based testing

Consider Hypothesis for span/matching/config invariants if it meaningfully improves assurance. It is particularly appropriate for interval logic, order invariance, serialization round-trips, and assignment/matching invariants.

## Performance tests

Do not optimize prematurely, but add microbenchmarks or dataset-scale timing once a real bottleneck appears. Performance work must preserve evaluation identity and deterministic behavior.
