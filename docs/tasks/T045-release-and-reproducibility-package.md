# T045 Package the resolver and research resources for reuse

Status: Complete for the local installable release candidate and
reproducibility package; T042 and T044 research inputs remain explicitly
pending/unvalidated. Assigned implementer: GPT-5.6 Luna. Milestone: F.

## Outcome

Deliver an installable, documented release candidate with reproducible results and clear supported operating modes.

## Dependencies and reading

[T040](T040-research-validation-and-ablation-campaign.md), [T042](T042-tagged-corpus-and-dictionary-build.md), [T044](T044-downstream-impact-evaluation.md), [T048](T048-bioadi-runtime-and-resolver.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: pyproject.toml; README.md; docs/architecture.md; docs/testing-and-quality.md; T040/T042/T044 reports.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Package and test the Python library/CLI with lightweight default dependencies and optional Ab3P/PLOD/resource integrations. Document Windows cache replay and supported live Linux operation.
2. Provide concise installation, embedding, experiment, resource-query and migration examples; synchronize architecture and extension documentation.
3. Assemble source/model/resource notices, versioned artifact manifests, research results, limitations and complete environment recipes. Keep third-party model and text redistribution separate from the package's MIT declaration.
4. Run clean-install validation on supported environments, offline examples, a marked real-dependency smoke and the full coverage gate.
5. Prepare local release artifacts and a release checklist. External package/data publication is a distinct explicit action.

## Acceptance criteria

- A new environment can install the package, resolve a local document, replay a documented experiment and query a supplied resource using the release instructions.
- The release identifies measured strengths, remaining failure modes, model/data identities and downstream evidence without unsupported claims.
- All required preceding deliverables are complete or explicitly labeled unavailable/provisional; no partially validated research milestone is relabeled complete.

## Verification

Wheel/install smoke, documented example replay, artifact integrity/migration, supported-platform checks and full quality gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

An earlier developer preview can ship after T032/T043 with explicit limitations, but it is not completion of this full project plan. Do not upload packages, models or corpora without publication authorization.

## Inputs and possible blockers

Validated results and permitted distributable artifacts; final release size and channels can be decided after the local package is reviewable.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T045-release-and-reproducibility-package.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
