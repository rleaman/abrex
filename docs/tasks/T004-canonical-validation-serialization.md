# T004 - Canonical Validation and Serialization

## Goal

Make normalized corpora auditable, immutable, fingerprinted artifacts suitable for repeated experiments.

## Depends on

T002, T003.

## Scope

Implement:

- canonical record validation framework;
- strict and permissive validation modes;
- structured validation issue model with severity/code/location;
- JSONL canonical serialization;
- dataset manifest;
- deterministic dataset fingerprint;
- round-trip loader;
- summary report of dropped/repaired/ambiguous/unscoreable annotations.

## Design constraints

- no silent dropping;
- canonical serialization must be versioned;
- manifest includes adapter/config identity and source fingerprints where possible;
- output ordering must be deterministic;
- fingerprint must not change merely because filesystem paths differ, unless path is semantically part of source identity.

## Tests

Golden canonical JSONL fixture, round-trip tests, fingerprint stability tests, validation issue tests, and corruption detection.

## Acceptance criteria

Running the corpus build command twice on unchanged inputs/config produces byte-stable or semantically stable canonical artifacts with the same fingerprint and explicit validation summaries.
