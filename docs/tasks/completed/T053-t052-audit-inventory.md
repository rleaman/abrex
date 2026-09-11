# T053 Build the targeted T052 audit inventory

Status: Engineering complete; human audit questions remain open.

## Delivered

- Added the typed-boundary builder in `src/abrex/literature/audit_inventory.py`
  and the reproducible entry point `scripts/build_t053_audit_inventory.py`.
- Validated the frozen T052 packet, final annotation state, packet identity,
  bundle file hashes and source-manifest identity before materializing outputs.
- Produced 60-case/current-decision reconciliation: 60 cases, 60 annotated
  cases, 105 current decisions, 26 additions, 6 corrected origins and 2
  rejected suggestions.
- Selected 12 targeted cases after case-level deduplication, retaining all
  applicable reasons, plus 8 unchanged accepted controls from 8 article groups
  using seed `20260908`. The control denominator was 28 and there was no
  shortage.
- Reported the 13 additions in the two lipid passages as 8 additions in
  `case-1a4f2e3443392fdca836` and 5 in
  `case-8deab3bbe026a86e6b5c`.
- Recorded the seven requested questions with source-text references and
  half-open offsets. They are explicitly questions, not automatic corrections
  or adjudicated facts.

## Artifacts and identities

- [audit-packet.json](../../../evidence/T053/audit-packet.json) — full passage
  packet for 20 selected cases; SHA-256
  `129d0ec198641cb862f3f6b6e5987d0f1c7e3222cdfa5334e61882e9ef27a4ab`;
  content identity `e204dfb865de780ce8e8de512343f6c9cf85f99bcbfe763c4316fef33486c8da`.
- [inventory.json](../../../evidence/T053/inventory.json) — current-only
  decisions, selection denominators/reasons, addition report and questions;
  SHA-256
  `852bef5430e144ec1a2dfce86a1fe41e567e1fb12ef72b90ad230382eedc26e0`;
  content identity `c01c76d6e9f5fb7ec58f6ccb9f6488780f416d9b139fb5f626224b7f324a35d8`.
- [question-sheet.md](../../../evidence/T053/question-sheet.md) — concise
  human question sheet; SHA-256
  `eb61692b86c26c673c26547875dbdbe8ed47d16c2d373bd069b6aab2f1360684`.

## Reproduction

```powershell
.\env313\Scripts\python.exe scripts\build_t053_audit_inventory.py
```

## Checks

- Focused: `pytest tests/unit/test_t053_audit_inventory.py -q --basetemp .pytest-tmp/T053-focused` — **2 passed**.
- Standard fast checks: Ruff format — **171 files formatted**; Ruff — **passed**; mypy — **no issues in 171 source files**; `pytest tests/unit tests/contract --basetemp .pytest-tmp/T053-fast -q` — **354 passed**.
- Canonical gate: `scripts/quality_gate.py --python .\env313\Scripts\python.exe` — **passed** after clearing only its generated `.pytest-tmp/t017-fast` directory; final run reported **354 passed**.
- `git diff --check` — **passed**; Git emitted only existing LF/CRLF normalization warnings for unrelated documentation files.

No T054 work or user annotation was performed. The next dependency is the
separately assigned human review of this question sheet; no scientific
decision is implied by this preparation task.
