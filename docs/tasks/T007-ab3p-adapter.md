# T007 - Ab3P Baseline Adapter

## Goal

Make Ab3P a reproducible resolver implementation behind the common resolver contract.

## Depends on

T005.

## Scope

Implement:

- `ab3p` resolver plugin;
- external executable configuration;
- safe subprocess wrapper;
- temporary input/output handling;
- parser for Ab3P output;
- mapping predictions back to canonical document spans;
- stderr/exit-code capture;
- timeout configuration;
- version/provenance capture where feasible;
- clearly marked integration tests.

## Engineering constraints

- subprocess mechanics belong in infrastructure, not domain;
- never shell-concatenate untrusted document text;
- temporary files/directories must be cleaned reliably;
- failures should identify document IDs and preserve diagnostic context;
- offset reconstruction ambiguity must be explicit and testable.

## Testing

Unit-test output parsing separately from executable integration. Provide fixture outputs for representative abbreviation patterns and malformed tool output.

## Acceptance criteria

When an Ab3P executable is configured, the resolver runs through the same batch interface as a toy resolver and emits canonical prediction artifacts. When Ab3P is absent, ordinary unit tests still pass and integration tests skip with a clear reason.
