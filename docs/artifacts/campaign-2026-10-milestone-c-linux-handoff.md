# Milestone C Ab3P and PLODv2 Linux handoff

Status: **prediction-only bundle ready for a fresh Linux server**

The deterministic archive is:

`C:\Users\leamanjr\projects\abrex\.artifacts\campaign-2026-10\milestone-c\abrex-milestone-c-linux-bundle-v1.zip`

- Bundle ID: `1bad70d5276022c986d47dc32f4dd1dc1b0a9317b72ffb18291d40467ce42e4f`
- SHA-256: `9b3f4fa02c0029bbca03b2ed17cfb24e4a081791abeb6a322d1f0ae10c62f53d`
- Contents: 160 files, 120 immutable prediction-only documents for each job
- Gold annotations and credentials included: no

Copy that one ZIP to an internet-connected Linux server with Python 3.13, Git,
Make, a C++ compiler, curl, and `sha256sum`. Extract it, enter the extracted
directory, and run:

```bash
chmod +x setup-runtime.sh doctor.sh run-job.sh run-all.sh collect-results.sh
./setup-runtime.sh --check
./setup-runtime.sh --all
./doctor.sh
./run-all.sh
```

If Python 3.13 is not named `python3.13`, first load the server's Python module
or set `ABREX_BOOTSTRAP_PYTHON=/absolute/path/to/python3.13`. The setup uses
standard-library `venv`, downloads and verifies the pinned PLOD checkpoint,
builds the pinned Ab3P sources, and is resumable. Do not substitute the
historical WSL paths.

`doctor.sh` must report `"complete": true` before execution. Successful
completion prints a result path named:

`abrex-results-1bad70d5276022c986d47dc32f4dd1dc1b0a9317b72ffb18291d40467ce42e4f.zip`

Copy that result ZIP back into the Abrex project; no renaming or unpacking is
needed. Then reply:

> Linux results returned

The campaign owner will locate, validate, and import it. Archive release
metadata is recorded in
`evidence/campaign-2026-10/milestone-c/linux-bundle-release-v1.json`.
