# Run Ab3P and PLODv2: start here

Verified on September 13, 2026 in this checkout. Both runtimes already exist in
Ubuntu WSL. The original T058 failure came from incorrect configuration, not
missing installations. A dated success is not proof of future availability;
use the smoke below before reporting either method unavailable.

## One command to check all three methods

From PowerShell **in the abrex repository root**:

```powershell
wsl.exe -d Ubuntu -- /home/rleaman/.local/share/abrex/venv313/bin/python scripts/run_t058_readiness.py configs/literature/T058-runtime-readiness.yaml --output .artifacts/T058/verified-runtime/report.json --runtime-dir .artifacts/T058/verified-runtime/workers --require-all
if ($LASTEXITCODE -ne 0) { throw "Baseline readiness failed; inspect .artifacts/T058/verified-runtime/report.json and worker diagnostics" }
```

This runs the current checkout's orchestration inside Linux. The existing worker
boundary selects the separate PLOD environment. It does not download weights.
The report must say `available` and `complete` for Schwartz–Hearst, Ab3P,
PLOD independent spans and PLOD pairing. Prediction counts can differ by method.
`--require-all` saves failure evidence and returns nonzero if any is not ready.
This is a tiny operational smoke, not a benchmark or completion of T058 by itself.

Windows orchestration is also supported using
`.\env313\Scripts\python.exe scripts/run_t058_readiness.py` with the same
arguments; it launches Linux workers through WSL automatically. If that Python
launch is denied, use the WSL command above. Do not infer a resolver failure
from a Windows interpreter permission error.

## Exact existing resources

| Setting | Working value |
| --- | --- |
| WSL distribution | `Ubuntu` |
| Core / Ab3P Python | `/home/rleaman/.local/share/abrex/venv313/bin/python` |
| PLOD Python | `/home/rleaman/.local/share/abrex/plod313/bin/python` |
| Ab3P manifest, relative to repo root | `.artifacts/T021/live-installation-manifest.json` |
| Ab3P installation root | `.artifacts/T021/live-build/Ab3P` |
| Ab3P executable inside installation | `identify_abbr_offsets` |
| PLOD checkpoint | `/home/rleaman/.local/share/abrex/models/plodv2/019ed5392cad2deab220ad6bfda0681b20cabe21/pytorch_model.bin` |
| PLOD checkpoint SHA-256 | `3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277` |

The [ready YAML](../configs/literature/T058-runtime-readiness.yaml) contains these
settings and 120-second smoke timeouts. Paths are machine-local settings: copy
the YAML to an ignored task directory and override paths for another host.
Relative installation/cache paths require the repository working directory.
For another working directory use absolute **Linux** paths in worker settings.
Do not pass `C:\...` paths to Linux worker parameters.

Ab3P is a Linux executable, not a native Windows binary. Use the existing
adapter, which handles its resource working directory; do not invent a new
`path_Ab3P` file in the checkout. PLOD requires its own environment, not bare
`python3` or the lightweight core environment. The verified PLOD stack is
Flair 0.15.1 and PyTorch 2.14.0+cpu.

## Before declaring a runtime unavailable

1. Read this guide and run the strict smoke using the checked-in YAML.
2. Read the actual worker diagnostic. Check the named interpreter, manifest,
   executable/resources or checkpoint on the **Linux** side. A placeholder
   path or `checkpoint_sha256: unknown` is a configuration error.
3. Verify current package origin and versions, not just historical notes:

```powershell
wsl.exe -d Ubuntu -- /home/rleaman/.local/share/abrex/plod313/bin/python -c 'import sys, abrex, flair, torch; print(sys.executable); print(abrex.__file__); print(flair.__version__); print(torch.__version__)'
```

4. Reuse existing resources within the assigned repair budget. Only if a real
   prerequisite is absent or fails verification, record the exact command,
   path, error and bounded remediation. Do not rebuild or download merely
   because the first config failed. Never count failures as empty predictions.

Detailed recovery references: [Ab3P build/runtime](development-environments.md),
[PLOD installation and pinned model](plod-runtime.md).

## Quality gate

```powershell
wsl.exe -d Ubuntu -- /home/rleaman/.local/share/abrex/venv313/bin/python scripts/quality_gate.py --python /home/rleaman/.local/share/abrex/venv313/bin/python
if ($LASTEXITCODE -ne 0) { throw "Repository fast gate failed" }
```

Then run `git diff --check` separately. The gate now preserves the virtualenv
interpreter path instead of resolving its symlink to the base interpreter.
No installation of Ruff into the base Python should be necessary.

## T058 closure after the configuration repair

Read [the repair evidence and acceptance handoff](t058-repair-handoff.md) for
what has already passed and exactly what Luna must still reconcile.

Preserve the original failed report as historical evidence; produce a newly
named report for the repaired run. Reconcile the task specification, completion
note and index only after checking every acceptance criterion. Verify actual
cold/warm prediction-cache behavior and changed-text/config invalidation; a
different generic input hash alone is not such a test. Existing Ab3P cache
regressions in `tests/unit/test_ab3p.py` are useful starting evidence.
Retain independent PLOD spans, exact offset checks (including supplementary
Unicode), empty-result control, actual import/version/resource identities and
worker commands. Run focused checks and the fast gate. Do not start T059/T060
or alter frozen T052/T057 evidence while closing T058.
