# T010 - Experiment Runner and Reproducibility Layer

## Goal

Create a declarative experiment command that composes corpus, resolver, evaluator, metrics, and reporters from YAML and records everything needed to reproduce a run.

## Depends on

T001, T004, T005, T006.

## Scope

Implement an experiment application service and thin CLI capable of:

1. resolving configuration;
2. loading a canonical corpus artifact;
3. instantiating a resolver;
4. running or loading valid cached predictions;
5. evaluating under configured matching/metrics;
6. running configured reporters;
7. writing a run manifest.

Run manifest should include, where available:

- timestamp;
- git commit and dirty state;
- resolved config;
- corpus fingerprint;
- resolver key/version/config;
- environment/package snapshot;
- seed;
- prediction artifact fingerprint;
- evaluation artifact fingerprint.

## Caching

Prediction reuse must be protected by a key/fingerprint based on relevant inputs and resolver configuration. Never reuse a cache merely because a filename exists.

## Acceptance criteria

A checked-in example YAML can run end-to-end with a toy resolver. Repeated identical runs reuse valid prediction artifacts when configured to do so and produce equivalent evaluation output.
