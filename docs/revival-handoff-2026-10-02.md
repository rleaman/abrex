# ABREX revival handoff — October 2, 2026

## Current state

The engineering baseline, CLP snapshot integration, Jev candidate judge,
portable Linux execution, and prediction-blind reviewer are implemented. The
paired Linux runtime jobs returned successfully on October 4. T061–T065 are
now complete: the development evidence is reconciled, the T063 scientific
protocol is approved and frozen, and the 32-case fresh prediction-blind packet
has been acquired and browser-verified. T066 is complete with an audited,
corrected prediction-blind lock. The remaining work is deliberately sequential:
run T067, then make the T068 scientific direction decision.

The corrected development comparison currently favors Schwartz–Hearst. On the
20-passage, 59-pair T057 development view it scored 36 TP, 7 FP and 23 FN
(F1 0.7059). Jev resolver v2 separately asks whether a pair is a definition and
which span is the short form. At frozen thresholds 0.75 and 0.95 it scored 23
TP, 15 FP and 36 FN (F1 0.4742). Jev candidate coverage was 47/59 (79.66%), so
some misses cannot be repaired by judging alone. The live run used 225,965
input tokens for historical v1 and 347,692 for corrected v2; v2 cost
approximately $0.0146 at the supplied rate and had no request failures.

The complete four-way strict-pair comparison is now at
`docs/artifacts/T060-development-comparison-split-v2.json`. Schwartz–Hearst
leads on F1 (0.7059); Ab3P scored 0.6355, PLODv2 pairing 0.6105, and Jev v2
0.4742. The deduplicated assisted-review queue contains 33 proposals in 11
passages and is ready at `evidence/T060/review-packet-split-v2.json`. The
unsuffixed artifacts preserve the superseded v1 comparison and must not be used
for T061.

## Linux handoff

Copy `.artifacts/T060/abrex-t060-linux-bundle-release3.zip` to the Linux server.
Its SHA-256 is
`1755738fe6023e79b51afa2c5cb707476e3aaa33d6b0cea452681e8215ceaa15` and
its bundle ID is
`71ed8dc6d27ab7b9002fbdd98130a9b3184c3c5884e66113ed407adfa399e5b8`.
The archive contains prediction-only inputs, embedded ABREX source, checksums,
shell launchers, a Slurm array, and all setup scripts and pinned requirement
files needed for a fresh server. It contains neither gold annotations,
credentials, external source archives, nor the 394 MB PLOD checkpoint.

Do not reuse the old WSL `uv_tool`, virtual-environment, or model paths. They do
not exist on a fresh server, and `uv` is not required. On an internet-connected
Linux login node:

```bash
mkdir -p abrex-t060
unzip abrex-t060-linux-bundle-release3.zip -d abrex-t060
cd abrex-t060

chmod +x setup-runtime.sh doctor.sh run-job.sh run-all.sh collect-results.sh
./setup-runtime.sh --check
./setup-runtime.sh --all
./doctor.sh
```

The prerequisite check requires an actual Python 3.13 interpreter plus `git`,
`make`, `g++`, `curl`, and `sha256sum`. If the server provides Python through
an environment module, load that module first. If its executable is not named
`python3.13`, point the setup at it explicitly and repeat the check:

```bash
export ABREX_BOOTSTRAP_PYTHON=/absolute/path/to/python3.13
./setup-runtime.sh --check
./setup-runtime.sh --all
```

To use a project or scratch filesystem instead of the default user data
directory, set `ABREX_RUNTIME_ROOT` before both setup commands. The setup uses
Python's built-in `venv`, installs the two pinned environments, checks out and
builds pinned Ab3P/NCBITextLib sources, generates the Ab3P installation
manifest, downloads and verifies the pinned PLOD checkpoint, and writes
`runtime.env`. The launchers source `runtime.env` automatically, including in
Slurm jobs. It contains paths and no credentials.

Only proceed if the doctor report says `"complete": true`. Then either run:

```bash
./run-all.sh
```

or queue the independent jobs:

```bash
sbatch submit.slurm
# after both array jobs finish
./collect-results.sh
```

