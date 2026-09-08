# BioADI: installed WSL Java and working extraction smoke

The missing-Java blocker was resolved on September 7, 2026. Java is installed
under the WSL user's home; Windows and system Java settings are unchanged.

## Runtime and entry point

- Distribution: Eclipse Temurin JDK 8u504-b01, Linux x64.
- Java: `/home/rleaman/.local/share/abrex/java8/jdk8u504-b01/bin/java`.
- `jar`, `javap`, and `javac` are in the same `bin` directory.
- Installation metadata: `~/.local/share/abrex/java8/release.json`.
- Archive SHA-256, verified against the Adoptium release metadata:
  `9c70e102f527ac674ac2fe9c7d47b9a04e2d19842ba5ab8e9b33f368bbadfaea`.
- BioADI JAR: `.artifacts/T048/bioadi-0.1.0.jar`, SHA-256
  `62e92f3debc0b792c6ee0678a88c30102dec349c7f337befa427de232014975a`.

**Use `aiiaadi.util.Executor` explicitly.** This JAR's manifest selects
`spiaotools.SentParDetector`; `java -jar` does not select the BioADI extraction
entry point. No JAR modification or additional Java libraries were needed.

From PowerShell in the repository root, rerun the local five-record input:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mail/Documents/Projects/abrex && timeout 30s "$HOME/.local/share/abrex/java8/jdk8u504-b01/bin/java" -Xmx512m -Dfile.encoding=UTF-8 -cp .artifacts/T048/bioadi-0.1.0.jar aiiaadi.util.Executor .artifacts/bioadi-runtime/input.txt'
```

For an interactive WSL session, optionally set:

```bash
export JAVA_HOME="$HOME/.local/share/abrex/java8/jdk8u504-b01"
export PATH="$JAVA_HOME/bin:$PATH"
```

Use an explicit Java executable path in future typed resolver configuration;
do not rely on interactive shell setup for automated runs.

## Input/output evidence

The CLI reads numeric document-ID lines followed by text lines. Inspection of
its bytecode shows that it trims lines, skips empty lines, and joins text
lines with spaces. Thus its echoed text is not an offset-preserving copy of
arbitrary input. It prints the document ID, text, and indented rows resembling
`TNF|Tumor necrosis factor|0.9861388671823804`.

The bounded smoke produced the expected TNF and MRI definitions, no pairs for
the negative control, and TNF after a Unicode prefix. Two identical TNF
definitions in one document produced two rows. These rows contain no offsets;
duplicate rows alone do not identify individual mention positions.

See [machine-readable runtime evidence](artifacts/bioadi-runtime-smoke.json)
for exact inputs, outputs, command, version, hashes, and process result. Local
smoke inputs, raw output, bytecode inspection, and the verification helper
remain under ignored `.artifacts/bioadi-runtime/`.

The helper invokes Java with a 30-second timeout, checks the exit code and
stderr, and checks the expected five pair rows across five records. It runs
from a directory separate from the JAR to exercise resource lookup.

## T048 integration result

Runtime feasibility is positive for this small pilot. T048 now provides a
typed registry-backed resolver, explicit cache identity, bounded subprocess
execution, safe exact-occurrence mapping, and a real T022 resolver artifact.
The standard evaluator intentionally rejects the 51 execution failures in
that artifact; see the [T048 resolver report](artifacts/T048-bioadi-resolver-report.json)
for the conditional success-only result and the open abstention policy.

The CLI catches some exceptions and exits zero, so an exit code alone cannot
establish success. Do not treat the numeric score as calibrated confidence.

The original T048 report is historical evidence of the missing runtime, not
the current availability decision. The typed adapter and bounded T022
comparison are recorded in the current T048 completion note. No independent
BioADI benchmark claim or artifact licensing determination is made by this
environment setup.
