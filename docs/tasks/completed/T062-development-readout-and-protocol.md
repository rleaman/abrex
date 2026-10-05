# T062 completion — development recovery readout and protocol

Completed October 4, 2026.

## Outcome

T061 was incorporated as a versioned assisted supplement without changing the
frozen T057 evidence. The updated view contains 67 strict exact relations, 12
diagnostic relations, and no unresolved relations. Eight strict relations are
new in T061.

The primary occurrence-level results are:

| Method | TP | FP | Outside target | FN | F1 |
|---|---:|---:|---:|---:|---:|
| Schwartz–Hearst | 36 | 6 | 1 | 31 | 0.661 |
| PLODv2 pairing | 34 | 1 | 1 | 33 | 0.667 |
| Ab3P | 35 | 12 | 1 | 32 | 0.614 |
| split-question Jev | 25 | 11 | 2 | 42 | 0.485 |
| Schwartz–Hearst + PLOD exact union | 45 | 7 | 2 | 22 | 0.756 |

PLODv2 pairing contributes nine correct pairs absent from Schwartz–Hearst with
one additional false positive. T062 therefore recommends freezing the existing
`transparent_hybrid` exact union of Schwartz–Hearst and PLODv2 pairing as the
sole challenger against the fixed Schwartz–Hearst baseline. Jev is not advanced
to this fresh check.

## Artifacts

- `docs/artifacts/T062-development-readout.json` — SHA-256
  `d5ad3578d2c26ae94a1a854fecc8ad6552b5948f48e1a1ed652692723690e307`
- `docs/artifacts/T062-development-readout.md` — SHA-256
  `0fabfa72faffb6a5f585387801ff04111228cb589f06f41c9ff05f9d72624e25`
- `evidence/T062/development-ledger-v1.json` — SHA-256
  `1e4ff9f3d562158f3098a38a64df78d5374d3489c4f51bb9844710a74c3bfeec`
- `evidence/T062/recovery-table-v1.jsonl` — SHA-256
  `0905d2dd95d11df2561265da8dfb4cafc3f79a073ad175fc1efd801ae930ec7c`
- `evidence/T062/prediction-dispositions-v1.jsonl` — SHA-256
  `2a9f95e67227d4889c7699743024b0f362356db67779f37ee2a2266385736677`
- `docs/artifacts/T063-decision-prefill.json` — SHA-256
  `28b05dec035a71009808765929f966c1a9bc66e884c4a461576a0a3f89543816`

Rebuild with `scripts/build_t062_readout.py`.

## Verification

- Canonical fast gate: 421 passed, one skipped; source import, Ruff, and strict
  mypy all passed.
- Full gate: 425 passed, one skipped; 95.13% statement coverage, above the 95%
  floor.
- `git diff --check`: passed (line-ending conversion notices only).

## Limits and next dependency

This is assisted development evidence and is not a population estimate or an
independent evaluation. The all-method gold-assisted oracle reaches 47/67
strict pairs (70.15% recall) and is not deployable. Human review elapsed time
was not measured retrospectively.

T063 now awaits one bundled scientific-lead confirmation. No fresh T065 source
acquisition is authorized until that confirmation is recorded.
