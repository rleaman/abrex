# T013 completion note

## Changed

- Added the standalone `abrex.candidates` package with immutable candidates,
  generation results, diagnostics, generator metadata, records, and artifacts.
- Added the injectable `GENERATORS` registry and typed YAML pipeline composition
  with explicit generator selection and optional duplicate pruning.
- Added the conservative `parenthetical` generator. It enumerates every
  preceding word window within the configured limit and reports invalid,
  short, long, or context-free parentheticals as pruning diagnostics; it does
  not perform abbreviation acceptance or evaluation.
- Added deterministic `candidates-v1` JSONL serialization, readback validation,
  fingerprints, public extension-point documentation, and focused tests.

## Verification

- `env313\Scripts\python.exe -m ruff format --check src tests` — passed.
- `env313\Scripts\python.exe -m ruff check src tests` — passed.
- `env313\Scripts\python.exe -m mypy` — passed.
- `env313\Scripts\python.exe -m pytest tests/unit/test_candidates.py` — 6
  passed.
- Repository unit/contract gate — 125 passed with elevated filesystem access.

## Unresolved issues

The initial generator intentionally supports only non-nested parenthetical
short forms with ASCII alphanumeric/hyphen syntax and preceding word windows.
Reverse-order, nested, punctuation-rich, and corpus-specific constructions
remain proposed follow-up generator variants rather than implicit behavior.