Copy the generated `abrex-results-71ed8dc6d27ab7b9002fbdd98130a9b3184c3c5884e66113ed407adfa399e5b8.zip`
back into this checkout. It includes result manifests, predictions, execution
logs, the doctor report, and any Slurm logs. Import it with:

```powershell
.\env313\Scripts\python.exe -m abrex jobs import `
  .artifacts/T060/linux-bundle-release3 `
  PATH_TO_COPIED_RESULT_ZIP `
  --into .artifacts/T060/imported-linux-results
```

The returned archive was imported successfully. Both jobs produced 20/20
records with zero execution errors. Ab3P took 1.89 seconds and PLODv2 pairing
took 30.87 seconds on the recorded Linux host. The importer verified bundle
identity, experiment identity, path safety, and every checksum.

### Small PLOD span follow-up

For the complete Windows-to-Linux-to-Windows procedure, including verification,
Slurm, copy-back, import, and the corrected T061 launcher, use the
[T060/T061 runbook](t060-t061-runbook.md).

The original PLOD pairing job retained paired definitions but not the
independent detector output. T060 requires the latter so unpaired spans remain
auditable. Copy
`.artifacts/T060/abrex-t060-plod-spans-followup.zip` to the same server. Its
SHA-256 is
`1a65a277b898b919e5bd54aff622d1df46c4db5bea93ea694c78fdebf22d654d`
and its bundle ID is
`aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb`.

Assuming the first bundle is still in `abrex-t060-release3`, reuse its verified
runtime without rebuilding or downloading anything:

```bash
mkdir -p abrex-t060-plod-spans
unzip abrex-t060-plod-spans-followup.zip -d abrex-t060-plod-spans
cd abrex-t060-plod-spans
chmod +x doctor.sh run-all.sh run-job.sh collect-results.sh
cp ../abrex-t060-release3/runtime.env ./runtime.env
. ./runtime.env
printf 'export ABREX_JOB_PYTHON_T060_PLODV2_SPANS_LINUX=%q\n' \
  "$ABREX_PLOD_PYTHON" >> runtime.env
./doctor.sh
./run-all.sh
```

Copy the resulting
`abrex-results-aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb.zip`
back to the project root and import it using the command in the runbook. This
is one PLOD pass over the same 20 passages; it does not rerun Ab3P or require a
new setup.

### T061 review complete

The returned PLOD span follow-up is imported and complete. Existing T061 work
was preserved, then the unfinished proposals were reconciled against frozen
T057 evidence and the exact-boundary policy. The user accepted the one
remaining full `scavenger receptor class B type 1 (SR-BI)` pair. Verify the
saved state at any time with:

```powershell
.\scripts\Review-T061.ps1
```

The completed state is in
`evidence/T061/review-packet-minimal.annotations.json`; the original seven
completed passages remain in
`evidence/T060/review-packet-split-v2.annotations.json`.

## CLP reuse

The exported snapshot is pinned to sister-project commit
`323fd4f51aa3c5b54ed30f37dd297b00b49e277e`; no sister-repository files were
modified by this work. The exported `clp-abbr-snapshot-v1` contains 200 table/list sections,
143 positive and 57 negative examples. It maps 3,696 accepted pairs to unique
half-open source spans and reports 339 ambiguous or missing mappings as
unscorable rather than guessing. Registry keys are `clp_abbr_snapshot_v1` and
`clp_table_v5_1`. Any later live coupling uses the typed
`clp-abbr-worker-request-v1` / `clp-abbr-worker-response-v1` JSON boundary,
not sister-project imports. This material is development evidence because it influenced
the sister parser; it is excluded from fresh evaluation.

## Next checkpoints

1. T060–T065 are complete. The approved protocol and actual 32-case packet are
   frozen under `docs/artifacts/T063-decision-prefill.json` and `evidence/T065`.
2. T066 is complete. Use the corrected state and replacement lock under
   `evidence/T066`; the original lock under `evidence/T065` remains preserved.
   Both post-lock corrections were authorized before predictions were exposed.
3. Prepare/run/import prediction-only T067
   jobs and evaluate prose and table/list arms separately. T068 remains the
   user's final scientific direction choice.

T042 remains deferred. The excluded BADREX-corrected corpora remain out of
scope under the recorded decision.
