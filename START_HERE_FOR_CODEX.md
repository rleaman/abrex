# Abbreviation Resolution Project - Codex Handoff

## Purpose

Build a research-grade, extensible abbreviation-definition extraction platform for biomedical and scientific literature. The immediate purpose is not to jump to a new model. The first goal is to create a trustworthy experimental substrate in which baselines, candidate generators, rule systems, learned scorers, and later production integrations can be swapped in and evaluated under the same contracts.

The central architectural principle is:

```text
Document
  -> Resolver
  -> list[AbbreviationDefinition]
  -> Evaluator
```

Every resolver must be interchangeable. Evaluation must not know or care how a resolver is implemented.

## What Codex should do first

1. Read `AGENTS.md` completely.
2. Read [current work](docs/CURRENT_WORK.md), the assigned task, relevant public contracts and the specific dependency acceptance artifacts needed for that task. Do not read all of `docs/` or recursively reread historical task instructions. Consult historical plans/notes only for a concrete question; their dated status is not current authority.
3. If this is a fresh repository and no task number was assigned, implement only `docs/tasks/T000-bootstrap-repository.md`.
4. After T000, implement only task numbers explicitly assigned by the user. Never treat the existence of later task files as authorization to execute them.
5. Before an assigned task, verify that its dependencies are already satisfied; if not, report the missing dependency rather than silently absorbing large prerequisite work into the task.
6. Do not silently change scientific contracts, annotation semantics, or evaluation definitions. If a scientific choice is underspecified, expose it as configuration and document the unresolved decision rather than inventing a hidden default.
7. Keep each task independently reviewable. Do not bundle unrelated refactors into an assigned task.

## Initial implementation sequence

The recommended first milestone is:

- T000: repository bootstrap
- T001: configuration and registry infrastructure
- T002: core domain schema and provenance
- T003: corpus adapter and normalization framework
- T004: corpus validation and canonical serialization
- T005: resolver interface and execution contract
- T006: evaluation contract and matching engine
- T007: Ab3P baseline adapter
- T008: regression/golden-test infrastructure
- T009: error-analysis/reporting framework
- T010: experiment runner and reproducibility layer

Only after that substrate is stable should model-facing work begin.

## Non-goals for the first milestone

Do not:

- train a transformer;
- invent a new abbreviation algorithm;
- optimize benchmark results before evaluation semantics are frozen;
- mix PMC/PubMed retrieval concerns into core resolver logic;
- make dataset-specific assumptions in shared domain objects;
- hard-code component choices that should be registry/config driven;
- add a heavy framework when a small explicit abstraction is sufficient.

## Deliverables expected from every task

Each task must leave the repository in a passing state and include:

- implementation;
- unit tests;
- integration or regression tests where appropriate;
- type annotations;
- documentation of public extension points;
- configuration examples when configuration is added;
- a short task completion note under `docs/tasks/completed/` or equivalent, summarizing files changed, tests run, and any unresolved issues.

## Engineering priority order

When tradeoffs arise, prioritize:

1. correctness and reproducibility;
2. explicit contracts and invariants;
3. cohesion and dependency direction;
4. testability;
5. configurability and extension hooks;
6. observability and debuggability;
7. performance;
8. convenience.

Do not sacrifice the earlier items for the later ones without explicit user approval.
