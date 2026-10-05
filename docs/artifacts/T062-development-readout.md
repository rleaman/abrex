# T062 development recovery readout

This is assisted development evidence, not a blind or population estimate.

## Revised development view

- Strict exact relations: 67
- New T061 strict relations: 8
- Diagnostic relations: 12

## Exact-pair results

| Method | TP | FP | Outside target | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ab3p | 35 | 12 | 1 | 32 | 0.745 | 0.522 | 0.614 |
| jev_candidate_judge | 25 | 11 | 2 | 42 | 0.694 | 0.373 | 0.485 |
| plodv2_pairing | 34 | 1 | 1 | 33 | 0.971 | 0.507 | 0.667 |
| schwartz_hearst | 36 | 6 | 1 | 31 | 0.857 | 0.537 | 0.661 |
| S&H + PLOD exact union | 45 | 7 | 2 | 22 | 0.865 | 0.672 | 0.756 |

## Recommendation

On the assisted development view, PLODv2 pairing adds nine strict pairs absent from Schwartz-Hearst with one additional false positive; their exact union improves F1 from 0.661 to 0.756. Freeze and test this transparent existing composition, without further tuning, against Schwartz-Hearst.

Freeze Schwartz–Hearst as the baseline and the existing transparent exact union of Schwartz–Hearst plus PLODv2 pairing as the sole challenger.
Do not advance Jev in this small fresh check.

The complete occurrence-level recovery and prediction tables are listed in the JSON report's `artifacts` section.
