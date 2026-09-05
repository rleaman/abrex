# T010 completion note

## Changed

- Added the typed `abrex.experiments` application service and the thin
  `abrex experiment run` CLI command.
- Added content-addressed prediction caching protected by canonical corpus
  fingerprint, resolver configuration, and resolver version, with artifact,
  document-span, metadata, and dataset-fingerprint validation on reuse.
- Added deterministic evaluation/report artifacts and a `run-manifest-v1`
  manifest containing timestamps, Git state, resolved configuration, corpus,
  resolver, environment/package snapshot, seed, and artifact fingerprints.
- Added a checked-in end-to-end toy experiment YAML and configuration docs.

## Verification

The repository fast quality gate was run with the Python 3.13 environment:

- `env313\\Scripts\\python.exe -m ruff format --check src tests`
- `env313\\Scripts\\python.exe -m ruff check src tests`
- `env313\\Scripts\\python.exe -m mypy`
- `env313\\Scripts\\python.exe -m pytest tests/unit tests/contract`

The T010 end-to-end toy experiment was also run twice with cache reuse enabled;
the second run reused the validated prediction artifact and produced equivalent
evaluation output.

## Unresolved issues

The runner records environment versions for the core package and its direct
dependencies only; a complete lockfile/environment export remains a proposed
follow-up. Atomic artifact publication and richer CLI overrides are also
outside T010 scope.
