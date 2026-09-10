# Abbreviation Resolution Project

A modular framework for abbreviation resolution and expansion extraction in scientific text.

The [project completion plan](docs/project-completion-plan.md) summarizes the
remaining research and engineering milestones. See the
[current-state audit](docs/project-state-audit.md) for verified capabilities
and the [task index](docs/tasks/README.md) for the planned GPT-5.6 Luna assignments.
The provisional [scientific model](docs/scientific-model/README.md) records the
phenomena and distinctions being refined through iterative annotation before
they are operationalized as annotation guidelines. Frozen packets, annotations
and provenance live in the [scientific evidence bundles](evidence/README.md).

## Start here when returning to the project

Open PowerShell in the repository folder. These commands use the existing
Windows environment; for a new installation, follow **Development** below.

```powershell
$py = ".\env313\Scripts\python.exe"
```

**Try the complete pipeline on a tiny bundled example** (no downloads or WSL):

```powershell
& $py -m abrex experiment run docs/examples/experiment-toy.yaml --output-root data/exploration/toy-experiment
```

Look in the printed run directory for `evaluation.json` and `run-manifest.json`.
This demonstrates resolution, evaluation, and reporting; it is not a benchmark.

**Extract definitions from the locally built MEDSTRACT corpus**:

```powershell
& $py -m abrex resolver run docs/examples/resolver-schwartz-hearst.yaml --input data/processed/medstract/canonical.jsonl --output data/exploration/medstract-sh-predictions.jsonl
```

Open the output JSONL to inspect predicted short/long forms, spans, and
diagnostics. This produces predictions, not accuracy scores. If the input is
missing, see the build instructions in the [returning-user guide](docs/quickstart.md).

For corpus audits, other datasets, experiment variants, output locations, and
common missing-input problems, keep the [returning-user guide](docs/quickstart.md)
handy. For what to implement next, consult the [task index](docs/tasks/README.md)
and the latest [completion notes](docs/tasks/completed/).

## Development

The project targets Python 3.13 and uses a `src/` layout. Create an environment
and install the checked-in development snapshot. See
[reproducible development environments](docs/development-environments.md) for
Windows and Linux commands:

```console
python -m pip install --requirement requirements-dev.lock
python -m pip install --no-deps --editable .
```

Run the fail-fast quality gate from the same environment:

```console
python scripts/quality_gate.py
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
python scripts/quality_gate.py --full
```

The `pytest` portion is what actually runs the tests; Ruff and mypy only
check formatting, lint, and types. To run the tests alone, use
`python -m pytest` (or `.\env313\Scripts\python.exe -m pytest` on Windows).

Resolve configuration layers and print the deterministic result:

```console
python -m abrex config resolve configs/base.yaml
```

Resolve a locally available PubMed/PMC article with an explicit segmentation
policy; this command performs no network retrieval:

```console
python -m abrex article resolve docs/examples/article-resolution.yaml \
  --input docs/examples/local-article.json \
  --output data/article-resolution.json
```

See [local article integration](docs/literature-integration.md) for the input
shape, provenance contract, and downstream entity mapping.

For the local installable release candidate and exact artifact hashes, see
[release-candidate.md](docs/release-candidate.md). Research artifacts remain
separately labeled as exploratory, provisional or pending; no external
publication is performed by this workflow.

## Historical datasets

Download one source bundle with its own YAML configuration, or the named
historical group, with:

```console
abrex datasets download --config configs/datasets/sdu_aaai22_ae.yaml
abrex datasets download-all --group historical
```

Normal reruns reuse a validated destination without contacting the network.
Use `--dry-run` to classify missing, reusable, and conflicting items without
network or filesystem writes; use `--force` only for an intentional refresh.
Group runs continue after independent conflicts or failures and return the
structured result array on stdout. The old positional command
`python -m abrex datasets download configs/historical-datasets.yaml` remains
accepted as legacy compatibility syntax; new source definitions live under
`configs/datasets/` and the group is declared in `configs/dataset-groups.yaml`.

### Command-line logging

ABREX commands emit concise operational logs at `INFO` level by default. Logs
go to stderr, so JSON/YAML/TSV command output remains clean on stdout. Use
`--quiet` for warnings and errors only, `--verbose` for the normal operational
view, or `--debug` for low-level diagnostics such as resolved paths, cache keys,
and bounded subprocess details.

Log levels have these meanings: `ERROR` requires attention; `WARNING` reports
a degraded, skipped, repaired, incomplete, or potentially problematic event;
`INFO` reports high-level milestones; and `DEBUG` reports developer-oriented
diagnostics. Logging does not participate in scientific artifacts or their
fingerprints.
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
