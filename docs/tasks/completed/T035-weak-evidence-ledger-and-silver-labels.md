# T035 completion: weak-evidence ledger and silver labels

## Delivered

- Added immutable `EvidenceRecord` values keyed by a content SHA-256 over
  document ID, exact half-open spans, source family/identity/version,
  polarity, weight, local context and iteration lineage.
- Added append-only `EvidenceLedger` insertion that is idempotent by evidence
  identity and collapses competing records to one vote per source family.
- Added typed `EvidenceAggregationConfig` and deterministic positive,
  negative, abstain and conflict/priority policies. Missing evidence remains
  abstain; gold annotations are not read or modified.
- Added `SilverLabel` lineage containing all contributing evidence IDs, the
  aggregation configuration, reason and transparent confidence, plus a
  helper that validates exact local context before recording evidence.

## Evidence and limitations

The focused truth-table fixtures cover duplicate insertion, same-family
deduplication, contradictory-family abstention and missing-evidence abstention
in `tests/unit/test_evidence.py`. This completes the engineering mechanism,
not silver-label accuracy validation: no approved multi-source reviewed set is
available in the bounded repository artifacts. The existing T032/T034 source
family distinctions must be supplied by future evidence builders; correlated
teacher outputs must not be counted as independent truth.

## Verification

- Focused T035 tests: 2 passed.
- Targeted strict mypy and Ruff: passed.
- Repository unit/contract fast gate: run before commit.

## Next ready task

T036 is ready to build bounded contextual pattern induction on top of explicit
evidence and silver-label lineage.
