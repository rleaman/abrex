# T011 completion note

## Changed

- Added offline, registry-backed adapters for BioC XML/JSON sources, SDU
  acronym-identification JSON, and tab-separated corrected pair sources.
- Registered explicit variants for Schwartz & Hearst, its BADREX correction,
  Ab3P, BIOADI, MEDSTRACT, corrected MEDSTRACT, and SDU@AAAI-21/22.
- Preserved source coordinates/text and adapter variant identity in canonical
  provenance; reconstructed SDU offsets and pair-only document text are
  explicitly recorded as transformations.
- Added synthetic structural fixtures and adapter-specific tests, and
  documented source formats, offline/licensing expectations, and reconstruction
  choices.

## Verification

- Ruff format check: passed.
- Ruff lint: passed.
- mypy: passed (`55` source files).
- Unit/contract gate: passed (`88 passed`) with elevated filesystem access.
- Coverage run: `88 passed`, but repository coverage was `96.73%` and did not
  meet the then-configured 100% threshold because the new historical parser's
  defensive/error branches are not yet exhaustively covered.

## Unresolved issues

Real corpus downloads, licensing decisions, and dataset-specific source
quirks remain user-supplied and were not committed. Coverage follow-up should
add tests for malformed BioC/SDU/pair inputs and all parser branches before
claiming the repository-wide coverage gate is fully green.

## Addendum: T011 follow-up — runnable historical corpus build configs

### Completion summary

The T011 follow-up is complete. Every supported historical corpus with a
complete local raw source is now buildable through the existing T003/T004
registry-backed corpus pipeline and canonical JSONL/manifest serializer. No
corpus-specific ingestion or serialization path was introduced.

### Configurations added

Added the following repository-relative YAML configurations under
`configs/corpora/`:

- `ab3p.yaml` — adapter `ab3p_corpus`, source
  `data/raw/historical/ab3p_corpus/Ab3P_bioc_gold.xml`, output
  `data/processed/ab3p_corpus/`.
- `bioadi.yaml` — adapter `bioadi`, source
  `data/raw/historical/bioadi/bioadi_bioc_gold.xml`, output
  `data/processed/bioadi/`.
- `medstract.yaml` — adapter `medstract`, source
  `data/raw/historical/medstract/medstract_bioc_gold.xml`, output
  `data/processed/medstract/`.
- `schwartz_hearst.yaml` — adapter `schwartz_hearst`, source
  `data/raw/historical/schwartz_hearst/SH_bioc_gold.xml`, output
  `data/processed/schwartz_hearst/`.

Each configuration declares the adapter parameters, source identifier and
format, the explicit `identity` normalizer, `strict: false` permissive
validation, and canonical `canonical.jsonl`/`manifest.json` artifact names.
The adapter variant identity is preserved in both record provenance and the
T004 manifest adapter metadata.

### Orchestration and CLI changes

Added `configs/corpus-groups.yaml` with a configuration-driven `historical`
group. The new command:

```console
abrex corpus build-all --group historical
```

loads the named group and composes the same single-corpus build operation for
each listed configuration. The existing positional build syntax remains
supported, and the build command now also accepts:

```console
abrex corpus build --config configs/corpora/ab3p.yaml
```

When `--output` is omitted, the typed output section in the corpus YAML
selects the processed-artifact directory and filenames. Output directories are
created by the CLI; the canonical serializer remains the shared T004 path.
Downloading remains independent: `datasets download` only acquires and
records raw sources and never triggers normalization or building.

### Raw datasets detected locally

The following complete historical source sets were present under
`data/raw/historical/`:

- Ab3P: `Ab3P_bioc_corpus.xml`, `Ab3P_bioc_gold.xml`, and `Ab3P_gold.key`.
- BIOADI: `bioadi_bioc_corpus.xml`, `bioadi_bioc_gold.xml`, and
  `BioADI_gold.key`.
- MEDSTRACT: `medstract_bioc_corpus.xml`, `medstract_bioc_gold.xml`, and
  `MEDSTRACT_gold.key`.
- Schwartz & Hearst/BioText: `SH_bioc_corpus.xml`, `SH_bioc_gold.xml`, and
  `SH_gold.key`.

The checked-in download manifest also supports corrected BADREX sources
(`schwartz_hearst_badrex` and `medstract_badrex`) and SDU shared-task sources
(`sdu_aaai21_ai`, `sdu_aaai21_ad`, and `sdu_aaai22`), but their source files
were absent locally. The corrective follow-up now provides explicit configs for
all of these variants; they remain intentionally non-buildable until the
corresponding user-managed source files are downloaded.

### Processed artifact verification

The four individual build commands and the historical group command were run
successfully. The resulting ignored artifacts were verified as canonical JSONL
plus manifest pairs:

| Variant | Manifest adapter identity | Records | Schema |
| --- | --- | ---: | --- |
| Ab3P | `ab3p_corpus` | 1,237 | `canonical-v1` |
| BIOADI | `bioadi` | 1,185 | `canonical-v1` |
| MEDSTRACT | `medstract` | 197 | `canonical-v1` |
| Schwartz & Hearst/BioText | `schwartz_hearst` | 991 | `canonical-v1` |

Generated files under `data/processed/` were not committed; that directory
remains gitignored as intended.

Exact commands used from the repository root were:

```powershell
.\env313\Scripts\python.exe -m abrex corpus build --config configs/corpora/ab3p.yaml
.\env313\Scripts\python.exe -m abrex corpus build --config configs/corpora/bioadi.yaml
.\env313\Scripts\python.exe -m abrex corpus build --config configs/corpora/medstract.yaml
.\env313\Scripts\python.exe -m abrex corpus build --config configs/corpora/schwartz_hearst.yaml
.\env313\Scripts\python.exe -m abrex corpus build-all --group historical
```

### Tests and quality gate

Added configuration contract and end-to-end tests in
`tests/unit/test_historical_configs.py`, malformed historical parser coverage
in `tests/unit/test_historical_corpora.py`, and downloader safety/CLI tests in
`tests/unit/test_download_datasets.py`.

Final verification passed:

- Ruff format check: passed.
- Ruff lint: passed.
- mypy: passed (`59` source/test files).
- Full test suite: passed (`105 passed`).
- Repository coverage: passed (`100.00%`, configured threshold `100%`).
- `git diff --check`: passed.

The intended documented workflow is now:

```text
download historical data
    -> build canonical corpora
    -> run resolver
    -> evaluate
```

## Corrective follow-up

The repository now also registers `sdu_aaai21_ad` with a dedicated
acronym-index/expansion adapter and `sdu_aaai22_ae` with a dedicated
half-open-range extraction adapter. Runnable repository-relative configs and
the `historical` build group include these variants plus the BADREX corrected
sources. Their raw files remain intentionally uncommitted; the ordinary unit
config test validates paths without requiring private downloads.
