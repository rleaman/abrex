# ABREX revival handoff — October 2, 2026

## Current state

The engineering baseline, CLP snapshot integration, Jev candidate judge,
portable Linux execution, and prediction-blind reviewer are implemented. The
remaining work is deliberately sequential: finish the two Linux runtime jobs,
prepare and complete the assisted T061 review, freeze the T063 scientific
choices, acquire the fresh blind packet, obtain the user's T066 annotations,
and only then run T067/T068.

The existing development comparison currently favors Schwartz–Hearst. On the
20-passage, 59-pair T057 development view it scored 36 TP, 7 FP and 23 FN
(F1 0.7059). The frozen Jev candidate judge scored 29 TP, 24 FP and 30 FN
(F1 0.5179) at threshold 0.60. Jev candidate coverage was 47/59 (79.66%), so
some misses cannot be repaired by judging alone. The live run used 225,965
input tokens, cost approximately $0.0095 at the supplied rate, and had no
request failures.

## Linux handoff

Copy `.artifacts/T060/abrex-t060-linux-bundle-release2.zip` to the Linux server.
Its SHA-256 is
`8156f0cae72b7f06339293e660330a9193ac6695d8bf1cb31812ac185b74f36e` and
its bundle ID is
`47cb4c8a73b1935bbdf8ddeadba73b0ce9b62d8810e50a907e3e3dbd50bc8ef7`.
The archive contains prediction-only inputs, embedded ABREX source, checksums,
shell launchers, and a Slurm array. It contains neither gold annotations nor
credentials.

On Linux:

```bash
mkdir -p abrex-t060
unzip abrex-t060-linux-bundle-release2.zip -d abrex-t060
cd abrex-t060

export ABREX_JOB_DOCTOR_PYTHON=/home/rleaman/.local/share/abrex/venv313/bin/python
export ABREX_JOB_PYTHON_T060_AB3P_LINUX=/home/rleaman/.local/share/abrex/venv313/bin/python
export ABREX_JOB_PYTHON_T060_PLODV2_PAIRING_LINUX=/home/rleaman/.local/share/abrex/plod313/bin/python
export ABREX_AB3P_MANIFEST=/absolute/path/to/live-installation-manifest.json
export ABREX_AB3P_ROOT=/absolute/path/to/Ab3P
export ABREX_PLODV2_CHECKPOINT=/absolute/path/to/pytorch_model.bin

chmod +x doctor.sh run-job.sh run-all.sh collect-results.sh
./doctor.sh
```

Only proceed if the doctor report marks every check available. Then either run:

```bash
./run-all.sh
```

or queue the independent jobs:

```bash
sbatch submit.slurm
# after both array jobs finish
./collect-results.sh
```

Copy the generated `abrex-results-47cb4c8a73b1935bbdf8ddeadba73b0ce9b62d8810e50a907e3e3dbd50bc8ef7.zip`
back into this checkout. It includes result manifests, predictions, execution
logs, the doctor report, and any Slurm logs. Import it with:

```powershell
.\env313\Scripts\python.exe -m abrex jobs import `
  .artifacts/T060/linux-bundle-release2 `
  PATH_TO_COPIED_RESULT_ZIP `
  --into .artifacts/T060/imported-linux-results
```

The importer verifies bundle identity, experiment identity, path safety, and
every checksum. Reimporting the identical result is safe; a conflicting result
is rejected.

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

1. Import the Linux results. ABREX can then assemble the complete T060
   comparison and the smallest deduplicated T061 assisted review packet.
2. Complete T061. ABREX will calculate the T062 recovery/error analysis and
   reduce T063 to the prefilled choices in
   `docs/artifacts/T063-decision-prefill.json`.
3. After those choices are confirmed, freeze and acquire the 32-item packet.
   The implemented blind UI will be used for T066; it has passed real Edge
   browser QA, payload-isolation, save/reload, import/export, Unicode/repeated
   text, zero-relation, lock, and narrow-viewport checks.
4. Once the annotation lock exists, prepare/run/import prediction-only T067
   jobs and evaluate prose and table/list arms separately. T068 remains the
   user's final scientific direction choice.

T042 remains deferred. The excluded BADREX-corrected corpora remain out of
scope under the recorded decision.
