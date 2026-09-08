# T029 Define contemporary sampling and article-level data separation

Status: Complete. Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Create reproducible development, evaluation and pilot unlabeled-pool manifests that prevent literature and teacher leakage. [T047](T047-large-scale-corpus-selection.md) separately selects the large-scale discovery/training and tagged-release document sets using these exclusions.

## Dependencies and reading

[T019](T019-audit-and-repair-corpus-semantics.md), [T026](T026-pubmed-bioc-source-parsing.md), [T027](T027-jats-tables-captions-and-definition-lists.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/scorers/splits.py; docs/scientific-contracts.md; docs/project-completion-plan.md; handoff/idea.txt.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Implement configurable sample selection with a frozen random/stratified-random component independent of resolver detections and a separately labeled challenge component for tables, captions, ambiguity and rare forms.
2. Use T028 aggregate frequencies for SF/pair priorities. Build article-level occurrence links from the sampled literature before any coverage-based article selection; the supplied frequency JSON does not establish article locations.
3. Group PMID/PMCID versions, abstract/full-text counterparts and duplicate/near-duplicate content before assigning partitions. Preserve official historical splits; record model training-data overlap when ascertainable and unknown overlap when not.
4. Write explicit manifests and a proposal for target years, abstract/full-text mix, strata, sample sizes and split rationale. Reserve final evaluation articles from lexicon induction, training, threshold tuning and iteration.
5. Store sampling probabilities where meaningful; keep deliberately selected challenge scores separate from population-weighted estimates.

## Acceptance criteria

- A fixed seed/frame/config reproduces the same article groups and assignments with no overlap.
- Smoke fixtures catch the same article under different identifiers and prevent lookup of held-out evidence through derived lexicons.
- A sampling report shows frame coverage, unavailable texts and selection limitations; no Ab3P-only benchmark is labeled unbiased.

## Verification

Determinism, group leakage and duplicate-version tests, official-split preservation, sampling accounting and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Sample sizes and production mix are proposals, not established scientific requirements. Generate mechanisms and a concrete manifest for review; do not silently invent final train/dev/test assignments for scientific claims.

## Inputs and possible blockers

Real T026/T027 articles. T028 is optional. Final benchmark release requires the recorded sampling and evaluation protocol.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T029-sampling-and-leakage-controls.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
