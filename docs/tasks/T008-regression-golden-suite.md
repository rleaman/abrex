# T008 - Regression and Golden Baseline Suite

## Goal

Create guardrails that make later autonomous Codex work safer by turning semantic drift into test failures.

## Depends on

T004, T006, T007.

## Scope

Build a curated small regression fixture set containing difficult constructions such as:

- standard `long form (SF)`;
- `SF (long form)` where applicable;
- nested parentheses;
- punctuation/hyphenation;
- digits and Greek letters;
- repeated same-text abbreviations at different positions;
- multiple definitions in one sentence/document;
- false-positive-looking parentheticals;
- boundary-sensitive long forms;
- Unicode biomedical text.

Store expected canonical gold records, baseline predictions when available, and exact evaluation outcomes.

## Design constraints

Golden fixtures are human-review artifacts. Do not auto-regenerate them during normal tests.

Keep fixtures small enough to inspect manually.

## Acceptance criteria

A single regression test command can detect changes in canonicalization, Ab3P parsing/predictions, and exact evaluation outcomes on the curated fixture set.
