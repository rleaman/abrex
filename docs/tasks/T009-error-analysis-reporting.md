# T009 - Error Analysis and Reporting Framework

## Goal

Turn evaluator match records into useful research diagnostics without coupling reporting to specific resolver implementations.

## Depends on

T006.

## Scope

Implement reporter registry and at least:

- JSON result reporter;
- TSV/CSV error table reporter;
- human-readable HTML error report.

HTML report should show document context around spans and distinguish TP/FP/FN/mismatched components clearly.

Add optional stratification hooks for dimensions such as:

- corpus;
- abbreviation length;
- long-form length;
- positional construction;
- parenthetical pattern;
- resolver disagreement.

The framework may expose these dimensions before all classifiers are implemented.

## Design constraints

Reporters receive immutable result records and do not recompute matching.

Generated reports must include run metadata and configuration identity.

## Acceptance criteria

An evaluation run can produce machine-readable metrics and a browsable per-error report from the same match-record artifact without rerunning the resolver.
