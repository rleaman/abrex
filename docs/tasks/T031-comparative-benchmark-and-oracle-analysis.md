# T031 Measure resolver complementarity and uncertainty

Status: Complete for the historical comparison and engineering deliverables.
The contemporary extension remains pending because T030's labels are
provisional and not approved for development claims. Assigned implementer:
GPT-5.6 Luna.

## Outcome

Determine where each real resolver succeeds and whether combining them has measurable headroom.

## Dependencies and reading

[T022](T022-real-baseline-smoke-benchmarks.md), [T024](T024-plodv2-pairing-resolver.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/evaluation/; src/abrex/reporting/; src/abrex/experiments/runner.py; docs/evaluation.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Compose a typed experiment matrix over available audited historical datasets and, once T030 is ready, the contemporary development/pilot data. Select exact-pair or exact-span metrics according to annotation contract.
2. Compare baseline predictions and PLOD spans/pairs on identical document universes. Report coverage/failures, per-corpus metrics, standalone span versus pairing loss, intersections, union errors and resolver-unique correct pairs.
3. Implement a clearly labeled gold-assisted oracle analysis using the configured one-to-one matcher; state its denominator and duplicate policy. Report attainable union recall and constraints, not an inflated deployable score.
4. Add article-group paired bootstrap confidence intervals as a downstream analysis plugin and explicit construction/section strata. Freeze seed and procedure; keep challenge-set estimates separate.
5. Generate a concise evidence report and rank candidate changes by unique recovered errors, precision losses and runtime. Historical analysis must not wait for contemporary annotation.

## Acceptance criteria

- Hand-computed fixtures validate unique TP/FP, union and oracle counts under duplicates and repeated definitions.
- Metrics from incompatible tasks are never pooled into a single F1; execution failures and unscoreable gold remain visible.
- Reports identify whether sufficient complementary signal exists; uncertainty and dataset limitations accompany any claimed gain.

## Verification

Small analytically known comparisons, bootstrap determinism and grouping, real three-resolver matrix, reporting tests and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Use development/pilot data to guide model choices. Locked final test data is reserved for T040; any already-inspected historical test results are labeled exploratory.

Include the [T048 BioADI resolver](T048-bioadi-runtime-and-resolver.md) as an additional comparison if its runtime assessment establishes viability. Keep a clear pending/not-viable status otherwise; do not block the three-resolver baseline on optional software. Check its training-corpus overlap.

## Inputs and possible blockers

T022 and T024 are required. Contemporary extension awaits T030; lack of that extension must be visible in the report.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T031-comparative-benchmark-and-oracle-analysis.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

