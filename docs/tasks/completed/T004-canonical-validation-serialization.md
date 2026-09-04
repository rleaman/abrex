# T004 completion note

## Changed

- Added strict/permissive canonical validation with immutable,
  location-aware `ValidationIssue` values and `ValidationSummary` audit
  counts for repaired, dropped, ambiguous, and unscoreable data.
- Added versioned deterministic canonical JSONL serialization with complete
  document, annotation, provenance, and prediction metadata round-tripping.
- Added path-independent SHA-256 dataset fingerprints and immutable JSON
  manifests containing adapter, normalizer, configuration, source, count, and
  validation identity.
- Added artifact-pair loading with fingerprint/count corruption detection and
  the YAML-composed `corpus build` CLI command.
- Added a reviewed golden JSONL fixture plus validation, round-trip,
  fingerprint, manifest, corruption, and CLI repeatability tests.

## Verification

Using the repository's Python 3.13 environment:

- `python -m ruff format --check src tests`
- `python -m ruff check src tests`
- `python -m mypy`
- `python -m pytest tests/unit tests/contract`
- `python -m pytest --cov --cov-report=term-missing`

## Unresolved issues

Incomplete and overlapping annotations are surfaced as audit classifications;
their scoring behavior remains intentionally deferred to T006 matching policy.
Dataset-specific source-coordinate conversion and artifact storage/atomic
publication remain future concerns.
