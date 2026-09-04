# T006 completion note

## Changed

- Added immutable matching outcomes, per-document evaluation records, metric
  results, and aggregate evaluation results.
- Added the injectable `MatchingPolicy` and `Metric` protocols plus generic
  registry-backed YAML composition.
- Added deterministic `exact_pair` matching with one-to-one duplicate
  handling, explicit `unscoreable` incomplete annotations, and stable output
  independent of input ordering.
- Added micro pair-level TP/FP/FN, precision, recall, and F1 through the
  `pair_prf` metric, with explicit `zero` or `raise` zero-denominator modes.
- Added focused unit/contract coverage for duplicate predictions, repeated and
  crossing spans, empty inputs, multi-pair assignment, order invariance, and
  YAML registry injection.

## Verification

Using the repository's Python 3.13 environment:

- `env313\\Scripts\\python.exe -m ruff format --check src tests`
- `env313\\Scripts\\python.exe -m ruff check src tests`
- `env313\\Scripts\\python.exe -m mypy`
- `env313\\Scripts\\python.exe -m pytest tests/unit tests/contract`
- `env313\\Scripts\\python.exe -m pytest --cov --cov-report=term-missing`

The focused T006 suite passed. The full repository gate passed with elevated
access because the managed environment's global pytest temp directory is not
readable by the test process under the default sandbox.

## Unresolved issues

The initial exact policy excludes incomplete annotations from pair counts as
explicit `unscoreable` outcomes. Whether particular corpora should instead
score partial annotations as errors remains a scientific review decision for a
future named policy/configuration. Fuzzy matching, relaxed boundaries, text
normalization, and reporting artifacts remain out of scope.
