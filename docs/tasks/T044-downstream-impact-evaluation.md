# T044 Measure impact on the biomedical NLP pipeline

Status: Complete for the downstream adapter contract and regression fixtures;
real impact validation remains incomplete because no user pipeline or frozen
downstream dataset is available. Assigned implementer: GPT-5.6 Luna.
Milestone: F.

## Outcome

Determine whether the selected abbreviation layer improves a real downstream task enough to justify its cost.

## Dependencies and reading

[T040](T040-research-validation-and-ablation-campaign.md), [T043](T043-document-local-mention-propagation.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: docs/literature-integration.md; T040 research report; T043 mention-linking documentation; docs/project-completion-plan.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Obtain a concrete downstream adapter contract and frozen input/output evaluation snapshot from the user's pipeline. Preserve its entity extraction/normalization settings across comparisons.
2. Compare no abbreviation propagation where meaningful, existing baseline handling and the frozen release candidate on the same articles.
3. Measure entity recovery/linking precision and recall, introduced false expansions, ambiguity, latency and resource use; group statistical comparisons by article.
4. Produce a small review packet connecting changed downstream outcomes to the exact abbreviation decision and source text.
5. Write a recommendation and deployment configuration only when the observed quality/cost tradeoff meets the recorded target.

## Acceptance criteria

- A reproducible real downstream comparison exists, with unchanged non-abbreviation components and traceable errors.
- Definition extraction, mention linking and downstream entity results are reported separately.
- If no downstream dataset or integration is available, deliver the adapter contract and fixtures but explicitly leave impact validation incomplete.

## Verification

Adapter contract, frozen-input comparison repeatability, downstream regression cases and full quality gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Synthetic downstream examples prove integration only. Do not claim biological/entity improvements from abbreviation F1 alone or from the vision document's suggested cell-phenotype use case.

## Inputs and possible blockers

Actual pipeline interface, permitted evaluation data and the user's relevant success metric are not in this repository.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T044-downstream-impact-evaluation.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
