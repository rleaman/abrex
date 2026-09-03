# T013 - Candidate Generation Framework

## Goal

Separate candidate enumeration from acceptance/scoring so future rule-based and learned systems can share the same candidate substrate.

## Depends on

T001, T002, T008.

## Scope

Implement:

- `CandidateGenerator` protocol and registry;
- canonical candidate object with short/long spans, construction metadata, and provenance;
- configurable candidate-generation pipeline;
- at least one conservative parenthetical generator modeled on well-understood local-definition constructions;
- diagnostics for candidate pruning reasons.

## Scientific boundary

Candidate generation should aim for high recall, but its intended scope and exclusions must be explicit. Do not claim benchmark improvements without evaluation.

## Acceptance criteria

Candidate artifacts can be generated independently, serialized for analysis, and consumed by later resolver/scorer implementations without depending on evaluator internals.
