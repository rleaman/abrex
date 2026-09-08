# T043 Link abbreviation mentions to local definitions

Status: Complete for explicit local mention-linking engineering and tests;
production policy remains downstream-data dependent. Assigned implementer:
GPT-5.6 Luna. Milestone: F.

## Outcome

Make detected definitions usable throughout an article while keeping mention resolution distinct from definition extraction.

## Dependencies and reading

[T026](T026-pubmed-bioc-source-parsing.md), [T032](T032-transparent-hybrid-resolver.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/literature/mapping.py; src/abrex/literature/service.py; src/abrex/literature/models.py; docs/literature-integration.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Define a typed downstream mention-link result with mention span, chosen definition reference, scope, evidence and ambiguity/abstention status.
2. Implement named local policies for nearest preceding definition, section/article scope, redefinition and conflicting senses. Include explicit word-boundary/case/plural handling variants.
3. Retain original text and source mappings; do not rewrite article text or invent a local definition for an undefined SF.
4. Compose the selected resolver and mention-linker through application services and expose a small library/CLI example for an entity pipeline.

## Acceptance criteria

- Repeated mentions link deterministically to the appropriate definition under each selected policy.
- Redefinitions, conflicting sections, before-definition mentions, multi-token forms and undefined SFs have explicit outputs and tests.
- Definition-detection scores and mention-linking scores are separate; downstream clients can inspect and reject uncertain links.

## Verification

Mention-scope/redefinition golden cases, source-coordinate round trip, resolver injection contract and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No global acronym sense disambiguation, automatic entity normalization or assumptions about the user's cell-phenotype pipeline.

## Inputs and possible blockers

Local article examples. Production policy should be selected on actual downstream development data.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T043-document-local-mention-propagation.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
