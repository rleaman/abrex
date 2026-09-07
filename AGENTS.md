# Permanent Engineering Instructions for Codex

These instructions apply to all work in this repository unless a task explicitly overrides them.

## Settled resource decisions

The BADREX-corrected `schwartz_hearst_badrex` and `medstract_badrex` corpora
are unavailable and excluded. Do not recheck their URLs, search for copies,
recreate configs or raise their absence as a blocker in routine work. Follow
[the recorded decision](docs/badrex-availability.md); reopen only on a user
request, a newly supplied source or concrete new evidence encountered during
assigned work. Historical completion notes do not override this decision.

## 1. Architectural style

Use a modular monolith with strong internal boundaries. Maximize cohesion and minimize coupling.

Preferred dependency direction:

```text
CLI / experiment orchestration / adapters
                |
                v
        application services
                |
                v
       domain interfaces/models
                ^
                |
  infrastructure implementations
```

The domain layer must not import CLI, filesystem, subprocess, web, YAML, or dataset-specific infrastructure.

Use dependency inversion at important extension points. Prefer `typing.Protocol` or narrow abstract interfaces over concrete cross-module dependencies.

Avoid global mutable state. A registry may have a process-level default instance for convenience, but core code must support explicit registry injection for tests and embedding.

## 2. Configurability

Most component selection must be configurable through YAML plus registry lookup.

Examples of registry-backed extension points:

- corpus loaders/adapters;
- annotation normalizers;
- document preprocessors;
- candidate generators;
- resolvers;
- alignment/scoring strategies;
- feature extractors;
- evaluators/matching policies;
- metrics;
- reporters/exporters;
- experiment hooks;
- serializers;
- cache backends.

A YAML file should select a component by a stable registry key and provide validated parameters. Do not scatter `if resolver == ...` dispatch logic across the codebase.

Configuration must be parsed into typed configuration models at the boundary. Do not pass untyped dictionaries deeply through the application.

Configuration resolution must be deterministic. Resolved configuration should be serializable and saved with experiment outputs.

## 3. Registry design

Create a small, generic registry abstraction rather than one bespoke registry implementation per component type.

Required characteristics:

- typed where practical;
- duplicate-key protection by default;
- aliases only when explicit;
- helpful errors listing available keys;
- decorator registration and explicit registration APIs;
- creation/factory support separated from registration where useful;
- test-local registry instances supported;
- no import-time side effects beyond deliberate plugin registration modules;
- stable public keys treated as API.

Do not use Python entry points initially unless there is a concrete need for separately distributed plugins. Design so entry points can be added later without changing domain contracts.

## 4. Domain-model rules

Core domain objects must represent scientific concepts, not file formats or tool-specific output.

At minimum expect concepts equivalent to:

- `Document`;
- `TextSpan`;
- `AbbreviationDefinition`;
- `AnnotationProvenance`;
- `CorpusRecord` or equivalent evaluation record;
- resolver prediction metadata.

Offsets must have explicit semantics. Use half-open character intervals `[start, end)` unless the scientific contract explicitly changes this.

Preserve raw/source identifiers and provenance sufficient to trace every normalized annotation back to its source representation.

Avoid inheritance-heavy entity models. Prefer immutable or effectively immutable value objects and composition.

## 5. Scientific boundaries

Scientific contracts are higher authority than implementation convenience.

Do not silently decide:

- whether long-form or short-form span boundaries may be relaxed;
- whether punctuation differences count as exact matches;
- how nested/overlapping definitions score;
- whether duplicates collapse;
- how ambiguous gold annotations are represented;
- whether document normalization changes offsets;
- train/dev/test splits;
- corpus trustworthiness or inclusion/exclusion criteria.

If a task does not specify one of these, implement the mechanism to make the choice explicit and configurable, then document the unresolved decision.

## 6. Quality standards

Target Python 3.13 unless constrained by an external dependency.

Use:

- `pyproject.toml` as the project configuration source;
- `src/` layout;
- pytest;
- ruff for linting and formatting;
- mypy with a meaningfully strict configuration;
- pre-commit hooks;
- coverage reporting;
- structured logging using the standard library or a thin wrapper;
- pathlib rather than raw path strings internally;
- context managers for resources;
- explicit encoding for text I/O.

Public functions, methods, and classes should be typed. Prefer total functions and explicit failure modes.

Avoid broad `except Exception` unless re-raising with context at a system boundary.

Use custom exception types for meaningful domain/application failures.

No silent data loss. Any dropped, repaired, ambiguous, or unparseable annotation must be counted and reportable.

## 7. Testing policy

Tests are part of the feature, not cleanup.

Use a test pyramid:

- many fast unit tests for pure logic;
- focused contract tests for every registry-backed interface;
- integration tests for corpus adapters and external tools;
- golden/regression tests for resolver outputs and evaluation behavior;
- end-to-end smoke tests for experiment configuration.

Whenever a bug is found, add a regression test before or with the fix.

Do not make unit tests depend on network access.

External-tool tests such as Ab3P must be clearly marked and skippable when the dependency is unavailable.

## 8. Reproducibility

Every experiment run should be able to record:

- git commit;
- dirty-tree status;
- resolved YAML configuration;
- package/environment information;
- corpus fingerprints/manifests;
- random seeds;
- resolver/component registry keys and versions where applicable;
- timestamps;
- prediction artifact paths;
- evaluation artifact paths.

Cached predictions must be content-addressed or otherwise protected against accidental reuse under changed inputs/configuration.

## 9. CLI design

CLI commands are thin application adapters. They should parse arguments/configuration, invoke application services, format results, and exit.

Do not put scientific logic in CLI functions.

Design commands so automated experiment runs do not require prompts or interactive state.

## 10. Documentation

Public extension points require documentation and at least one minimal example.

Keep architecture docs synchronized with code. If an assigned task changes an interface or dependency direction, update the relevant docs in the same task.

Use Architecture Decision Records for material choices with long-term consequences.

## 11. Scope discipline

When assigned task `Txxx`, read its dependencies and acceptance criteria. Implement the smallest coherent change that fully satisfies them.

Do not opportunistically rewrite unrelated modules. If cleanup is valuable but out of scope, record it as a proposed task rather than hiding it in the current diff.

Before declaring a task complete, run the task-specific checks plus the repository-wide fast quality gate.
