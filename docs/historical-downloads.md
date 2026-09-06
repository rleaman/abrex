# Historical dataset downloads

The checked-in [download manifest](../configs/historical-datasets.yaml) is a
declarative source-acquisition list. It does not download anything by itself.
Run from the repository root:

```console
python -m abrex datasets download configs/historical-datasets.yaml
```

The downloader processes sources sequentially, identifies itself with a
research user-agent, waits between requests, retries transient failures with
exponential backoff, writes atomically through `.part` files, verifies an
optional SHA-256, and safely extracts ZIP/TAR archives. Each completed source
gets a `.download.json` record containing its URL and digest.

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
`BioADI-BioC.zip`, and `MEDSTRACT.zip`; the two BADREX corrected files; the
AAAI-21 AI/AD repository JSON files; and the AAAI-22 repository archive.
