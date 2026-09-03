# T001 - Configuration and Registry Infrastructure

## Goal

Implement the small generic infrastructure that will make component selection YAML-driven and registry-backed.

## Depends on

T000.

## Scope

Implement:

- generic registry abstraction;
- stable-key registration and duplicate protection;
- explicit and decorator-based registration;
- helpful unknown-key errors;
- test-local registries;
- typed component specification (`type` + `params`);
- YAML loading and deterministic merge semantics;
- environment-variable interpolation for explicitly marked values;
- resolved-config serialization;
- `config resolve` CLI command or equivalent.

Pydantic v2 is preferred for configuration validation unless there is a reason to choose a lighter alternative.

## Design constraints

- Registry lookup happens in a composition/application layer, never in domain entities.
- Generic registry code must not know about resolvers or corpora.
- Avoid a service locator pattern in core logic.
- Registry keys are public API.
- No hidden import scanning.

## Tests

Cover:

- successful registration/lookup;
- duplicate-key failure;
- unknown-key diagnostics;
- registry isolation;
- YAML merge precedence;
- malformed config diagnostics;
- environment interpolation;
- round-trip serialization of resolved config.

## Acceptance criteria

A minimal YAML file can select a toy registered component, validate its params, instantiate it through a composition function, and print the deterministic resolved config.
