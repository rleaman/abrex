# T032 Implement an evidence-driven transparent hybrid

Status: Complete for the bounded historical development comparison and
engineering deliverables. No production promotion is claimed. Assigned
implementer: GPT-5.6 Luna. Milestone: C.

## Outcome

Provide a simple inspectable resolver combination and measure it against the strongest single baseline.

## Dependencies and reading

[T031](T031-comparative-benchmark-and-oracle-analysis.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/resolvers/registry.py; src/abrex/resolvers/execution.py; src/abrex/domain/models.py; docs/scientific-contracts.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Use T031 development findings to specify a small number of named strategies such as exact union and priority cascade. Record why each strategy targets an observed error pattern.
2. Implement typed child-resolver composition, exact-duplicate merge with all contributor provenance, explicit conflict handling and abstention. Keep raw child outputs available.
3. Include child configurations/versions/artifact identities and fusion policy in cache identity. Detect recursive/cyclic configurations and report child failures explicitly.
4. Evaluate matched development runs with and without the hybrid; save acceptance/rejection reasons for every proposed pair and document precision/runtime tradeoffs.

## Acceptance criteria

- Every accepted pair can be traced to its children and a named decision rule; duplicate merging does not erase source evidence.
- Conflict, shared-form and child-failure cases are deterministic and covered by tests.
- A reproducible comparison shows gain, no gain or regression honestly. Default promotion occurs only if predeclared precision/quality constraints are met.

## Verification

Composition contracts, duplicate/provenance and conflicting LF cases, cyclic config and cache-change regressions, development benchmark and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No learned ranker yet, no implicit averaging of incomparable confidence scores and no test-driven priority tuning. If the single baseline is better, retain it as the recommended resolver.

## Inputs and possible blockers

T031 development comparison. Production precision tolerance remains an explicit decision, not an invented number.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T032-transparent-hybrid-resolver.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
