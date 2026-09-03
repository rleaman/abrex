# T000 - Bootstrap Repository

## Goal

Create the initial Python repository skeleton and quality toolchain without implementing scientific behavior.

## Scope

Create:

- `pyproject.toml`;
- `src/abrex/` package;
- test directories;
- `configs/` hierarchy;
- `docs/decisions/` with an ADR template;
- pre-commit configuration;
- basic logging setup;
- top-level README with developer commands;
- task-completion-note convention.

Adopt Python 3.13 unless a concrete dependency prevents it.

## Engineering requirements

- `src/` layout;
- ruff formatting/linting;
- mypy meaningfully strict;
- pytest and coverage;
- no runtime dependency that is not justified;
- one command or script for the fast quality gate;
- one command for the full test gate.

## Do not

- create placeholder modules for all future concepts;
- implement corpus parsing, resolver logic, or evaluation logic;
- introduce Hydra, a DI container, a web framework, or a workflow engine without demonstrated need.

## Acceptance criteria

1. Fresh environment installation succeeds.
2. Importing `abrex` succeeds.
3. Fast quality gate passes.
4. At least one trivial unit test proves package/test discovery.
5. README documents install, lint, typecheck, and test commands.
6. ADR template exists.
