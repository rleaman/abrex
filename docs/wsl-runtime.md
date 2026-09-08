# Local WSL runtime and T020 smoke verification

For the user-local Java JDK and BioADI extraction command, see
[BioADI runtime](bioadi-runtime.md).

For the separate optional Flair/PyTorch environment and pinned PLODv2 model,
see [PLOD CPU runtime](plod-runtime.md). The core environment below does not
contain that optional model stack.

The missing-`pydantic` blocker reported in the T020 completion note was resolved
on September 7, 2026. Ubuntu's system Python remains unchanged.

## Installed environment

- WSL distribution: Ubuntu.
- Python: CPython 3.13.15.
- Environment: `/home/rleaman/.local/share/abrex/venv313`.
- Installer: `/home/rleaman/.local/share/abrex/bin/uv` (0.12.10).
- Dependencies: the repository's `requirements-dev.lock`, including Pydantic
  2.13.5, followed by an editable `abrex` installation with `--no-deps`.
- The editable installation follows the working checkout, including ongoing
  edits. Windows `env313` and Linux environments are separate.

From PowerShell, run the installed Linux interpreter explicitly:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mail/Documents/Projects/abrex && "$HOME/.local/share/abrex/venv313/bin/python" -m abrex --help'
```

Use this interpreter instead of bare `python3` for ABREX commands in WSL.
An interactive alternative is to enter `wsl.exe -d Ubuntu`, then run:

```bash
source "$HOME/.local/share/abrex/venv313/bin/activate"
cd /mnt/c/Users/mail/Documents/Projects/abrex
python -m abrex --help
```

To refresh dependencies after an intentional lock update, inside WSL run:

```bash
cd /mnt/c/Users/mail/Documents/Projects/abrex
"$HOME/.local/share/abrex/bin/uv" pip install --python "$HOME/.local/share/abrex/venv313/bin/python" -r requirements-dev.lock
"$HOME/.local/share/abrex/bin/uv" pip install --python "$HOME/.local/share/abrex/venv313/bin/python" --no-deps --editable .
```

## Operational verification

To avoid racing T021 edits, verification used an archived source snapshot of
commit `395661011e9900a280cd6eb3c1d8d0ab201975ec`, with `PYTHONPATH` pointing
to that snapshot's `src` directory. It did not test the concurrently changing
T021 working tree.

- Real binary: `.artifacts/T018/script-a/Ab3P/identify_abbr`, with the T018
  installation manifest and WordData verification enabled.
- Input: bundled `docs/examples/experiment-corpus.jsonl` (two documents).
- Live result: two records, zero failures; TNF / Tumor necrosis factor and
  MRI / Magnetic resonance imaging extracted without diagnostics.
- Cache-only replay: byte-identical prediction output.
- Prediction fingerprint:
  `b10402244dbbfb41b90081e5993a7d71bae2eb3f0ba6cc19f5685936bd0bbde0`.
- Focused snapshot tests: `11 passed` in `tests/unit/test_ab3p.py`.
- Snapshot fast quality gate: Ruff format and lint passed, mypy passed for
  109 source files, and all 174 unit/contract tests passed.

Snapshot, smoke configurations, raw cache, and predictions are retained locally
under ignored `.artifacts/wsl-runtime/`. This is a small operational smoke,
not benchmark validation or validation of T021's native-offset changes.
