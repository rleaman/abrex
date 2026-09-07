# T020 Make Ab3P resource lookup and cache identity reliable

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

Run the installed Ab3P from any application working directory and invalidate predictions whenever its effective installation changes.

## Dependencies and reading

[T018](T018-build-and-verify-real-ab3p.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/infrastructure/ab3p.py; src/abrex/resolvers/adapters/ab3p.py; src/abrex/resolvers/adapters/ab3p_resolver.py; src/abrex/experiments/runner.py; tests/unit/test_ab3p.py.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Add a typed installation/resource configuration referencing the T018 manifest. Resolve the required working directory/path_Ab3P safely without process-wide chdir or shell interpolation.
2. Expose resolver-owned cache_identity that includes verified executable, resource and relevant wrapper/parser versions; propagate it to raw caches and the experiment-level prediction cache.
3. Retain portable cache_only replay on Windows. Define migration/versioning for legacy label-only entries and fail clearly on incompatible manifests.
4. Record actual resolved identities in run provenance. Different absolute paths with equivalent content may replay raw caches; a stable label alone must not permit changed binaries/resources to reuse results.

## Acceptance criteria

- A live call from an unrelated working directory finds WordData and returns the same pairs as upstream.
- Replacing executable or WordData at the same path invalidates both relevant cache layers; repeat unchanged runs reuse validated output.
- Offline replay checks installation identity without requiring a local Linux executable. Missing resources and incompatible cache versions are explicit errors.

## Verification

Mocked identity-change and relocation regressions, real T018 executable smoke, cache round trip, experiment cache tests, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Do not change pair reconstruction or detection algorithms here. Old cache compatibility must be explicit, not guessed.

## Inputs and possible blockers

Verified T018 installation and a Linux ABREX environment.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T020-ab3p-runtime-and-cache-identity.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

