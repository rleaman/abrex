# T062 Measure recoverable misses and draft a fresh-sample protocol

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T061 adjudications; T057 guidelines; T060 run artifacts.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Incorporate adjudications in a new immutable development version. Any guideline change must be documented and all compared outputs reinterpreted consistently; do not change the original evidence.
2. Produce per-method coverage and a per-relation recovery table: absent candidate, detected spans without correct pairing, wrong boundary, correct exact pair, representation-limited evidence, out-of-scope/unsupported and unresolved. Separate observable facts from suspected failure mechanisms.
3. Report unique correct additions, added errors and review/processing cost versus S&H and versus the strongest available single baseline. Compute a gold-assisted union using one-to-one occurrence matching; explicitly call it an upper bound within available candidates. Compare simple union only as an existing baseline, not proof of denoising.
4. Report raw counts by article, relation kind and evidence structure. Development matching summaries are descriptive assisted results, not population accuracy estimates. Do not use T052 as an unbiased recall denominator or bootstrap individual pairs as independent articles.
5. Recommend at most one existing candidate configuration for fresh comparison with a fixed baseline. If evidence favors new structural rules, a selector or model revision, write a separately bounded follow-up proposal; do not implement it inside this task or tune it on fresh evaluation text.
6. Draft a concrete protocol: proposed 24 fresh passages from at least 12 new article groups, balanced 12 abstract-arm/12 PMC text passages, at most two per group, sampled without detector/token enrichment. Treat these as adjustable budget proposals, not approved population proportions. Record frame, seed, source eligibility, acquisition/time/byte limits, passage segmentation and target source mix.
7. Specify primary exact-pair counts/precision/recall, article-group uncertainty where meaningful, coverage failures, representation exclusions, strict out-of-scope predictions, zero-definition passages and secondary diagnostics. Propose concrete numerical gain/error/cost tolerances with rationale for T063; do not leave all thresholds as unspecified placeholders.
8. Specify that the fresh check is a small blinded evaluation, not a powered benchmark or proof of general superiority. Model/prompt/config and primary policy freeze precede acquisition; all discovery articles and linked copies are excluded.

## Acceptance, deliverables and stopping point

Deliver concise readout, complete recovery table, runnable report inputs and a concrete protocol decision sheet. Test oracle matching, duplicate occurrences, unscoreable/unresolved units and denominators with meaningful fixtures. Make unavailable-method limits prominent. No iterative training or fresh-source acquisition yet.

