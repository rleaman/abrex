# Milestone C protocol decision

Decision status: **awaiting user approval**

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

The source-only reviewer and disposable save/resume/lock flow are already
browser-tested. The actual frozen packet will be tested again before delivery.

## What approval authorizes

Approval authorizes the campaign owner to acquire and freeze the source-only
sample, build the sidecar carrying ordered passages and raw table XML, and
deliver the tested prediction-blind review packet. It does not authorize:

- any TypeSafe scientific-data request or spend;
- any confirmatory resolver prediction run, including Luna;
- unlocking annotations or exposing predictions to reviewers;
- additional Azure OpenAI requests before the annotation lock and a new bounded
  execution authorization.

After the sample and rules-only CLP dry run are complete, the owner will present
the exact TypeSafe and Luna request counts, passages, and hard cost caps for
separate authorization. Ab3P and PLODv2 execution will use the documented
portable Linux bundle because this Windows host has no installed WSL
distribution.

## Minimal response

To accept this recommendation, reply:

> Approve the Milestone C protocol as prepared.

If you want a scientific change, identify only the field to change: sample size,
method set, review burden, primary contrasts, or success thresholds. All
clerical freeze, acquisition, packet construction, and validation work remains
with the campaign owner.
