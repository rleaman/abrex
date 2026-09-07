# T017 Make development and experiment environments reproducible

Status: Complete (engineering scope; hosted CI replay pending). Assigned implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

A fresh Windows or Linux environment can run the current package and its offline quality gate from documented, reproducible dependencies.

## Dependencies and reading

Existing T000–T016 baseline; no new task prerequisite.

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: pyproject.toml; README.md; docs/testing-and-quality.md; .pre-commit-config.yaml; docs/tasks/completed/T016-pmc-pubmed-integration.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Preserve the Python 3.13 core target and pinned quality tools. Add a reproducible dependency snapshot/lock workflow consistent with pyproject.toml, with documented Windows and Linux installation commands.
2. Provide a fail-fast quality-gate script that creates its temporary parent directory and checks each command's exit status. Keep generated test files and environments out of version control.
3. Add offline CI for the core package on Windows and Linux. Keep real Ab3P and model jobs separate and explicitly skippable; never install neural dependencies merely to import abrex.
4. Reconcile current setup documentation with the audit: BADREX configs are absent; old run counts and historical local-data claims are historical evidence.

## Acceptance criteria

- Clean-environment install, package import, CLI help, unit/contract tests and full coverage gate succeed on the documented supported path.
- Lock/snapshot regeneration is documented; versions used in verification are retained. No tool-version drift between local gate and CI.
- A failing check stops the gate with a nonzero result; missing temp parents no longer cause the documented Windows test command to fail.

## Verification

Run the install/import smoke, gate-script failure-path check, fast gate and full offline coverage suite. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not upgrade algorithms, lower the 95% coverage floor, or force the optional Flair stack into the core environment. CI workflow creation does not authorize publishing a release.

## Inputs and possible blockers

Existing env313 is usable with host access. Fresh dependency acquisition may require network access; report exact missing packages if unavailable.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T017-reproducible-development-environments.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
