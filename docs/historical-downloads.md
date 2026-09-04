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
the JSON files directly. The AAAI-22 repository is archived and extracted as a
whole because it does not publish a stable single-file release. The resulting
files remain user-managed source material; inspect the extracted layout and
pass the appropriate file to the T011 adapter configuration.

The URLs in the manifest were resolved from the project references in
`docs/notes-for-later.md`: BioC's `SH-BioC.zip`, `Ab3P-BioC.zip`,
`BioADI-BioC.zip`, and `MEDSTRACT.zip`; the two BADREX corrected files; the
AAAI-21 AI/AD repository JSON files; and the AAAI-22 repository archive.
