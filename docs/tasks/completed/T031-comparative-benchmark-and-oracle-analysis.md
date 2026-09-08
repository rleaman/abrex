# T031 completion: comparative benchmark and oracle analysis

## Delivered

- Added the typed comparative analysis and seeded document-group bootstrap
  implementation in `src/abrex/evaluation/comparative.py`.
- Added the pinned PLODv2 pairing benchmark configuration and
  `scripts/build_t031_comparison.py`, which validates dataset fingerprints and
  prediction artifacts before comparison.
- Built the real three-resolver matrix on the identical 64-record T022 smoke
  slice using Schwartz--Hearst, native-offset Ab3P and PLODv2 pairing under
  `exact_pair`.
- Added the tracked evidence report
  [`T031-comparative-analysis-report.json`](../../artifacts/T031-comparative-analysis-report.json)
  and deterministic core report alongside artifact fingerprints.

## Evidence

The 64-document slice contains 143 scoreable gold pairs. Results were:

| Resolver | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native-offset Ab3P | 121 | 4 | 22 | 0.9680 | 0.8462 | 0.9030 |
| PLODv2 pairing | 104 | 20 | 39 | 0.8387 | 0.7273 | 0.7790 |
| Schwartz--Hearst | 110 | 5 | 33 | 0.9565 | 0.7692 | 0.8527 |

The gold-assisted union recovered 130/143 pairs (0.9091). Unique correct
occurrences were 9 for Ab3P, 6 for PLODv2 and 2 for Schwartz--Hearst. These
figures measure attainable complementarity, not a deployable ensemble score.

## Verification

- Pinned PLODv2 CPU smoke with network disabled — passed.
- T031 PLODv2 experiment over all 64 records — passed; 0 execution failures.
- T031 comparison artifact validation and deterministic report build — passed.
- Existing analytical fixtures cover duplicate/repeated-definition union and
  seeded bootstrap behavior.

## Limitations and next task

This is an exploratory historical smoke slice selected by T022's hash-based
protocol, not a representative benchmark. Pair and span metrics remain
separate. Bootstrap groups default to document IDs because linked article-group
metadata was not supplied. The provisional T030 contemporary labels were not
used, and BioADI remains excluded pending an approved abstention/mapping policy.

T032 and T033 are now dependency-ready; T034 also requires T046, which is
already complete.
