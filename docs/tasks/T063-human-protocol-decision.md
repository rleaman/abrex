# T063 Choose the fresh-check scope and success criteria

Owner: **USER — scientific lead; not a Luna implementation assignment**  
Status: **Complete - approved by the scientific lead on October 4, 2026.**
Dependencies: T062 readout and concrete protocol proposal.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Your steps

T062 recommends the existing `transparent_hybrid` exact union of
Schwartz–Hearst and PLODv2 pairing as the sole challenger against the fixed
Schwartz–Hearst baseline. The complete sample, policy, tolerances, limits, and
reviewer plan are prefilled in
[`T063-decision-prefill.json`](../artifacts/T063-decision-prefill.json).

The scientific lead replied **Approve T063** on October 4, 2026. The complete
prefilled recommendation is approved and frozen without revision. T065 may
therefore prepare the prediction-blind sample under that exact contract.

If the prefill is acceptable, reply exactly **Approve T063**. Otherwise list
only the fields to change. The detailed historical choice list below remains
the authority for any requested revision.

1. Choose whether to compare a promising existing configuration against the fixed baseline or perform a baseline-only quality check. A new method requiring development returns to a separate Luna task before this protocol freezes.
2. Confirm or revise the proposed annotation budget, source mix, article/passage sampling rules and acquisition limits. The suggested 24 passages are a manageable exploratory check, not a statistical guarantee.
3. Confirm the strict target and treatment of shared evidence, neighboring relations, source errors and uncertain/unscoreable cases. Select the proposed numerical quality/error/cost tolerances or provide alternatives before results are seen.
4. Identify who will annotate. You may perform the first pass yourself while blind to predictions. If a second independent reviewer is available, identify the subset/workflow; otherwise retain the honest label “single-reviewer, prediction-blind.” Luna cannot serve as an independent human reviewer.
5. Confirm model access/budget only if a real model run needs a route not already authorized. No need to reconfirm existing permissions.
6. Return the decision sheet. If you prefer to stop with a strong single baseline, record that decision rather than manufacturing an ensemble requirement.

## Acceptance, deliverables and stopping point

User deliverable: selected configuration, numeric tolerances, sample/effort budget and reviewer plan. Luna may explain tradeoffs and revise the document, but cannot silently select scientific policy on your behalf. Acquisition and dependent confirmatory work wait for these decisions; blind-interface fixture work can proceed independently.

