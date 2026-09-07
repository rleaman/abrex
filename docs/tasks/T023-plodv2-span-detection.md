# T023 Integrate PLODv2 as a reproducible span detector

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Run the supplied Flair checkpoint on canonical text and persist all detected SF/LF spans independently of pairing.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md), [T019](T019-audit-and-repair-corpus-semantics.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: handoff/detect_abbreviations_PLODv2.py; docs/resolvers.md; src/abrex/domain/models.py; src/abrex/resolvers/base.py; docs/project-state-audit.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Verify the checkpoint surrey-nlp/flair-abbr-pubmed-filtered, its revision, labels, full artifact dependencies and runtime compatibility. Pin optional Flair/PyTorch dependencies; test Python 3.13 before selecting an isolated compatible worker environment.
2. Implement a narrow injectable span-detector protocol and typed config for device, batch size and explicit segmentation/window handling. Domain models must not import Flair, torch or BioC.
3. Persist raw and validated spans with model/tokenizer/embedding hashes, original scores, source offsets and any processing diagnostics. Validate slices against canonical text; retain unpaired spans for exact_span evaluation.
4. Support bounded long-text processing without silent truncation, with explicit window offsets and duplicate handling. Keep model acquisition separate from inference, and avoid import-time downloads or uncontained global device mutation.

## Acceptance criteria

- Real CPU inference produces canonical spans and a reproducibility manifest; unavailable CUDA or model files fail clearly.
- The model's span output can be scored before pairing, including cases with only one form detected.
- Changing model/dependent embedding content, segmentation or runtime-relevant config invalidates cached spans; Unicode/window boundaries are verified.

## Verification

Fake-detector unit/contract tests, raw label and offset fixtures, long-window boundary cases, marked real-checkpoint CPU smoke, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not copy the BioC-mutating helper into core code or interpret span scores as pair probabilities. Model-card metrics are span metrics, not evidence of ABREX pair accuracy.

## Inputs and possible blockers

Checkpoint download and disk capacity. The model card identifies CC-BY-SA-4.0; record notices and verify distribution requirements before packaging weights.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T023-plodv2-span-detection.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

