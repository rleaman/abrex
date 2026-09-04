# T003 completion note

## Changed

- Added typed `CorpusAdapter` and `NormalizationStep` contracts with explicit
  parse, source-to-canonical mapping, normalization, and validation stages.
- Added immutable source-resource and parsed-record descriptors, injectable
  corpus/normalizer registries, deterministic `CorpusPipeline` composition,
  and strict/permissive build behavior.
- Added machine-readable diagnostics for observations, repairs, dropped rows,
  mapping failures, duplicate record IDs, and source provenance.
- Added embedded fixture adapter data containing clean, malformed, and
  repairable records, plus the `trim_captured_text` and `identity` normalizers.
- Documented the extension point and added a YAML composition example.

## Verification

Using the repository's Python 3.13 environment:

- `python -m ruff format --check src tests`
- `python -m ruff check src tests`
- `python -m mypy`
- `python -m pytest tests/unit tests/contract`
- `python -m pytest --cov --cov-report=term-missing`

## Unresolved issues

Canonical artifact serialization, manifests, and full validation issue models
remain scoped to T004. Dataset-specific adapters and source-coordinate
conversion policies remain future work; no corpus inclusion, split, or scoring
policy was introduced.

