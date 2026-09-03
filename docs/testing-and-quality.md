# Testing and Quality Gate

## Repository-wide fast gate

The exact commands may differ by tooling, but provide a single documented command that runs:

- formatting check;
- linting;
- type checking;
- fast unit and contract tests.

A second full gate may include integration/regression tests and coverage.

## Target tooling

Recommended defaults:

- Python 3.13;
- pytest;
- pytest-cov;
- ruff;
- mypy;
- pre-commit;
- build/hatchling or another minimal PEP 517 backend;
- tox or nox only if it adds concrete value.

## Coverage

Do not chase a vanity global percentage. Set a meaningful floor for core pure-Python modules and require tests for new behavior. Critical matching, span, registry, config, and normalization logic should be exhaustively exercised.

## Contract tests

For every plugin protocol, create reusable contract tests that concrete implementations can opt into.

Examples:

- a `Resolver` returns objects with valid document IDs and spans;
- a `CorpusAdapter` yields deterministic record ordering or documents its ordering contract;
- a `Reporter` does not mutate its input result object;
- a `MatchingPolicy` is deterministic and order-invariant if the policy claims to be.

## Golden tests

Use small human-readable fixtures for high-value behavior. Golden outputs should be reviewed rather than generated and blindly accepted.

Appropriate golden targets include:

- canonical serialization for a handful of corpus records;
- Ab3P parsed output for representative constructions;
- exact evaluator match outcomes for difficult multi-pair cases;
- HTML/JSON report structure where stable.

## Property-based testing

Consider Hypothesis for span/matching/config invariants if it meaningfully improves assurance. It is particularly appropriate for interval logic, order invariance, serialization round-trips, and assignment/matching invariants.

## Performance tests

Do not optimize prematurely, but add microbenchmarks or dataset-scale timing once a real bottleneck appears. Performance work must preserve evaluation identity and deterministic behavior.
