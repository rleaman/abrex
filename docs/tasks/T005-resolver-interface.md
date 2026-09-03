# T005 - Resolver Interface and Execution Contract

## Goal

Define the interchangeable resolver abstraction used by all baseline and future methods.

## Depends on

T001, T002.

## Scope

Implement:

- `Resolver` protocol/interface;
- registry selection/instantiation;
- single-document and batch execution service;
- prediction validation;
- resolver metadata including stable key and implementation version where practical;
- structured execution errors;
- optional confidence handling;
- prediction artifact serialization distinct from gold corpus serialization.

## Design constraints

- evaluator must not be imported;
- resolver does not know how predictions will be scored;
- external-process resolvers are supported through infrastructure adapters, not subprocess logic in the domain interface;
- input document text is canonical and must not be silently modified.

## Tests

Create toy resolver implementations for contract testing, including a failing resolver and invalid-span resolver.

## Acceptance criteria

A YAML-selected toy resolver can run over canonical documents and emit deterministic prediction artifacts with metadata and validation diagnostics.
