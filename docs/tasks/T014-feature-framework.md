# T014 - Feature Extraction Framework

## Goal

Provide a registry-driven, inspectable feature layer for candidate scoring and error analysis.

## Depends on

T001, T013.

## Scope

Implement feature extractor protocol/registry and composable feature sets for transparent features such as:

- character alignment statistics;
- token counts/ratios;
- capitalization patterns;
- digit/punctuation patterns;
- short-form/long-form length relationships;
- position/direction;
- lexical cue indicators;
- parenthetical construction metadata.

## Requirements

- feature names stable and explicit;
- deterministic output ordering;
- no hidden access to evaluator gold labels;
- feature configuration recorded in experiment config;
- efficient batch extraction without premature optimization.

## Acceptance criteria

A configured feature set can transform candidate artifacts into a deterministic tabular/matrix representation with schema metadata suitable for analysis or a later model.
