# T015 completion note

## Changed

- Added the registry-backed `abrex.scorers` package with typed scorer,
  persistence, calibration, selection, split-manifest, and materialization
  contracts.
- Added deterministic child-seed derivation, finite-score validation, explicit
  train/dev/test document assignments, and model sidecar manifests protected by
  model and feature-schema fingerprints.
- Added the neutral identity calibrator and explicit fixed-threshold policy;
  no model family, label semantics, objective, split generation, or hidden
  threshold was introduced.
- Added the YAML-selectable `learned_scorer` resolver adapter, which hosts a
  persisted scorer through the existing resolver executor and prediction
  artifact path.
- Exposed the persisted model SHA-256 as resolver cache identity so an
  overwritten model artifact cannot reuse predictions produced by an older
  model at the same path.
- Extended optional resolver prediction metadata and versioned serialization
  to retain model-artifact and feature-configuration fingerprints while
  preserving existing artifact output when those fields are absent.
- Added public scorer documentation and YAML/JSON examples.

## Verification

- `env313\\Scripts\\python.exe -m ruff format --check src tests`
- `env313\\Scripts\\python.exe -m ruff check src tests`
- `env313\\Scripts\\python.exe -m mypy`
- `env313\\Scripts\\python.exe -m pytest tests/unit tests/contract` — 143 passed.
- Full `env313\\Scripts\\python.exe -m pytest` — 146 passed.
- `env313\\Scripts\\python.exe -m pytest --cov --cov-report=term-missing` —
  all 146 tests passed, but the repository's then-existing `fail-under=100`
  coverage gate was unmet at 96.51%; uncovered legacy branches and new defensive
  error branches are listed by Coverage and are not scientific failures.

## Unresolved issues

No scientific scorer or label policy is selected by T015. A project-specific
follow-up must register the intended model, label construction, optimization
target, split rationale, calibration method, and threshold/ranking policy
before reporting scientific results.

The historical coverage snapshot above predates the repository-wide policy
correction; the current declared floor is 95%, and the full current suite
passes that floor.
