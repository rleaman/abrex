# T067 Run the frozen comparison and report the fresh-check result

Owner: **Luna — engineering and preparation**  
Status: **Complete — the frozen fresh check failed the adoption gate.**
Dependencies: T066 locked annotations; T065 frozen protocol and runnable methods.

Use `evidence/T066/review-packet-blind-v1.annotations.corrected-v2.json` and
its adjacent `.lock.json` file as the sole authoritative gold input. The
original user lock remains preserved under `evidence/T065`; do not silently
substitute it for the authorized corrected revision.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Verify annotation lock/hash, pre-run model/config identities and article isolation. Resolve technical input validation before running; never use gold labels in model requests, candidate generation or threshold selection.
2. Run only the selected candidate and fixed baseline under identical approved inputs/context. Preserve raw outputs, failures, truncation, latency, tokens/cost and complete manifests. If a required runtime is unavailable, report the check incomplete; do not substitute a different model or configuration.
3. Evaluate using the frozen policy and one-to-one occurrence matching. Report raw TP/FP/FN, precision/recall, coverage and empty-passage false positives. Keep unknown, unsupported, out-of-scope and representation-limited cases distinct; apply predeclared eligibility rules consistently.
4. Use article-group uncertainty only where justified by the small sample; show counts and paired per-article differences. Do not present source-arm balancing as population weighting or a small positive result as definitive superiority.
5. Compare against the predeclared gain/error/cost tolerances. Report pass/fail/inconclusive with actual evidence; a failed required run is not a no-gain scientific result.
6. Freeze the primary report before error-driven revision. Any post-reveal label correction receives a version, rationale, exposure record and separate sensitivity result; preserve the original scored result. Do not tune and reevaluate on the same sample as fresh confirmation.
7. Deliver a concise recommendation among strongest single baseline, supported existing combination/model, separately scoped structural development, or insufficient evidence. Link detailed errors for later review; no new frontend dashboard is required.

## Acceptance, deliverables and stopping point

Deliver runnable evaluation command, frozen predictions/results, coverage/cost table and decision readout. Test denominator handling, empty passages, duplicate matching and immutable input enforcement. Run focused tests and fast gate; run the full gate at this milestone and report any existing coverage shortfall without lowering thresholds. No production promotion, training campaign or corpus-scale processing.

## Current execution checkpoint

The corrected lock was verified and projected into separate local gold and
prediction-only datasets under `evidence/T067`. The checksummed Linux result
archive for bundle
`ab96b25c055f49832c3bfedc6c0e50cf87ddc59f8349b1decd38c7c1625c9966`
was imported on October 5, 2026. Both frozen methods completed all 32 inputs
with zero runtime failures.

The immutable [primary readout](../T067-fresh-evaluation-readout.md) records a
failed adoption gate: the exact union improved strict-pair F1 from 0.250 to
0.556 and added 14 unique true positives, but it also added 10 false positives
against the predeclared maximum of two. The improvement was concentrated in
the table/list arm and principally one article group; prose F1 declined from
0.500 to 0.480. No threshold or method was changed after gold was revealed.

See the [completion record](completed/T067-fresh-evaluation-readout.md) for
artifact identities, arm-level results, and verification. T068 is now the
scientific lead's next-direction decision; this result does not authorize a
post-hoc challenger or production promotion.

