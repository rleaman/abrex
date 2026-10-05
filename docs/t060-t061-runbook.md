# T060 PLOD span follow-up and minimal T061 review

The PLOD span follow-up is complete and imported. It processed all 20 passages
in 89.15 seconds with no execution errors. Do not rerun or recopy it unless the
imported artifact is lost. The only remaining user action is one T061 support
decision. The October 4 Jev correction did not affect the PLOD bundle.

## Part A: PLOD span follow-up (complete; reference only)

### 1. Verify the bundle on Windows

Open PowerShell in `C:\Users\leamanjr\projects\abrex` and run:

```powershell
Set-Location C:\Users\leamanjr\projects\abrex
$bundle = ".\.artifacts\T060\abrex-t060-plod-spans-followup.zip"
if (-not (Test-Path -LiteralPath $bundle -PathType Leaf)) { throw "Missing $bundle" }
(Get-FileHash -Algorithm SHA256 -LiteralPath $bundle).Hash.ToLower()
```

The output must be:

```text
1a65a277b898b919e5bd54aff622d1df46c4db5bea93ea694c78fdebf22d654d
```

Copy that ZIP to the same Linux account that contains the earlier extracted
`abrex-t060-release3` directory. No Jev key or gold annotations are involved.

### 2. Extract it on Linux

The commands below assume both the earlier directory and the new ZIP are in
the same parent directory. Run them from that parent directory:

```bash
test -f abrex-t060-release3/runtime.env
sha256sum abrex-t060-plod-spans-followup.zip
mkdir -p abrex-t060-plod-spans
unzip -q abrex-t060-plod-spans-followup.zip -d abrex-t060-plod-spans
cd abrex-t060-plod-spans
chmod +x doctor.sh run-all.sh run-job.sh collect-results.sh
cp ../abrex-t060-release3/runtime.env ./runtime.env
. ./runtime.env
printf 'export ABREX_JOB_PYTHON_T060_PLODV2_SPANS_LINUX=%q\n' \
  "$ABREX_PLOD_PYTHON" >> runtime.env
```

The `sha256sum` value must match the Windows value above. If
`abrex-t060-release3/runtime.env` is missing, stop: do not substitute an old WSL
path or a generic Python executable.

### 3. Run the doctor

```bash
./doctor.sh
. ./runtime.env
"$ABREX_JOB_DOCTOR_PYTHON" -c \
  'import json; r=json.load(open("doctor-report.json", encoding="utf-8")); assert r["complete"], r; print("doctor complete")'
```

Continue only after the last command prints `doctor complete`. If it fails,
copy `doctor-report.json` and the terminal error back for diagnosis; do not
reinstall the runtime first.

### 4. Run one job

For a server that permits short work on the current node, run:

```bash
./run-all.sh
```

`run-all.sh` runs the one PLOD job and creates the result ZIP. On a Slurm
cluster, use this instead:

```bash
sbatch submit.slurm
squeue -u "$USER"
```

After the array job disappears from `squeue`, inspect its output and package
the result:

```bash
tail -n 50 slurm-*.out
./collect-results.sh
```

Either route must create:

```text
abrex-results-aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb.zip
```

Verify it exists before copying it back:

```bash
test -s abrex-results-aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb.zip
sha256sum abrex-results-aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb.zip
```

### 5. Import the returned ZIP on Windows

Copy the result ZIP into the ABREX project root. Then run in PowerShell:

```powershell
Set-Location C:\Users\leamanjr\projects\abrex
$result = ".\abrex-results-aa9203f6c86cd5cd6664ffba112d538cc5a4ee9b1d4fb74599413c07aba2d0bb.zip"
if (-not (Test-Path -LiteralPath $result -PathType Leaf)) { throw "Missing $result" }
.\env313\Scripts\python.exe -m abrex jobs import `
  .artifacts/T060/plod-spans-followup `
  $result `
  --into .artifacts/T060/imported-linux-results
if ($LASTEXITCODE -ne 0) { throw "PLOD span result import failed" }
```

Keep the ZIP until ABREX has inspected the imported detector-span artifact.

## Part B: one-question T061 assisted review on Windows (complete)

The pair was accepted and the readiness check reports 1/1 complete. The
instructions below are retained for audit and recovery only.

### 1. Start or resume

Open a second PowerShell window in the repository root and run:

```powershell
Set-Location C:\Users\leamanjr\projects\abrex
.\scripts\Review-T061.ps1
```

The command checks the environment and minimal packet, prints current
progress, opens `http://127.0.0.1:8765`, and keeps serving until you press
Ctrl+C. If the browser does not open automatically, open that address manually.

### 2. Make the one required decision

The page asks only whether the passage defines `SR-BI` as
`scavenger receptor class B type 1`. Choose **Supported** or **Unsupported**,
then click **Save and next incomplete**. Do not redo the whole-passage search
or edit relation details: those fields are already carried forward or
mechanically determined. Use **Not sure** only if the displayed passage truly
does not permit a decision; it intentionally leaves T061 incomplete.

`Not sure` and a whole-passage status other than `Searched` deliberately leave
the passage incomplete. Method identities can remain hidden unless they are
needed diagnostically.

The resumable working file is:

```text
evidence/T061/review-packet-minimal.annotations.json
```

### 3. Pause, resume, and check completion

Save the current passage before pressing Ctrl+C. Run the same launch command
later to resume. To check completeness without starting the web server:

```powershell
.\scripts\Review-T061.ps1 -Check
```

The check succeeds only after that one support decision is saved. At
completion it prints:

```text
READY: the T061 assisted review is complete.
```

Download a **JSON backup** from the page as an additional recovery copy, but
leave the working sidecar in its location for T062.
