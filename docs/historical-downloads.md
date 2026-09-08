# Historical dataset downloads

Each checked-in file under [`configs/datasets/`](../configs/datasets/) is one
declarative source bundle. The configuration-driven group is in
[`configs/dataset-groups.yaml`](../configs/dataset-groups.yaml). Run from the
repository root:

```console
abrex datasets download --config configs/datasets/ab3p.yaml
abrex datasets download-all --group historical
```

The downloader processes sources in declared order, waits only between actual
network requests, retries transient failures with exponential backoff, writes
atomically through `.part` files, verifies an optional SHA-256, and safely
extracts ZIP/TAR archives. Each completed source gets a versioned
`.download.json` record containing its source/extraction identity, archive
digest, and deterministic output fingerprint.

Rerunning a completed command reports `reused` and makes no request. Missing
items report `planned` in a dry run and are downloaded normally. A missing,
changed, corrupt, or untrusted sidecar reports `conflict`; use `--force` to
replace that selected artifact after the replacement has been staged and
verified. Group runs continue through independent conflicts and failures and
return a nonzero exit code if either occurs. `--force` is never implied by a
group: group execution ignores legacy `downloads.overwrite: true` unless
`--force` is explicitly supplied. Single-bundle legacy invocations still
accept that field, but new commands should use the explicit CLI option.

Dry runs resolve and inspect every item without network requests, writes, or
destination changes:

```console
abrex datasets download-all --group historical --dry-run
```

The former positional aggregate command remains accepted during migration:

```console
python -m abrex datasets download configs/historical-datasets.yaml
```

It is a bounded compatibility manifest retained for existing automation; new
source definitions are authoritative in the per-bundle files and the group.

SourceForge corpus archives are extracted under `data/raw/historical/`.
SDU@AAAI-21 files are downloaded individually because the repositories publish
the JSON files directly. The official SDU@AAAI-22 AE repository is downloaded
from its `main` branch and extracted as a whole because it does not publish a
stable single-file release. The SDU download strips GitHub's repository root
directory, so the checked-in English scientific training config expects
`data/english/scientific/train.json` beneath `data/raw/historical/sdu_aaai22/`.
The resulting files remain user-managed source material; inspect the extracted
layout if you select another language/domain split and adjust that YAML path
explicitly.

Downloading only acquires raw files; it never normalizes or builds a corpus.
After acquisition, use the runnable configurations and commands in
[historical-builds.md](historical-builds.md).

The URLs in the manifest were resolved from the project references in
`docs/notes-for-later.md`: BioC's `SH-BioC.zip`, `Ab3P-BioC.zip`,
`BioADI-BioC.zip`, and `MEDSTRACT.zip`; the AAAI-21 AI/AD repository JSON
files; and the AAAI-22 repository archive. The BADREX corrected URLs remain
historical notes only: they return 404 and are not in the current manifest.
