# T033 Generate candidates for difficult prose and full-text structures

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Increase candidate recall on observed failures, particularly abbreviation tables and figure captions, without prematurely accepting candidates.

## Dependencies and reading

[T027](T027-jats-tables-captions-and-definition-lists.md), [T031](T031-comparative-benchmark-and-oracle-analysis.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/candidates/; docs/candidates.md; docs/notes-for-later.md; handoff/idea.txt.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Add separate registry-backed generators for reverse-order/bracketed definitions, nesting-aware prose patterns and table/definition-list relationships identified in T031.
2. Use T027 structural metadata to enumerate plausible same-row/header/list relations while preserving cell paths and canonical spans. Captions are text sources; image-only regions remain explicitly uncovered.
3. Preserve raw candidate origins and diagnostics for limits, pruning and duplicates. Keep existing parenthetical behavior/version as a baseline.
4. Measure gold candidate coverage and candidate counts per document/structure, including missed-gold reason summaries. Add bounded complexity controls for long tables and dense prose.

## Acceptance criteria

- Regression examples include reverse order, Greek/multi-token forms, nested parentheses, shared-LF lists and table rows with multiple plausible expansions.
- Candidate generation emits possibilities rather than fabricated gold or forced decisions; provenance survives serialization.
- Development candidate recall and expansion in candidate volume are measured with the same gold/denominator across variants.

## Verification

Generator contract, structural-source mapping, bounded-complexity and deterministic-order tests; development coverage report; fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not silently relax evaluation boundaries or fold every anecdotal PLOD correction into the existing baseline. Only implement bounded variants motivated by data.

## Inputs and possible blockers

T027 structured article metadata and T031 error examples. Annotated structural development cases from T030 improve scientific validation.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T033-structural-candidate-generators.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

