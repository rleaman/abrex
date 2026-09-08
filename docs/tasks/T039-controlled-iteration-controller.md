# T039 Implement bounded evidence and model iteration

Status: Complete for bounded controller and two-iteration smoke mechanics;
research improvement remains unvalidated. Assigned implementer: GPT-5.6 Luna.
Milestone: D.

## Outcome

Run the original idea's dictionary–pattern–model feedback loop with explicit lineage, stop rules and rollback.

## Dependencies and reading

[T036](T036-contextual-pattern-induction.md), [T038](T038-lightweight-scorer-training.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: handoff/idea.txt; src/abrex/experiments/runner.py; src/abrex/scorers/artifacts.py; docs/project-completion-plan.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Create a typed iteration application that consumes immutable input snapshots and writes numbered evidence, dictionary, pattern, label and model artifacts. Reuse existing component registries.
2. Specify which previous-iteration artifacts may label which new documents. Prevent a new pair from serving as its own independent support in the same iteration.
3. Implement required iteration/document/time/storage limits, configurable development precision/coverage guards, minimum independent support and stop-on-no-gain rules.
4. Checkpoint completed stages; resume idempotently and roll back to the best development-selected snapshot. Retain rejected promotions and all parent identities.
5. Run a tiny two-iteration smoke exercising new evidence, a rejected noisy promotion and a stopped loop.

## Acceptance criteria

- A DAG of manifests traces each accepted pair/rule/model to its source iteration and evidence.
- Retries do not duplicate observations; changed resources invalidate dependent stages; interrupted execution resumes consistently.
- The controller stops at configured limits or guard failures and never reads locked final labels to decide continuation.

## Verification

Two-iteration deterministic fixture, self-support/cycle rejection, interruption/resume and guard-trigger tests, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not enable unbounded self-training or schedule unattended work implicitly. Passing this task demonstrates a controlled mechanism, not that iteration improves accuracy.

## Inputs and possible blockers

T036/T038 runnable artifacts and explicitly set small pilot limits.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T039-controlled-iteration-controller.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
