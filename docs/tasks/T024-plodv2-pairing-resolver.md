# T024 Add explicit PLODv2 pairing strategies and resolver integration

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Convert detected SF/LF spans into inspectable local-definition predictions while preserving raw span diagnostics.

## Dependencies and reading

[T023](T023-plodv2-span-detection.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: handoff/detect_abbreviations_PLODv2.py; docs/notes-for-later.md; src/abrex/resolvers/registry.py; src/abrex/candidates/base.py; docs/scientific-contracts.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Extract span-merging, pair eligibility, pair cost and selection into separate pure components selected by typed registry configuration.
2. Create a named helper-compatible strategy for comparison and a corrected candidate-position-anchored strategy. Pattern evidence must refer to the actual slice between these spans; a match elsewhere in the document is not evidence.
3. Specify reverse order, distance limits, ties, one-to-one versus shared-form relations, abstention and duplicate rules. If a greedy strategy is retained, name it and test its deterministic limitations rather than presenting it as optimal assignment.
4. Register a plodv2 resolver that composes T023 detection and pairing, preserves model/pairer identities and rejection reasons, and emits the existing canonical prediction format.

## Acceptance criteria

- Repeated surface strings cannot create a spurious pattern match at another location.
- Permutation/tie cases, multiple SFs sharing an LF, unmatched spans and false parentheticals have explicit, reproducible outcomes.
- Standalone span scores and final pair scores remain separately reportable; model/pairer changes invalidate appropriate caches.

## Verification

Regressions for whole-passage regex matching, adjacency merging and greedy tie cases; Unicode/reverse/nested fixtures; resolver contract and real-model smoke; fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

The attached helper is reference code, not the scientific specification. Do not universally exclude titles or trim punctuation based on anecdotes; make candidate transformations separate named variants.

## Inputs and possible blockers

T023 raw span artifacts allow most work offline without repeated model inference.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T024-plodv2-pairing-resolver.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

