# Milestone B direct-extraction result

This is assisted development evidence. The frozen GPT-6 Luna prompt does not
advance unchanged to Milestone C.

## Execution

- Completed structured responses: 11 / 20.
- Runtime failures: 9 / 20 (45.0%), all
  `max_output_tokens` before output text.
- Accepted grounded predictions: 14.
- Invalid grounded proposals: 15 / 29 (51.7%);
  every rejection was serialized and none was repaired from gold.

## Exact evidence

On the 11 scorable documents only: TP
13, FP 1, and FN
13. Precision is 0.9286,
recall is 0.5000, and F1 is
0.6500. This is not a full-run score.

The availability-adjusted descriptive view has precision
0.9286, recall 0.1940, and
F1 0.3210. It does not relabel failed documents as
legitimate empty predictions. Only 1 of
14 candidate-omitted gold relations was
recovered.

## Cost and decision

Exact successful-cache usage cost was
$0.0121366.
Including the two diagnostic attempts and the final batch, total spend is bounded
between $0.0327660 and
$0.0471974, below the authorized $0.05.

The predeclared request-failure, invalid-grounding, and candidate-omission
recovery gates failed. Decision: `do_not_advance_unchanged_prompt_to_milestone_c`. The one exact false
positive is a later non-defining occurrence of an already reviewed short/long
form, so no unresolved human adjudication remains.

## Versioned follow-up

This negative decision remains authoritative for the unchanged offset-producing
prompt. A later user-authorized quote-grounded refinement removed offset
generation from Luna's task and passed its development gate on iteration 2.
That distinct prompt is documented in
[`campaign-2026-10-luna-iteration-result.md`](campaign-2026-10-luna-iteration-result.md).
