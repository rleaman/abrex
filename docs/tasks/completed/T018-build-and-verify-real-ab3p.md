# T018 completion note

## Changed

- Added [`scripts/build_ab3p.py`](../../scripts/build_ab3p.py), a Linux/WSL
  reproducibility builder that copies both supplied sibling source trees into a
  task-owned directory, builds NCBITextLib before Ab3P, regenerates WordData,
  runs the upstream comparison, exercises smoke/failure paths, and writes a
  path-independent manifest.
- Added the verified
  [`ab3p-installation-manifest.json`](../../docs/artifacts/ab3p-installation-manifest.json).
  Generated binaries, copied sources and raw smoke outputs remain under the
  ignored `.artifacts/T018/` directory.
- Added WSL2/PowerShell launch, path_Ab3P resolution, cache-export and
  non-native-Windows guidance to
  [`docs/development-environments.md`](../../docs/development-environments.md)
  and linked the manifest from [`docs/resolvers.md`](../../docs/resolvers.md).
- Recorded T018 as complete in this task and the task index.

The copied build applies only these compatibility repairs: CRLF-to-LF
normalization for `path_Ab3P` and the four textual WordData inputs, plus the
upstream modern-GCC repair `bool rate( int i ) const { return my_rate[i]; }`.
The supplied sibling trees were not modified and no detector rule was added.

## Source and installation identity

- Ab3P source: commit
  `41130cddfcba1449ba612905d4a51274f8f565a8`, Git tree
  `15ca7c33badc8f3193be7a44ba6374def652ef77`.
- NCBITextLib source: commit
  `e5ac0d4e0572970911f36099995e4170a12a85e7`, Git tree
  `9ddfe4421d9c3a8a2ed6607f2d59102b9b53a50e`.
- Environment: Ubuntu 24.04.1 LTS on WSL2, Linux 6.6.114.1,
  g++ 13.3.0, GNU Make 4.3, Python 3.12.3. The builder uses upstream
  `-std=c++11 -gdwarf-2`/`-g` flags and a stable debug-prefix map.
- Manifest SHA-256:
  `0b7d5a83d667e65c0714ab11b5e38392aa7ae2c60e71333892967919e22ccb31`.
  It contains executable, both static-library and all 16 semantic WordData
  artifact identities, including sizes and SHA-256 hashes, plus public-domain
  notices.

## Verification

Two clean builds were run from the repository checkout:

```text
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mail/Documents/Projects/abrex; python3 scripts/build_ab3p.py --output .artifacts/T018/script-a --manifest docs/artifacts/ab3p-installation-manifest.json'
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mail/Documents/Projects/abrex; python3 scripts/build_ab3p.py --output .artifacts/T018/script-b --manifest .artifacts/T018/script-b-manifest.json'
```

Both builds compiled successfully, generated 94,718 selected dictionary words
and 90,000 counted terms, passed `make test` with exit status 0, and produced
byte-identical manifests. The real `identify_abbr` executable produced two
definitions from the UTF-8/multiline smoke input, ran successfully from a
different working directory with an explicit `path_Ab3P`, and failed with
exit status 1 when its WordData resource path was intentionally missing. Raw
outputs are retained in each build's `verification/` directory.

Repository checks:

- Ruff format check: passed (110 files).
- Ruff lint: passed.
- mypy: passed (109 source files).
- Unit/contract tests: 167 passed.
- Full tests and coverage: 171 passed, 95.72% coverage, above the 95% floor.
- `python3 -m py_compile scripts/build_ab3p.py`: passed.
- `git diff --check`: passed.

## Remaining boundary and next task

This completes the T018 build and operational verification. It does not claim
corpus accuracy, a benchmark result, or a native Windows executable. Ubuntu's
available Python is 3.12.3 rather than ABREX's Python 3.13 target; live ABREX
cache population should therefore use a compatible Linux Python 3.13
environment while keeping Python and Ab3P in the same WSL command path. The
documented Windows path is cache export and `cache_only` replay.

T019, the historical corpus semantic audit, is ready next.
