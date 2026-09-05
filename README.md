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

The `pytest` portion is what actually runs the tests; Ruff and mypy only
check formatting, lint, and types. To run the tests alone, use
`python -m pytest` (or `.\env313\Scripts\python.exe -m pytest` on Windows).

Resolve configuration layers and print the deterministic result:

```console
python -m abrex config resolve configs/base.yaml
```

## Historical datasets

Download the user-managed historical corpus sources listed in the YAML
manifest with:

```console
python -m abrex datasets download configs/historical-datasets.yaml
```

The downloader uses polite sequential requests, retries transient failures,
writes atomically, verifies configured checksums, safely extracts archives,
and records a `.download.json` provenance file for each completed source.
Downloaded files are placed under `data/raw/historical/` for use with the T011
corpus adapters. See `docs/historical-downloads.md` for source-format and
licensing details.

Build the locally available historical corpora through the shared canonical
pipeline with `abrex corpus build --config`:

```console
abrex corpus build --config configs/corpora/ab3p.yaml
abrex corpus build --config configs/corpora/bioadi.yaml
abrex corpus build --config configs/corpora/medstract.yaml
abrex corpus build --config configs/corpora/schwartz_hearst.yaml
```

Or build the configuration-driven historical group:

```console
abrex corpus build-all --group historical
```

See [historical build documentation](docs/historical-builds.md) for the
download -> build -> resolve -> evaluate workflow and unavailable variants.

Pre-commit runs the formatting, lint, and type checks locally:

```console
python -m pre_commit install
python -m pre_commit run --all-files
```

Task completion notes are stored under `docs/tasks/completed/` and record changes, verification commands, and unresolved issues. Scientific behavior is intentionally deferred to the numbered tasks that define it.

# Local workspace cleanup

OneDrive can leave Python and pytest temporary artifacts behind when a process or sync operation holds a file open. The repository includes a conservative cleanup helper:

```powershell
.\scripts\Cleanup-Workspace.ps1
.\scripts\Cleanup-Workspace.ps1 -DeleteSafe
```

The first command is audit-only. The second removes only generated caches and test/coverage output classified as `SafeToDelete`. It writes a timestamped JSON report. Project data (`data/`) and Python environments (`env313/`, `.venv/`, `venv/`, `env/`) are reported as `ReviewBeforeDelete`, never removed automatically; tracked files are protected as well. A failed deletion is retained in the report with its exception details.
