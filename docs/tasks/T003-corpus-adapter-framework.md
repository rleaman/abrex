# T003 - Corpus Adapter and Normalization Framework

## Goal

Create the plugin contract for converting heterogeneous abbreviation corpora into canonical domain records.

## Depends on

T001, T002.

## Scope

Implement:

- `CorpusAdapter` protocol/interface;
- registry integration for corpus adapter selection;
- source-resource descriptor(s);
- normalization pipeline with individually registered normalization steps;
- adapter diagnostics/warnings collection;
- deterministic record iteration contract;
- fixture/demo adapter proving the architecture.

## Design constraints

Separate:

1. parsing source syntax;
2. mapping source fields into canonical concepts;
3. optional normalization/repair;
4. validation.

Do not bury repairs in parsers. Any repair/transformation must be observable through provenance/diagnostics.

## Tests

Provide reusable adapter contract tests and a small fixture source demonstrating clean, malformed, and repairable records.

## Acceptance criteria

A YAML configuration can select a corpus adapter plus a sequence of normalizer plugins and produce canonical records plus a machine-readable diagnostics summary.
