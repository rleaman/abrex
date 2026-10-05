# T068 Choose the next project milestone from the evidence

Owner: **USER — scientific lead; not a Luna implementation assignment**  
Status: **Complete — scientific direction recorded October 5, 2026.**
Dependencies: T067 final readout, or an explicit incomplete-experiment report.

## Decision basis

The scientific lead reviewed the frozen T067 result together with the earlier
historical and assisted-development evidence. This record preserves that
decision without rewriting the earlier plans or results as though the outcome
had been known in advance.

## Recorded decision

No evaluated resolver currently demonstrates the accuracy expected of a modern
abbreviation-extraction system on robust contemporary evidence. None is
promoted as a scientifically validated solution, and the tested fixed unions
are not adopted.

The evidence supports these narrower conclusions:

- Ab3P has the strongest historical single-method result, but it has no fresh
  contemporary evaluation and its historical slice is not representative.
- Schwartz–Hearst is deterministic and conservative, but its fresh recall is
  poor and it does not handle structured material adequately.
- PLODv2 has the strongest standalone numerical result in the small fresh
  check and supplies much of the table/list recall, but it produces too many
  false positives and its gain is concentrated.
- Jev is inexpensive and operational, but its development evidence does not
  demonstrate an improvement and it was not advanced to the fresh check.
- The CLP-derived table evidence is promising development material, but ABREX
  has not independently measured the parser's precision, recall or F1.
- No method has an adequately powered, independently confirmed contemporary
  performance estimate.

The fresh result answers the tested combination question negatively: the
unconditional Schwartz–Hearst/PLODv2 exact union recovers additional true
pairs but imports too many false positives to be acceptable. This does not
establish that every possible selective, learned or structure-aware
combination must fail; it establishes that the tested fixed aggregation is not
the solution.

Ab3P remains the operational incumbent until stronger evidence exists. This
is a pragmatic continuity decision based on its historical evidence and
usability, not a claim of contemporary superiority. Schwartz–Hearst, PLODv2
and the other implemented methods remain research comparators rather than
promoted production systems.

## Next direction

1. Perform cross-method error analysis.
2. Design new methods, including an LLM-based approach.

The frozen T067 result remains unchanged; using its errors for design makes it
development evidence for any future method.

