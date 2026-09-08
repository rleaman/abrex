# T030 Create an auditable contemporary annotation pilot

Status: Complete for the auditable tooling and bounded local pilot; independent
review and scientific gold certification remain pending. Assigned implementer:
GPT-5.6 Luna. Milestone: B.

## Outcome

Produce usable contemporary evaluation evidence while minimizing the scientist's routine annotation work.

## Dependencies and reading

[T029](T029-sampling-and-leakage-controls.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: docs/scientific-contracts.md; src/abrex/corpora/base.py; src/abrex/corpora/validation.py; docs/project-completion-plan.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Write operational guidelines with positive/negative examples for SF/LF boundaries, relation identity, repeated/nested/overlapping definitions, tables, captions, titles, partial evidence and ambiguity.
2. Create an annotation export/import and validation workflow for the T029 pilot, preserving source text, spans, relation IDs, annotator/tool identity, guideline version, independent passes and adjudication.
3. Use automatic suggestions only in clearly labeled assisted workflows; keep independent evaluation annotations blind to resolver identity where feasible. Multi-agent agreement is not automatically independent human gold.
4. Prepare a compact review packet of ambiguous cases and a diverse audit subset. If independent expert review is unavailable, label the result provisional/silver and restrict claims accordingly.
5. Keep training/development annotation packets separate from final evaluation packets under T029. Freeze reviewed evaluation artifacts and retain unresolved annotations with an explicit scoreability policy. Record counts, time and disagreement by phenomenon; the final packet cannot be used for T031 development choices or T037 training.

## Acceptance criteria

- The pilot imports into canonical artifacts without offset or identity loss; annotation revisions and adjudication remain traceable.
- Guidelines cover full-text structures and multi-relation cases; both empty-definition and difficult documents occur in the sample.
- A report distinguishes independent labels, assisted labels and unresolved cases. Research completion is not claimed on synthetic or unreviewed labels.

## Verification

Annotation round-trip, invalid-offset and adjudication-history tests, held-out access controls, pilot audit and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not use resolver predictions as their own gold or ask the user to label every routine case. A small meaningful independent review remains a scientific evidence requirement, not a programming blocker.

## Inputs and possible blockers

Reviewer/annotation budget is unresolved. Tooling can complete offline; gold certification and credible contemporary accuracy estimates require sufficient independent assessment.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T030-annotation-pilot-and-adjudication.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
