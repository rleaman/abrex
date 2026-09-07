# T034 Use dictionaries and terminologies as local candidate evidence

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Test whether lexical resources add useful local evidence while preserving ambiguity and preventing circular confirmation.

## Dependencies and reading

[T028](T028-lexical-resource-ingestion.md), [T029](T029-sampling-and-leakage-controls.md), [T033](T033-structural-candidate-generators.md), [T046](T046-external-dictionary-acquisition.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/candidates/; src/abrex/features/; docs/features.md; handoff/idea.txt.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Add a registry-backed candidate generator that finds supplied SF/LF variants within configurable local windows or structural units; record exact occurrence spans and resource source IDs.
2. Add deterministic resource features such as observed count, source agreement, ambiguity and contextual support. Missing evidence is explicit; resource-derived signals remain separate from local structural evidence.
3. Optionally add a named acronym-from-term proposal rule for terminology terms; guessed SFs remain candidate evidence with their generating rule identity.
4. Enforce T029 exclusions and resource cutoffs when building/using evaluation resources. An Ab3P-derived dictionary plus Ab3P detection is one correlated source family, not two independent votes.
5. Run no-lexicon versus lexical development ablations and report novel candidates, precision effects and lookup cost.

## Acceptance criteria

- A dictionary pair cannot be emitted as a local definition if its required local text spans are absent.
- Homonymous SFs, normalization collisions and cross-document resource provenance remain distinguishable.
- A held-out article's mined pair cannot leak back into its own evaluation through a newly built dictionary.

## Verification

Local-window and structural matching cases, missing/ambiguous resource evidence, leakage and cache identity tests, ablation report and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No global undefined-acronym disambiguation or blind terminology authority. Similar-context retrieval, if later justified, needs its own task and must not fabricate a local LF span.

## Inputs and possible blockers

A real permitted T028 resource and T029 split/exclusion manifests; fixtures alone demonstrate mechanics, not lexical benefit.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T034-lexical-candidates-and-evidence-features.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

