# T037 Build leakage-safe candidate training datasets

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Turn reviewed gold and controlled silver evidence into reproducible feature/label datasets for the existing scorer scaffold.

## Dependencies and reading

[T030](T030-annotation-pilot-and-adjudication.md), [T035](T035-weak-evidence-ledger-and-silver-labels.md), [T036](T036-contextual-pattern-induction.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/scorers/splits.py; src/abrex/scorers/base.py; src/abrex/features/pipeline.py; src/abrex/candidates/serialization.py; docs/scorers.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Implement registry-selected label construction using the frozen pair contract, preserving gold/silver origin, weight, ambiguity and abstention. Do not treat all unmatched candidates in partially annotated sources as negative.
2. Materialize candidate/feature/label rows with stable candidate identities, source fingerprints, feature schema, generator versions and exclusion manifest.
3. Partition by T029 article groups and record gold/silver composition, positive/negative balance and candidate recall. Keep PLOD's known/unknown pretraining overlap visible.
4. Produce a dataset card with inclusion rules, missing annotations, teacher correlations and label-noise audit; export a small reproducible training smoke dataset.

## Acceptance criteria

- No final evaluation article, counterpart abstract/full text or derived held-out evidence enters training/dev rows.
- Feature extraction has no gold access; only the separate label builder consumes annotations.
- Repeated builds yield equivalent rows/fingerprints, and row-level provenance reconstructs how each label was assigned.

## Verification

Partial-gold negative-label regressions, row joins/schema changes, overlap rejection, gold/silver separation and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

T030 provisional labels may support exploratory training, but cannot certify final accuracy. If reviewed gold is unavailable, clearly scope completion to the tooling and label the experiment provisional.

## Inputs and possible blockers

Explicit source/split/label policies and sufficient reviewed training/development annotations; never repurpose locked evaluation annotations as training data.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T037-training-dataset-materialization.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

