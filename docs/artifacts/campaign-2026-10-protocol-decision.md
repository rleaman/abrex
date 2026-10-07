# Milestone C protocol decision

Decision status: **approved and frozen on October 6, 2026**

The scientific lead approved the prepared protocol verbatim with:

> Approve the Milestone C protocol as prepared.

The machine-readable frozen record is
`evidence/campaign-2026-10/milestone-c/protocol-v1.json`. Its approval boundary
is unchanged from the prepared recommendation below.

## Recommended disposition

Approve the updated confirmatory protocol as prepared:

- 48 representative article groups with paired PMC prose and PubMed abstract
  passages, plus 24 disjoint structural-challenge groups;
- 72 groups and 120 passages total, with an estimated 8–12 hours of primary
  prediction-blind review;
- six confirmatory methods: native-offset Ab3P, Schwartz–Hearst, PLODv2 pairing,
  complete CLP V5.1, Jev candidate judging, and the frozen quote-grounded Luna
  extractor;
- strict exact-pair F1 on the representative component as the primary endpoint;
- two primary contrasts: complete CLP V5.1 versus Schwartz–Hearst, and
  quote-grounded Luna versus Jev candidate judging;
- superiority only when the absolute F1 gain is at least 0.05 and the paired
  article-group-bootstrap result passes Holm control across both contrasts;
- the structural challenge reported separately and never pooled into the
  representative estimate.

## Evidence behind the recommendation

The new draw excludes 238 PMIDs, 83 PMCIDs, known CLP overlap, and every linked
development identity. T067 and T062 are already exposed and remain development
evidence.

The original Luna prompt remains a recorded negative result. The separately
versioned quote-grounded extractor completed all 20 T062 requests and passed
every frozen gate on iteration 2: 58 TP, six FP, nine FN, precision 0.9063,
recall 0.8657, F1 0.8855, nine of 14 candidate omissions recovered, and two of
66 returned proposals rejected during deterministic grounding. The two-iteration
refinement cost $0.0104628. It is now frozen; no further T062 tuning is planned.

The source-only reviewer and disposable save/resume/lock flow are browser-tested.
The actual 120-passage frozen packet has also passed its separate Edge exercise.

## What approval authorizes

Approval authorizes the campaign owner to acquire and freeze the source-only
sample, build the sidecar carrying ordered passages and raw table XML, and
deliver the tested prediction-blind review packet. It does not authorize:

- any TypeSafe scientific-data request or spend;
- any confirmatory resolver prediction run, including Luna;
- unlocking annotations or exposing predictions to reviewers;
- additional Azure OpenAI requests before the annotation lock and a new bounded
  execution authorization.

The sample and rules-only CLP dry run are now complete. The separately gated
execution plan is 65 TypeSafe requests (64 Jev candidate-judge batches across
42 candidate-bearing passages plus one unresolved CLP ABBR-section judgment),
no retries, at most 724,000 input tokens and $0.05. The Luna plan is one frozen
quote-grounded request for each of 120 passages, no retries, at most 201,000
estimated input tokens, 8,192 output tokens per request, and $0.10. These are
prepared limits, not execution authorization. Machine evidence is
`evidence/campaign-2026-10/milestone-c/request-plan-v1.json`.

Ab3P and PLODv2 execution will use the documented portable Linux bundle because
this Windows host has no installed WSL distribution.

## Recorded response

The recommended response was received without revision on October 6, 2026.
Any later scientific change requires a new versioned protocol rather than an
in-place edit to the frozen record.
