# T067 completion — frozen fresh evaluation readout

Completed October 5, 2026.

## Outcome

The returned Linux archive matched bundle
`ab96b25c055f49832c3bfedc6c0e50cf87ddc59f8349b1decd38c7c1625c9966`.
Its doctor report was complete, both frozen jobs processed all 32 documents,
and neither job reported a runtime failure. The imported result identities are:

- Schwartz–Hearst: `c3af98e562e7d82d0cf5f2bb36aa121613c6435d117cd9aa55d7d664f19b1936`;
- PLODv2 pairing: `016681d43441d58a0f1f04bf400183034ab305398109986d913738721530e7ee`.

The predeclared challenger was the exact occurrence-level union of those two
methods. Its frozen comparison against Schwartz–Hearst is:

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Schwartz–Hearst | 6 | 10 | 26 | 0.375 | 0.188 | 0.250 |
| Exact union | 20 | 20 | 12 | 0.500 | 0.625 | 0.556 |

The challenger passed the F1, unique-addition, and runtime checks, but failed
the false-positive tolerance: it added 14 unique correct occurrences and 10
false positives, while the approved maximum was two. The primary result is
therefore **FAIL**. No post-reveal tuning or method substitution was performed.

## Arm-level interpretation

| Arm | Method | TP | FP | FN | F1 |
|---|---|---:|---:|---:|---:|
| Prose | Schwartz–Hearst | 4 | 3 | 5 | 0.500 |
| Prose | Exact union | 6 | 10 | 3 | 0.480 |
| Table/list | Schwartz–Hearst | 2 | 7 | 21 | 0.125 |
| Table/list | Exact union | 14 | 10 | 9 | 0.596 |

The union did not improve prose F1. Its table/list gain is scientifically
interesting but small and concentrated: article group `42543246` accounts for
14 challenger true positives, with one false positive, while several other
groups were neutral or worse. These eight paired article-group descriptions
are not population-weighted estimates and support neither a global promotion
nor post-hoc adoption of PLODv2 alone.

The supported stopping point is to retain Schwartz–Hearst as the current
global baseline. If T068 authorizes further work, the evidence favors a narrow
structural/table candidate-development task, evaluated on new independent
material, rather than the global exact union.

## Frozen artifacts and identities

- [Primary JSON report](../../artifacts/T067-fresh-evaluation-readout-v1.json)
  — content SHA-256
  `970be00933ed71b2022c9f29a5afabde5b6167c2ce294526938bfa816d377bcf`.
- [Concise readout](../../T067-fresh-evaluation-readout.md).
- [Prediction dispositions](../../../evidence/T067/prediction-dispositions-v1.jsonl).
- Returned archive: `.artifacts/T067/returned-results-v3.zip` — SHA-256
  `d043da479f58346ea655c71e7d4707428cc2c9ada21b6fd7b343c84c9bb2165e`.
- Frozen run-manifest SHA-256:
  `892475a4013cdb1362fee04796e64ed9a65f3f23746af4b83b4e619a1d836f9d`.
- Prediction artifact SHA-256 values: Schwartz–Hearst
  `26a69130b1dfb6c7e7aa527cffa476fc1ecbb37d973a9ab21cd539282ca33a90`;
  PLODv2 pairing
  `2ba5d79f67741a0720d57d5c1d93e6886b96e1ec7afd76710ab93b20cde46f15`.

The result archive remains under ignored `.artifacts`; its imported,
checksummed contents are reproducible inputs to the tracked readout.

## Verification

- The real-artifact readout rebuilt successfully against the imported result
  packages without changing its frozen identity.
- Focused T067 tests: 5 passed.
- Full repository gate: source-import verification, Ruff format and lint,
  strict mypy, and 435 tests passed with one skipped.
- Statement coverage: 95.00%, meeting the required 95% floor.
- `git diff --check`: passed (line-ending conversion notices only).

## Next dependency

[T068](../T068-human-next-direction.md) is now ready for the user's scientific
direction choice. It requires no further annotation or server setup.
