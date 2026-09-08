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

## Real Ab3P in Ubuntu WSL2

For the installed local Python environment, copyable launch commands, and the
successful T020 live/cache smoke, see [local WSL runtime](wsl-runtime.md).

The real Ab3P build is an optional Linux/WSL artifact, not a Python or native
Windows dependency. The checked-in builder copies the user-supplied sibling
sources into a task-owned output directory, builds NCBITextLib and Ab3P,
regenerates the WordData indexes, runs the upstream comparison, and writes the
[installation manifest](artifacts/ab3p-installation-manifest.json). It does
not modify either sibling source tree. The builder records the two source
revisions, source-tree hashes, compiler and Make versions, executable and
library hashes, semantic resource hashes, compatibility repairs, and raw smoke
outputs.

Run it from the repository root inside Ubuntu. The source paths below are the
supplied siblings of the checkout:

```bash
cd /mnt/c/Users/mail/Documents/Projects/abrex
python3 scripts/build_ab3p.py \
  --ab3p-source ../Ab3P \
  --ncbi-source ../NCBITextLib \
  --output .artifacts/T018/build-a \
  --manifest docs/artifacts/ab3p-installation-manifest.json
```

A Windows PowerShell launch translates the checkout path, sets the Linux
working directory explicitly, and preserves a nonzero WSL exit code:

```powershell
$repoWindows = (Get-Location).Path
$repoLinux = (wsl.exe -d Ubuntu -- wslpath -a "$repoWindows").Trim()
wsl.exe -d Ubuntu -- bash -lc "set -eu; cd '$repoLinux'; exec python3 scripts/build_ab3p.py --ab3p-source ../Ab3P --ncbi-source ../NCBITextLib --output .artifacts/T018/build-a --manifest docs/artifacts/ab3p-installation-manifest.json"
if ($LASTEXITCODE -ne 0) { throw "WSL Ab3P build failed with exit code $LASTEXITCODE" }
```

The supplied text files are CRLF-terminated. The builder converts only the
Ab3P path/resource inputs to LF in the copied build tree. It also applies the
minimal modern-GCC repair recorded in the manifest:
`bool rate( int i ) const { return my_rate[i]; }`. This fixes the upstream
missing return that otherwise becomes an illegal-instruction trap under GCC
13; it does not introduce a new detection rule.

Ab3P resolves `path_Ab3P` relative to the process working directory, not
relative to the executable. Running from the copied `Ab3P` directory uses its
`./WordData/` file. Running from another directory requires a LF-terminated
`path_Ab3P` in that directory whose one line names the absolute Linux
`WordData` directory, or a wrapper that changes directory before execution.
The builder verifies both cases and retains the raw outputs under its ignored
`.artifacts/T018/` directory.

For initial ABREX integration, run Python and the Linux executable in the same
Ubuntu command path, for example with the configured Linux resolver command:

```powershell
wsl.exe -d Ubuntu -- bash -lc "set -eu; cd '$repoLinux'; python3 -m abrex resolver run docs/examples/resolver-ab3p-cache.yaml --input data/processed/benchmark.jsonl --output artifacts/ab3p-predictions.jsonl"
if ($LASTEXITCODE -ne 0) { throw "WSL ABREX/Ab3P command failed with exit code $LASTEXITCODE" }
```

Copy the resulting raw `artifacts/ab3p-cache` directory into the Windows
checkout and use `backend: cache_only` with the same installation identity.
This project does not claim a native Windows Ab3P binary or direct loading of
the Linux executable by a native Windows Python process.
