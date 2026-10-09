# Milestone C Ab3P and PLODv2 Linux handoff

Status: **completed and returned; retained for provenance**

The replacement archive was returned, imported, and validated on October 7,
2026. No further Linux action is required. See
[`campaign-2026-10-milestone-c-linux-result.md`](campaign-2026-10-milestone-c-linux-result.md)
for the result and immutable receipt. The instructions below are retained only
to reproduce the server execution.

The first server attempt established that Python, the embedded source, Ab3P,
and PLODv2 were all available. Ab3P then rejected an internally inconsistent
native short-form offset for `WT` in `milestone-c-60282f673febc655719c`.
The passage is a single ASCII line, so this was not an encoding or line-origin
conversion problem. The strict mapper correctly refused to guess between the
two `WT` occurrences. Because the v1 launcher stopped on the first failed job,
PLODv2 did not run and no return archive was produced. The reported result is
preserved in `linux-bundle-v1-failure-receipt.json`.

The replacement archive is:

`C:\Users\leamanjr\projects\abrex\.artifacts\campaign-2026-10\milestone-c\abrex-milestone-c-linux-bundle-v2.zip`

- Bundle ID: `a1d57ed9ee18e1fc88ebe85e01ae33dddf3c3b853f32065b0ccf778dba1777be`
- SHA-256: `cc0f20b69b35997c67c6d53fe127963b3bb7aee79e1cf4123d4189296596f3c8`
- Contents: 160 files and 120 immutable prediction-only documents per job
- Gold annotations and credentials included: no

## Reuse the verified server runtime

Copy the v2 ZIP to the same Linux server and extract it into a new empty
directory. From that directory, copy the `runtime.env` file next to the v1
scripts you already ran, then execute:

```bash
chmod +x setup-runtime.sh doctor.sh run-job.sh run-all.sh collect-results.sh
cp /path/to/extracted-v1/runtime.env ./runtime.env
./doctor.sh
./run-all.sh
```

The copied file contains persistent runtime paths, not credentials. The doctor
must report bundle ID
`a1d57ed9ee18e1fc88ebe85e01ae33dddf3c3b853f32065b0ccf778dba1777be`
and `"complete": true`. If the old `runtime.env` is unavailable, run
`./setup-runtime.sh --all` instead; it verifies and reuses the existing pinned
runtime resources before writing a new file.

The v2 scientific behavior remains strict: no offset is searched for, repaired,
or inferred. A native mismatch becomes a structured document failure, all
remaining documents continue, PLODv2 still runs, and the result archive is
always collected. Offset failures now record the reported byte span and the
actual source slice for diagnosis.

Successful completion prints this exact return path:

`abrex-results-a1d57ed9ee18e1fc88ebe85e01ae33dddf3c3b853f32065b0ccf778dba1777be.zip`

Copy that ZIP back into the Abrex project without renaming or unpacking it and
reply:

> Linux v2 results returned

The campaign owner will locate, validate, import, and analyze it. Release
metadata is recorded in
`evidence/campaign-2026-10/milestone-c/linux-bundle-release-v2.json`.
