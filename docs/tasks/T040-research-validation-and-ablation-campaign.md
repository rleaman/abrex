# T040 Test the denoising hypothesis and select the release candidate

Status: Complete for the reproducible bounded campaign audit; production
improvement remains unsupported pending independent contemporary evidence.
Assigned implementer: GPT-5.6 Luna. Milestone: E.

## Outcome

Determine whether the proposed learning loop improves real local abbreviation resolution and resource quality.

## Dependencies and reading

[T030](T030-annotation-pilot-and-adjudication.md), [T031](T031-comparative-benchmark-and-oracle-analysis.md), [T039](T039-controlled-iteration-controller.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: docs/project-completion-plan.md; docs/scientific-contracts.md; T031 comparison report; T037 dataset card; T039 iteration manifests.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Before final evaluation, save a protocol fixing corpus versions, splits, candidate systems, metrics, uncertainty method, precision tolerance, resource budget and stopping rules.
2. Run bounded development ablations: strongest single baseline, simple hybrid, structural candidates, lexical evidence, gold-only scorer, silver-assisted scorer and zero/one/multiple iterations. Measure dictionary quality and label noise as well as extraction metrics.
3. Select one release candidate using development evidence. Evaluate frozen final data once for confirmation; if it is used for redesign, record that loss of holdout status and obtain a fresh evaluation set.
4. Report exact pair/span distinctions, article-group confidence intervals, tables/captions, ambiguity, frequency and unseen-pair performance, teacher-overlap limits, runtime and failures.
5. Write a continue/stop decision with reproducible artifacts; negative results are valid outcomes.

## Acceptance criteria

- Every reported score is backed by manifests and predictions; no table mixes synthetic, provisional and independently reviewed gold.
- Claimed gains meet the predeclared evidence/precision criteria and disclose uncertainty; otherwise the claim is explicitly unsupported.
- The chosen resolver and retained dictionary/rule artifacts are frozen, with rollback to the strongest validated baseline.

## Verification

Run experiment/report reproducibility checks, holdout-access audit, campaign-specific comparisons and full quality/coverage gates. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No promise of near-perfect accuracy and no endless test-set tuning. If contemporary gold or statistical power is inadequate, conclude that production improvement is not yet established.

Include the [T048 BioADI resolver](T048-bioadi-runtime-and-resolver.md) as an additional comparison if its runtime assessment establishes viability. Keep a clear pending/not-viable status otherwise; do not block the three-resolver baseline on optional software. Check its training-corpus overlap.

## Inputs and possible blockers

Independent evaluation evidence, recorded scientific decision thresholds and sufficient approved compute. Missing evidence limits conclusions, not the honesty of the report.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T040-research-validation-and-ablation-campaign.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
