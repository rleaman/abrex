# T035 Represent noisy evidence and derive versioned silver labels

Status: Complete for transparent evidence-ledger engineering and fixture truth
tables; silver-label accuracy remains scientifically unvalidated. Assigned
implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Combine heterogeneous evidence without mistaking correlated teacher agreement for independent truth.

## Dependencies and reading

[T032](T032-transparent-hybrid-resolver.md), [T034](T034-lexical-candidates-and-evidence-features.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/candidates/base.py; src/abrex/domain/models.py; src/abrex/scorers/base.py; handoff/idea.txt.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Define immutable evidence records keyed to document/content/span identity with source family, detector/rule/resource versions, local context and iteration lineage. Keep an append-only or content-addressed artifact history.
2. Implement configurable deterministic labeling functions for positive, negative and abstain evidence, plus a transparent conflict/aggregation policy. Record all contributing and vetoed evidence.
3. Distinguish gold, reviewed silver and automatically inferred silver; preserve confidence/weight semantics and reasons. Unlabeled text is not automatically negative.
4. Audit coverage, contradictions and source-family correlations. Use only development-reviewed examples to choose aggregation parameters; protect the T029 final holdout.

## Acceptance criteria

- Every silver label traces back to exact source text, evidence and aggregation config; contradictory cases can abstain.
- Reprocessing the same inputs does not create additional independent votes or increment occurrence counts.
- Gold annotations remain immutable and separate from generated labels; source-family ablations can be reproduced.

## Verification

Conflict/abstain truth tables, lineage/correlation grouping, idempotent evidence import and leakage fixtures, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not introduce an opaque probabilistic label model before the transparent baseline has evidence of need. Do not claim silver-label accuracy from teacher agreement alone.

## Inputs and possible blockers

Real multi-source development evidence and a small reviewed set for noise estimation.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T035-weak-evidence-ledger-and-silver-labels.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
