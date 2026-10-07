# Luna quote-grounded extractor development result

The quote-grounded extractor passed every predeclared T062 development gate on
iteration 2 and is frozen for evaluation on new prediction-blind annotations.
No further T062 tuning or Azure request is warranted before that evaluation.

| Iteration | TP | FP | FN | Precision | Recall | F1 | Omission recovery | Grounding failure | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 40 | 15 | 27 | 0.7273 | 0.5970 | 0.6557 | 3/14 | 6.8% | $0.0048709 |
| 2 | 58 | 6 | 9 | 0.9062 | 0.8657 | 0.8855 | 9/14 | 3.0% | $0.0055919 |

Both iterations completed structured output for all 20 documents. Iteration 2
used low reasoning, an 8,192-token output allowance, exact evidence quotations,
and deterministic Unicode offset recovery. It produced 58 TP, six FP, and nine
FN, for precision 0.9063, recall 0.8657, and F1 0.8855. It recovered nine of the
14 relations omitted by the candidate generators. Two of 66 proposals failed
literal evidence grounding; both were diagnostic representation-limited
relations outside strict target scoring.

Five of the remaining six false positives are reviewed out-of-scope diagnostic
naming/code relations. Three of the nine false negatives are overlapping
alternative gold boundaries for occurrences where another boundary was matched.
These remain visible; they were not repaired or removed from the strict totals.

Two of the authorized ten iterations were used. Cumulative actual provider cost
was $0.0104628; each iteration
remained independently below its $0.10 cap. Iteration 2 is selected because it
is the first version to pass every frozen development gate. Continuing to tune
against exposed T062 gold would add overfitting without answering generalization.
