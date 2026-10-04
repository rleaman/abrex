# Linux server runtime provisioning

## Operational decision

Recorded October 4, 2026 after the first fresh-server handoff exposed a
machine-local-path assumption.

ABREX has two distinct Linux runtime contexts. They must not be conflated:

1. The paths under `/home/rleaman/.local/share/abrex` in historical runtime
   reports document a previously verified Ubuntu WSL installation. They are
   provenance, not defaults for another host.
2. Fresh Linux servers use the setup script included in each portable job
   bundle. The user cannot install WSL in the active Windows environment, so
   server execution is the supported transfer/run/copy-back route.

The initial server handoff incorrectly carried the WSL interpreter paths and
the historical assumption that `uv` already existed at
`$HOME/.local/share/abrex/bin/uv`. On a new server this produced a predictable
`No such file or directory` failure before an environment could be created.

## Required handoff behavior

For a fresh-server Ab3P/PLODv2 bundle:

- include `setup-runtime.sh`, its pinned requirement files, the Ab3P builder,
  and the offset frontend source in the bundle;
- use Python 3.13's standard-library `venv`; do not require a preinstalled
  `uv` executable;
- treat `python3` in experiment configuration as a portable fallback, not a
  verified job interpreter;
- generate `runtime.env` with the actual server paths and have the doctor,
  job, result-collection, and Slurm launchers consume it automatically;
- build the pinned Ab3P and NCBITextLib revisions and generate the
  installation manifest on the server;
- download the pinned PLOD checkpoint, verify its SHA-256, and only then
  publish its final filename;
- keep credentials and gold annotations out of both the setup material and
  prediction bundle;
- run `setup-runtime.sh --check` before making changes and preserve the exact
  failed prerequisite when setup cannot proceed.

The only expected host-specific choice is locating Python 3.13, often by
loading a server module. If it is not named `python3.13`, set
`ABREX_BOOTSTRAP_PYTHON` to its absolute executable. `ABREX_RUNTIME_ROOT` may
select a persistent project or scratch filesystem. No other manual path
exports should be required for the generated jobs.

## Current T060 handoff

The original paired-method archive was
`.artifacts/T060/abrex-t060-linux-bundle-release3.zip`. From its extracted
directory:

```bash
chmod +x setup-runtime.sh doctor.sh run-job.sh run-all.sh collect-results.sh
./setup-runtime.sh --check
./setup-runtime.sh --all
./doctor.sh
```

Only run or submit jobs after the doctor reports `"complete": true`. See the
[dated revival handoff](revival-handoff-2026-10-02.md) for the current archive
hash, bundle ID, result filename, and copy-back command.

Those results returned successfully on October 4. A one-job follow-up now
captures the independent PLOD spans that the pairing artifact did not retain:
`.artifacts/T060/abrex-t060-plod-spans-followup.zip`. Reuse the first bundle's
`runtime.env`; no runtime reinstall is needed. The dated revival handoff has
the exact copy/run/copy-back commands and immutable identifiers.

## Interpretation of older documents

Do not rewrite historical evidence files merely because they contain WSL
paths: those paths are part of their recorded provenance. Operational guides
must label them as historical and point fresh-server work here. A missing
historical path on another host is not evidence that Ab3P or PLODv2 is
unavailable.
