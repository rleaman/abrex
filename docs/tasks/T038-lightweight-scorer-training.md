# T038 Train and evaluate a lightweight candidate scorer

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Replace the empty learned-scorer scaffold with a reproducible inexpensive baseline that can be compared to transparent fusion.

## Dependencies and reading

[T037](T037-training-dataset-materialization.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/scorers/; src/abrex/resolvers/adapters/learned.py; docs/scorers.md; docs/features.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Implement a CPU-oriented logistic-regression scorer as an explicitly named first research baseline, with validated hyperparameters and a compatible optional dependency. Reuse existing Scorer, persistence, calibration and selection contracts.
2. Add a thin training application/CLI consuming T037 artifacts and explicit split manifests. Record seed, objective, class/sample weighting, solver settings and training environment.
3. Choose thresholds only on development data under the recorded precision constraint; report calibration if used rather than assuming model probabilities are calibrated.
4. Run gold-only and gold-plus-silver comparisons against strongest single and transparent hybrid baselines. Save model hashes, schema identities and reproducible predictions.

## Acceptance criteria

- A train/save/load/predict round trip produces equivalent scores and rejects incompatible feature schemas or changed model artifacts.
- Training does not touch final holdout data and no threshold is silently defaulted for scientific runs.
- Development report includes candidate recall ceiling, precision/recall tradeoffs, runtime and no-gain outcomes; model deployment is not automatic.

## Verification

Scorer contract and persistence tamper checks, tiny separable/nonseparable datasets, deterministic training tolerance, model-cache regressions, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

This task specification selects logistic regression for a baseline experiment, not a claim it is the best family. Neural retraining or broad model searches require a separately justified task.

## Inputs and possible blockers

T037 training/dev artifacts. Use a permitted CPU budget; real benefit requires enough labels, not merely a fitted model.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T038-lightweight-scorer-training.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

