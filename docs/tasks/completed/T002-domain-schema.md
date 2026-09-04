# T002 completion note

## Changed

- Added immutable, format-neutral domain models for canonical documents,
  half-open text spans, abbreviation definitions, source-space provenance,
  prediction metadata, and corpus records.
- Added explicit validation for span invariants, document bounds, captured-text
  consistency, document identity, optional source coordinates, and confidence
  values.
- Kept source/gold semantics separate from resolver prediction metadata and
  documented incomplete annotations without coordinate inference.
- Added unit tests covering invalid and zero-length spans, Unicode and repeated
  text, overlapping spans, incomplete source annotations, provenance, and
  prediction metadata.

## Verification

Using the repository's Python 3.13 environment:

- `python -m ruff format --check src tests`
- `python -m ruff check src tests`
- `python -m mypy`
- `python -m pytest tests/unit tests/contract --cov --cov-report=term-missing`

All checks passed: 27 tests passed and coverage reached 100%.

## Unresolved issues

Matching semantics, duplicate handling, scoreability of partial annotations,
canonical serialization, and corpus-specific normalization remain explicit
responsibilities of later tasks. No policy for those concerns was introduced.
