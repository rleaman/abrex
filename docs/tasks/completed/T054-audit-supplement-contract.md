# T054 Add a versioned audit supplement contract

Status: Engineering complete; no human audit or adjudication performed.

## Delivered

- Added `src/abrex/literature/audit_supplement.py`, an immutable Pydantic
  contract linked to T052 packet/state hashes and the T053 audit-packet hash.
- Preserved exact Unicode anchors and ordered multi-fragment evidence, explicit
  reconstructed interpretations without fabricated coordinates, alternatives,
  source-error proposals, separate caption/table scope, per-relation decisions,
  passage-search status, and revision exposure metadata.
- Added durable JSON read/write with content identity validation, UTF-8 and
  `fsync`-before-replace atomic saves, and explicit stale/corrupt-input errors.
- Kept the existing T052 JSON and BioC interchange unchanged and documented the
  new JSON-only authoritative contract in
  [audit-supplement-schema.md](../../audit-supplement-schema.md).

## Checks

- Focused: `.\env313\Scripts\python.exe -m pytest tests/unit/test_t054_audit_supplement.py --basetemp .pytest-tmp/T054-focused-final -q` — **5 passed**.
- Ruff format: `.\env313\Scripts\python.exe -m ruff format --check src tests` — **173 files already formatted**.
- Ruff lint: `.\env313\Scripts\python.exe -m ruff check src tests` — **All checks passed**.
- Mypy: `.\env313\Scripts\python.exe -m mypy` — **no issues found in 173 source files**.
- Unit/contract suite: `.\env313\Scripts\python.exe -m pytest tests/unit tests/contract --basetemp .pytest-tmp/T054-fast-final -q` — **359 passed**.
- Canonical gate: `.\en v313\Scripts\python.exe scripts/quality_gate.py --python .\env313\Scripts\python.exe` — **passed**, including source-import verification, format, Ruff, mypy, and **359 passed**.
- `git diff --check` — **passed**; Git emitted only the existing LF/CRLF normalization warning for `src/abrex/literature/__init__.py`.

The first clean-basetemp fast-suite attempt had one transient Windows
`PermissionError` in the unrelated legacy download-sidecar test; a fresh
task-owned basetemp passed all 357 tests, and the final suite passed all 359.

No T055 work and no user annotation were performed.
