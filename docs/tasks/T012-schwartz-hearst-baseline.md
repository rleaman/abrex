# T012 - Schwartz-Hearst Baseline

## Goal

Provide a clean, testable Schwartz-Hearst-style baseline behind the common resolver interface.

## Depends on

T005, T008.

## Scope

Prefer wrapping a trustworthy, license-compatible implementation if doing so preserves reproducibility and span semantics. Otherwise implement from the published algorithm with clear citation/documentation.

Implementation must expose algorithmic choices as named configuration rather than hidden tweaks.

## Requirements

- registry key `schwartz_hearst`;
- no evaluator dependency;
- span-correct canonical predictions;
- regression tests on curated fixtures;
- documentation of deviations from the original algorithm or wrapped implementation;
- benchmark-ready metadata/version identity.

## Acceptance criteria

The experiment runner can swap `ab3p` for `schwartz_hearst` by changing YAML only.
