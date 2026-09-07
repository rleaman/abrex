# T041 Make corpus processing resumable and bounded in memory

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: E.

## Outcome

Process large literature collections without loading the whole corpus into memory or losing completed work on interruption.

## Dependencies and reading

[T022](T022-real-baseline-smoke-benchmarks.md), [T025](T025-literature-acquisition-manifests.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/experiments/runner.py; src/abrex/resolvers/execution.py; src/abrex/corpora/serialization.py; src/abrex/infrastructure/ab3p.py.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Profile a representative bounded pilot first. Introduce sharded application orchestration and streaming readers where measured scale requires them, preserving existing small-run APIs.
2. Write task-owned temporary artifacts atomically, publish a completion manifest last, and make interrupted/partial shards distinguishable from complete output.
3. Add deterministic shard membership, per-document provenance, bounded concurrency, retries, failure quarantine and checkpoint reuse protected by resolver/source/config identities.
4. Aggregate shard counts and artifacts without re-counting duplicated articles or retry outputs. Record throughput, peak memory, bytes/document and estimated full-run costs.
5. Expose explicit document/time/disk/concurrency limits and dry-run estimates; keep core scientific code independent of infrastructure.

## Acceptance criteria

- Kill/resume tests reproduce an uninterrupted run's accepted document/prediction set and artifact identities where specified.
- Corrupt or changed-input shards are recomputed; incomplete runs cannot be reported as complete benchmarks.
- A larger-than-memory-shaped test uses bounded buffering, with published pilot measurements rather than unverified scale claims.

## Verification

Interrupted publication, stale/corrupt checkpoint and idempotence integration tests, bounded-memory pilot, full quality gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No distributed framework or performance rewrite without measurements. This hardening may proceed after milestone A; large production runs remain gated by T040 and budget.

## Inputs and possible blockers

Small representative local corpus and disk/time limits; no cloud account is required for the first implementation.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T041-resumable-bounded-corpus-processing.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

