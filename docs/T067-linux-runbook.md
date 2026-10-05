# T067 Linux runbook

T067 runs exactly two frozen methods over the same 32 prediction-blind
documents: Schwartz–Hearst and the approved PLODv2 pairing component. The
challenger is their exact union, which is constructed locally only after both
prediction artifacts have been imported. The bundle contains no annotations,
gold labels, or credentials.

## 1. Copy and unpack the bundle

Copy this file from the Windows checkout to the Linux server:

```text
.artifacts/T067/abrex-t067-linux-bundle-v3.zip
```

On the Linux server, run:

```bash
mkdir -p "$HOME/abrex-t067-v1"
unzip abrex-t067-linux-bundle-v3.zip -d "$HOME/abrex-t067-v3"
cd "$HOME/abrex-t067-v3"
chmod +x setup-runtime.sh doctor.sh run-job.sh run-all.sh collect-results.sh
```

The expected bundle ID is:

```text
ab96b25c055f49832c3bfedc6c0e50cf87ddc59f8349b1decd38c7c1625c9966
```

The Windows ZIP SHA-256 is:

```text
bde41f96a1007c09135bdc0add39b1587e3e88c70c084882574b0a278d07b874
```

## 2. Reuse the runtime already prepared for T060

The T060 setup placed the persistent environments and verified PLOD checkpoint
outside its bundle. Reuse its `runtime.env`, then add the two T067 job names:

```bash
cp "$HOME/abrex-t060-release3/runtime.env" ./runtime.env
. ./runtime.env
printf 'export ABREX_JOB_PYTHON_T067_SCHWARTZ_HEARST=%q\n' \
  "$ABREX_CORE_PYTHON" >> runtime.env
printf 'export ABREX_JOB_PYTHON_T067_PLODV2_PAIRING_LINUX=%q\n' \
  "$ABREX_PLOD_PYTHON" >> runtime.env
./doctor.sh
```

Continue only if the JSON doctor report says `"complete": true`. If the T060
directory was renamed, replace only
`$HOME/abrex-t060-release3/runtime.env` with its actual path.

If that runtime no longer exists, create it from the self-contained setup
inputs instead:

```bash
./setup-runtime.sh --check
./setup-runtime.sh --all
./doctor.sh
```

This fallback uses standard-library `venv`; it does not use `uv`. If Python
3.13 is supplied under another executable name, first set
`ABREX_BOOTSTRAP_PYTHON` to its absolute path.

## 3. Queue or run

For Slurm:

```bash
job_id=$(sbatch --parsable submit.slurm)
echo "Submitted $job_id"
squeue -j "${job_id%%;*}"
```

After both array tasks have left the queue, inspect their final states:

```bash
sacct -j "${job_id%%;*}" --format=JobID,State,ExitCode,Elapsed
./collect-results.sh
```

Without Slurm, use:

```bash
./run-all.sh
```

Both routes produce:

```text
abrex-results-ab96b25c055f49832c3bfedc6c0e50cf87ddc59f8349b1decd38c7c1625c9966.zip
```

## 4. Copy back

Copy that result ZIP into the ABREX project root on Windows. No manual
inspection or renaming is needed. Tell Codex that it is present; the next step
will checksum-import it and run the already prepared frozen readout command:

```powershell
.\env313\Scripts\python.exe scripts\build_t067_readout.py
```

Do not run the readout before import. Its input checks require both matching
job-result manifests and reject changed datasets or prediction files.

## 5. Completed run record

This procedure completed successfully on October 5, 2026. The returned ZIP
was preserved as `.artifacts/T067/returned-results-v3.zip` with SHA-256
`d043da479f58346ea655c71e7d4707428cc2c9ada21b6fd7b343c84c9bb2165e`.
The importer verified both result packages and the doctor report; both jobs
processed 32/32 inputs with zero runtime failures. The immutable result is in
the [T067 readout](T067-fresh-evaluation-readout.md). Do not rerun this bundle
to tune against the revealed fresh annotations.
