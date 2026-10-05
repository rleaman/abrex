# T065 Freeze the protocol and prepare the fresh annotation packet

Owner: **Luna — engineering and preparation**  
Status: **Complete - fresh packet delivered October 4, 2026 local time.**
Dependencies: T063 user decisions; T064 user-ready blind mode.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Freeze the user-selected protocol, guidelines, method configurations, prompt/model identities and tolerances before retrieving fresh evaluation material. Preserve a decision manifest; no unspecified numerical limits.
2. Reuse the T025/T029/T051 acquisition and sampling boundaries. Draw new eligible article groups excluding all T051/T052 discovery groups, T060 development inputs and known linked PMID/PMCID copies. If a compatible independent local source frame exists, use it with provenance.
3. Follow the approved source mix, frame and deterministic passage sampling without running detectors, inspecting model output or enriching on uppercase tokens. Do not replace articles/passages because they appear empty or difficult. Record every exclusion, failed fetch, shortage, denominator and replacement rule.
4. Preserve canonical text and permitted structure/context, hashes and source/license evidence. This is local research preparation; prior T052 sharing authorization is not blanket publication permission.
5. Build a prediction-free packet and an empty annotation state. Keep operational acquisition metadata separate from the annotation view. Identify out-of-bounds context and titles explicitly; do not make titles secretly annotatable.
6. Validate counts, group isolation, replay and blind payloads. Open the reviewer on the actual packet without annotating or highlighting likely answers. Provide the user a short launch/save/return guide and actual workload.
7. Record any incidental model/annotator exposure. Do not label exposed material untouched; apply the predeclared contamination procedure rather than quietly replacing cases.

## Acceptance, deliverables and stopping point

Deliver frozen protocol, sample/source manifests, canonical packet, empty state and working launcher. Tests cover deterministic sampling, linked-group exclusion, shortages and prediction-free serialization. Acquisition stops at approved limits; incomplete sample status is explicit. Do not run evaluated methods until T066 annotation is locked.

## Completion evidence

The approved T063 artifact is frozen at SHA-256
`08eba6fd0adae99c355a6a18e8c615a037171056cf135c8339f8f3092a732541`.
The seeded acquisition selected eight eligible groups after 37 draws with zero
fetch failures, 4,695,175 downloaded bytes, and no reached limit. The delivered
packet has the approved 12/12/8 source mix and four cases per group. See
[`evidence/T065/README.md`](../../evidence/T065/README.md), the source manifest,
and [`T065-browser-qa.json`](../artifacts/T065-browser-qa.json). Evaluated
methods remain unrun pending the T066 annotation lock.

