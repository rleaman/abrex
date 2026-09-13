# T058 bounded runtime readiness

> September 13 correction: the completion claim below is retained as historical
> evidence and is superseded pending acceptance revision. Both optional runtimes
> ran successfully after correcting configuration. See
> [the runtime guide](../../baseline-runtimes.md). The original unavailable report
> does not describe current host readiness. The generic changed-input hash check
> does not establish prediction-cache invalidation.

Status: Engineering and bounded smoke complete; the three-primary-method run
remains incomplete because the optional runtimes are unavailable on this host.

The reusable readiness runner is [runtime_readiness.py](../../../src/abrex/literature/runtime_readiness.py),
with its portable configuration in
[T058-runtime-readiness.yaml](../../../configs/literature/T058-runtime-readiness.yaml).
It executes one fixed three-passage smoke containing supplementary Unicode,
repeated forms and a control passage with no expected definition. It preserves
PLOD independent spans and PLOD pairing as separate report entries, records
canonical text hashes, worker commands, coverage, truncation diagnostics and
changed-input identity checks, and never converts a failed worker into zero
detections.

## Observed readiness

The durable report is [T058-runtime-readiness.json](../../artifacts/T058-runtime-readiness.json).

| Method | Status | Coverage | Evidence |
| --- | --- | --- | --- |
| Schwartz–Hearst | available | complete, 3/3 passages | real in-process smoke; 2 pairs |
| native-offset Ab3P | unavailable | none | configured installation manifest is absent |
| PLODv2 independent spans | unavailable | none | configured checkpoint identity is `unknown`, rejected by validation |
| PLODv2 pairing | unavailable | none | same prerequisite failure; kept separate from spans |

The repair budget was two hours total, one bounded repair attempt per optional
method, and no bulk download or system installation. No repair was attempted:
the missing Ab3P installation and missing/invalid PLOD checkpoint are separate
prerequisite work, not safe local repairs.

## Reproduction

```powershell
.\env313\Scripts\python.exe scripts\run_t058_readiness.py `
  configs\literature\T058-runtime-readiness.yaml `
  --output docs\artifacts\T058-runtime-readiness.json `
  --runtime-dir .artifacts\T058\runtime-readiness
```

Edit only the machine-local interpreter, installation, cache and checkpoint
paths in the YAML before replaying on a prepared environment. The output is
portable JSON; the ignored runtime directory retains worker inputs and outputs.

Focused regression checks: **2 passed**. Ruff format, Ruff lint and strict
mypy: **passed**. The readiness runner was executed against the current
configuration and produced the statuses above. No accuracy or scientific
comparison claim is made.
