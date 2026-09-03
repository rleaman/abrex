# T015 - Learned Scorer/Ranker Scaffold

## Goal

Create infrastructure for supervised candidate scoring without prematurely choosing the scientific model.

## Depends on

T010, T013, T014.

## Scientific-review boundary

Model family, labels, split strategy, optimization target, and threshold selection require user approval or an explicit task specification.

## Scope

Implement only the architecture needed to plug in learned scorers:

- scorer protocol/registry;
- fit/predict lifecycle where appropriate;
- artifact persistence/versioning;
- deterministic seed plumbing;
- train/dev/test manifest consumption;
- threshold/calibration configuration hooks;
- prediction metadata linking model artifact and feature config.

A trivial or sklearn baseline may be used solely to prove the framework if explicitly documented as a plumbing test, not as a scientific result.

## Acceptance criteria

The experiment system can host a learned scorer without altering candidate, evaluator, or reporting contracts.
