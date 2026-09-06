# T012 completion note

## Changed

- Added the registry-backed `schwartz_hearst` resolver with a dependency-free
  close transcription of the published backwards character-alignment
  algorithm over canonical document text.
- Added typed YAML parameters for minimum short-form length, long-form word
  window, punctuation handling, and case handling, with stable version metadata.
- Added exact canonical span reconstruction, public resolver exports, a YAML
  example, and documentation of the citation and deliberate deviations
  (parenthetical short-form order only; no nested/reverse-order fallback).
- Enforced the Schwartz--Hearst word-initial rule for the first short-form
  character and the default `min(|SF| + 5, 2|SF|)` candidate word window.
- Added unit/contract coverage for matching, rejection, configuration, registry
  composition, and metadata propagation.

## Verification

- `env313\Scripts\python.exe -m ruff format --check src tests` — passed.
- `env313\Scripts\python.exe -m ruff check src tests` — passed.
- `env313\Scripts\python.exe -m mypy` — passed.
- `env313\Scripts\python.exe -m pytest tests/unit tests/contract` — 119 passed
  (with elevated filesystem access for pytest temporary files).
- `env313\Scripts\python.exe -m pytest --cov --cov-report=term-missing` — the
  focused task tests passed; repository-wide coverage is governed by the
  documented 95% floor.

## Unresolved issues

Reverse-order and nested-parenthesis constructions, alternate boundary rules,
and corpus-specific scientific variants remain out of scope and should be
introduced only as separately named/configured strategies.

The earlier coverage snapshot in this historical note predates the repository
quality-policy correction. The current repository-wide gate uses the deliberate
95% floor documented in `docs/testing-and-quality.md`.
