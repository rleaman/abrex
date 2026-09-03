# T006 - Evaluation Matching Engine

## Goal

Implement a transparent, extensible evaluator whose scientific behavior is determined by named matching-policy and metric plugins.

## Depends on

T002, T004.

## User-review boundary

This task contains scientifically consequential semantics. Codex should implement the mechanism and the explicitly stated default below, but must flag ambiguities rather than silently generalize them.

## Initial default policy

Implement an `exact_pair` matching policy in which a prediction matches a gold annotation only when document ID, short-form span, and long-form span are exactly equal. Matching must be one-to-one.

When multiple potential matches exist, use deterministic maximum-cardinality bipartite matching or an equivalent algorithm that is not dependent on input ordering.

## Scope

Implement:

- matching-policy protocol and registry;
- detailed match outcome records;
- exact-pair policy;
- metric protocol and registry;
- pair-level TP/FP/FN;
- micro precision/recall/F1;
- per-document evaluation records;
- evaluator application service;
- explicit behavior for zero-denominator cases, documented and tested.

## Do not yet

- add fuzzy text matching;
- normalize punctuation/case for scoring;
- add relaxed boundaries unless explicitly assigned later;
- collapse duplicate predictions silently.

## Tests

Exhaustively cover duplicated predictions, repeated text at different positions, crossing/overlapping spans, empty gold/prediction sets, order invariance, and multi-pair assignment.

## Acceptance criteria

Given fixed gold and prediction artifacts, evaluation is deterministic, emits aggregate metrics plus detailed per-document match records, and is invariant to input ordering.
