# T058 bounded runtime readiness

Status: Complete — acceptance evidence verified September 13, 2026.

The original failed report remains preserved at
[T058-runtime-readiness.json](../../artifacts/T058-runtime-readiness.json).
It used placeholder runtime settings and is historical evidence only. The
superseding strict WSL evidence is
[T058-runtime-readiness-repaired.json](../../artifacts/T058-runtime-readiness-repaired.json),
produced with the documented command in [baseline-runtimes.md](../../baseline-runtimes.md).

## Acceptance evidence

- All four readiness channels are `available` with `complete` coverage for all
  3/3 smoke passages: Schwartz–Hearst, native-offset Ab3P, PLODv2 independent
  spans and PLODv2 pairing.
- The smoke includes supplementary Unicode, repeated forms and an empty-result
  control. Worker input arrays are identical across optional methods.
- Exact source-offset evidence passed for every returned result: 2/2 S&H
  pairs, 1/1 Ab3P pair, 7/7 PLOD spans and 3/3 PLOD pairs have text that
  exactly slices the canonical text. The empty control returned zero pairs and
  zero independent spans for every method.
- Ab3P identity records the adapter/wrapper versions, Python 3.13.15,
  executable, manifest and resource hashes. PLOD records Python 3.13.15,
  Flair 0.15.1, PyTorch 2.14.0+cpu and the pinned checkpoint hash.
- Worker commands and runtime origins are recorded. No installation, download
  or rebuild was performed for closure; the existing WSL environments were
  reused.
- The existing `Ab3PCache` was tested through `Ab3PResolver`: a cold live run
  started with no entry and wrote one; a warm replay returned identical
  predictions while live invocation was actively blocked; changed text and a
  changed output-format configuration both produced cache misses. This is
  actual cache behavior, not only a generic hash comparison.
- PLOD independent spans and paired relations remain separate outputs. The
  `rejected_selection_conflict` diagnostic is retained as pairing evidence,
  not treated as a worker failure.

## Repair budget and scope

The recorded ceiling was two hours total troubleshooting, at most one bounded
repair attempt per optional method, and no bulk downloads or system
installation. The configuration/launcher repair was already supplied before
this closure pass; no installation work was repeated. T052/T057 frozen evidence
was not modified, and T059/T060 were not started.

## Reproduction

```powershell
wsl.exe -d Ubuntu -- /home/rleaman/.local/share/abrex/venv313/bin/python scripts/run_t058_readiness.py configs/literature/T058-runtime-readiness.yaml --output .artifacts/T058/verified-runtime/report.json --runtime-dir .artifacts/T058/verified-runtime/workers --require-all
```

Focused checks: **19 passed** for readiness and Ab3P cache behavior. The
repository fast gate passed: source import, Ruff format/lint, strict mypy and
**373** unit/contract tests. `git diff --check` passed. This is operational
readiness evidence only; it makes no accuracy, complementarity or deployment
claim.
