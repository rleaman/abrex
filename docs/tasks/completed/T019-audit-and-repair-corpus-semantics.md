# T019 completion note

## Changed

- Repaired the historical BioC XML/JSON adapter to preserve source passage
  text by default and to use a named semantic policy for relation pairing,
  annotation text overlays and multiple locations.
- Added diagnostics for missing/invalid locations, discontinuous locations,
  annotation-text disagreements, malformed or dangling relations, duplicate
  IDs and unpaired/unequal entities. Source entities are retained as partial
  annotations where the canonical model permits it; otherwise the loss is
  counted in the diagnostic stream.
- Added typed `CorpusSemanticsConfig` metadata to all current historical YAML
  configurations. SDU AI, AD and AE remain distinct: AD has no manufactured LF
  span and is not an `exact_pair` benchmark; AE uses independent `exact_span`
  evaluation and never pairs its lists by order.
- Added XML/JSON equivalence, source-text preservation, order-fallback,
  unequal-list, dangling-relation, duplicate-ID and multi-location regression
  coverage.
- Added [`audit_historical_corpora.py`](../../../scripts/audit_historical_corpora.py),
  [`historical-corpus-inventory.md`](../../historical-corpus-inventory.md) and
  the compact [`historical-corpus-audit.json`](../../artifacts/historical-corpus-audit.json).
  Raw sources and generated canonical JSONL remain ignored.
- Recorded the BADREX-corrected variants as excluded under the settled
  availability decision; no new BADREX source discovery or configuration was
  performed.

## Real-source audit

Command:

```powershell
.\env313\Scripts\python.exe scripts/audit_historical_corpora.py --output docs/artifacts/historical-corpus-audit.json
```

The seven locally supplied source configurations built successfully through
the canonical pipeline. The report records full source and canonical
fingerprints; the main counts were:

| Variant | Raw records / annotation units | Canonical records / annotations | Eligible metric / units |
| --- | ---: | ---: | ---: |
| Ab3P | 1,250 / 2,446 | 1,237 / 1,174 | `exact_pair` / 1,174 |
| BIOADI | 1,201 / 3,440 | 1,185 / 1,670 | `exact_pair` / 1,670 |
| MEDSTRACT | 198 / 318 | 197 / 156 | `exact_pair` / 156 |
| Schwartz & Hearst | 1,000 / 1,958 | 991 / 944 | `exact_pair` / 944 |
| SDU@AAAI-21 AI train | 14,006 / 37,501 | 14,006 / 14,006 | `exact_pair` / 10,575 |
| SDU@AAAI-21 AD train | 50,034 / 50,034 | 50,034 / 50,034 | `not_scoreable` / 0 |
| SDU@AAAI-22 AE English scientific train | 3,980 / 13,404 | 3,980 / 13,404 | `exact_span` / 13,404 |

The BioC audit found discontinuous annotations in Ab3P/BIOADI/MEDSTRACT/
Schwartz & Hearst at 23/14/1/10, respectively. Source-text mismatches and
record drops are retained in the processed manifests rather than repaired by
overlay. The report includes the exact diagnostic counts and SHA-256 values.

## Verification

- Focused historical tests: `22 passed`.
- Strict mypy: passed, 109 files.
- Ruff format check and lint: passed for `src`, `tests` and the audit script.
- Unit/contract suite: `176 passed`.
- Full suite with coverage: `176 passed`, `95.16%`, above the configured 95%
  floor.
- `git diff --check`: passed.
- Real-source audit/build: all seven local variants built successfully; raw
  and processed counts are documented above and in the audit artifact.

## Open scientific decisions

The legacy domain model represents a discontinuous BioC annotation with its
first location under the explicitly configured `first_location` policy; the
complete location list and resulting validation effects remain auditable, but
this is not a claim that the source annotation is scientifically equivalent
to one contiguous span. Source licensing terms and benchmark validity remain
for review. No baseline resolver scores were claimed by this task.

## Next ready task

T020: make Ab3P runtime/resource lookup and cache identity reliable.
