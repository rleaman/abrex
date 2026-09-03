# T002 - Core Domain Schema and Provenance

## Goal

Define the canonical scientific value objects used by every corpus, resolver, and evaluator.

## Depends on

T000.

## Scope

Implement narrow, well-tested domain models equivalent to:

- `TextSpan`;
- `Document`;
- `AbbreviationDefinition`;
- `AnnotationProvenance`;
- prediction metadata/confidence representation;
- canonical record/container types needed for evaluation.

## Required invariants

- spans use half-open `[start, end)` semantics;
- invalid negative or reversed spans are rejected;
- text-span consistency can be validated against a document;
- document identifiers are explicit and stable;
- provenance can preserve source corpus, source record ID, original coordinates/text, adapter identity/version, and transformation notes;
- prediction-specific metadata does not pollute gold/source semantics.

## Design constraints

- no YAML/file/subprocess imports in domain modules;
- prefer immutable value objects;
- keep serialization concerns separate from the core value-object API;
- support incomplete source annotations explicitly where necessary; do not invent missing coordinates.

## Tests

Include edge cases involving zero-length/invalid spans, Unicode text, repeated abbreviations, overlapping spans, and provenance.

## Acceptance criteria

The domain layer can represent all known common forms of abbreviation-definition annotations without referring to any specific dataset format.
