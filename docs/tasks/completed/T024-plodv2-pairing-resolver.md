# T024 completion note

## Changed

- Added typed pairing configuration, `PairCandidate`, `PairingResult`, and
  injectable pairing strategy protocols in `src/abrex/resolvers/plod_pairing.py`.
- Added `position_anchored` and named `pattern_greedy` strategies with explicit
  max-gap, reverse-order, local-pattern, one-to-one/shared-long-form, tie and
  duplicate behavior. Local pattern checks inspect only the candidate's actual
  between-span slice and adjacent closing context; they do not search the
  document globally.
- Added the registered `plodv2_pairing` resolver, preserving detector identity,
  standalone span scores, separate pair score, pairer identity, and cache
  configuration identity.
- Documented configuration and the scientific distinction between span and
  pair scores in `docs/resolvers.md`.

## Verification

- `env313\Scripts\python.exe -m pytest tests/unit/test_plod_pairing.py -q` —
  passed, 3 tests covering remote-pattern regression, shared-form/overlap
  policy, and resolver-contract output.
- Ruff format/check and strict mypy for the changed pairing implementation and
  tests — passed.
- The repository fast gate will be run after this task's documentation and
  registry changes; its known OneDrive temporary-directory behavior is
  retried with elevated access when needed.

## Scientific limits

The greedy strategy is explicitly named and not presented as optimal. Pair
selection, reverse order, distance, local pattern requirements and shared-form
behavior remain configuration choices; no universal scientific policy is
silently asserted. Real checkpoint inference remains subject to the T023 WSL
environment limitation recorded in its completion note.

## Next ready task

T031 is ready after T022 and T024. It may begin with the historical comparison
inputs and must report detection versus pairing loss separately.
