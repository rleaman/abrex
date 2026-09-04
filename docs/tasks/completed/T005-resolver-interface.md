# T005 completion note

## Changed

- Added the typed `Resolver` protocol and injectable resolver registry.
- Added YAML composition for resolver selection plus explicit strict/permissive
  prediction validation and batch execution error policy.
- Added single-document and batch execution with immutable resolver metadata,
  validation diagnostics, structured execution errors, and preserved duplicate
  predictions.
- Added the deterministic `predictions-v1` JSONL artifact format, fingerprint,
  read/write helpers, and a small pattern-based toy resolver for contract and
  smoke testing.
- Documented the public resolver extension point and added a YAML example.

## Verification

Using the repository's Python 3.13 environment:

- `env313\\Scripts\\python.exe -m ruff format --check src tests`
- `env313\\Scripts\\python.exe -m ruff check src tests`
- `env313\\Scripts\\python.exe -m mypy`
- `env313\\Scripts\\python.exe -m pytest tests/unit tests/contract`
- `env313\\Scripts\\python.exe -m pytest --cov --cov-report=term-missing`

The final full gate passed: 64 tests and 100% statement coverage.

## Unresolved issues

Resolver-specific scientific algorithms, external-process adapters, evaluator
matching semantics, experiment-run metadata, and artifact atomic publication
remain scoped to later tasks. The toy resolver is intentionally not a
benchmark baseline.
