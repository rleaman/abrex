# T022 Run reproducible real-data baseline benchmarks

Status: Complete for the bounded real-data baseline smoke and reproducibility
scope; scientific generalization remains pending later milestones. Assigned
implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

One documented command sequence produces audited real-corpus predictions, evaluation and provenance for Schwartz–Hearst and real Ab3P.

## Dependencies and reading

[T019](T019-audit-and-repair-corpus-semantics.md), [T021](T021-ab3p-native-offset-adapter.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/experiments/runner.py; docs/examples/experiment-toy.yaml; configs/corpora/; docs/tasks/completed/T008-regression-golden-suite.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Check in small experiment configurations and an explicit smoke-selection manifest for an available T019 paired corpus. Record full dataset and subset identities; never select examples because a resolver succeeds on them.
2. Run both baselines through the existing experiment service; record TP/FP/FN, precision/recall/F1, scoreable/unscoreable counts, mapping failures, elapsed time and environment identities.
3. Repeat with cache reuse and from a second fresh environment/build path. Add a marked live integration smoke that never substitutes synthetic Ab3P output.
4. Document known Schwartz–Hearst deviations and Ab3P mapping limitations. Keep upstream reproduction scores distinct from ABREX exact-offset scores if evaluation contracts differ.

## Acceptance criteria

- Both real resolvers complete on the same audited corpus slice and produce valid prediction, evaluation and run manifests.
- Warm-cache output matches cold output; fresh setup follows documented commands without source edits.
- No resolver failure is counted as an empty successful prediction, and all eligible documents appear exactly once.

## Verification

Live end-to-end runs and cache replay, integration/regression suites, fast and full coverage gates. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No ensemble optimization or changes to gold to improve scores. A smoke result proves operability, not research superiority.

## Inputs and possible blockers

Real canonical corpus from T019 and verified Ab3P installation. Any missing asset is a named operational blocker.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T022-real-baseline-smoke-benchmarks.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
