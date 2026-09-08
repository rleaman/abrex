# T033 completion: structural candidate generators

## Delivered

- Added registry-backed `reverse_order`, `nested_parenthetical` and
  `structured_relations` candidate generators with typed bounds and explicit
  pruning diagnostics.
- Extended `ArticleDocument` and segmenters to carry T027 structural metadata
  without changing canonical text or offsets.
- Structured candidates preserve table row/definition-item source paths and
  map text only within declared canonical section locations. Image-only
  regions remain explicitly uncovered.
- Added regression tests for reverse-order, Unicode-context, nested,
  structured-table and metadata-required behavior.

## Evidence

The bounded T033 development report is
[`T033-candidate-evidence-report.json`](../../artifacts/T033-candidate-evidence-report.json).
On the identical 64-record T022 smoke slice with 143 gold pairs, the existing
parenthetical generator emitted 1,575 candidates and covered 123 gold pairs
(0.8601). The structural-prose variant emitted 1,737 candidates and covered
the same 123 pairs (0.8601): it expanded candidate volume by 162 without
claiming a recall gain. This is an honest no-gain result for that historical
slice; structured table/definition-list coverage is measured separately when
ArticleDocument metadata is available.

## Verification

- Structural, literature and candidate tests — 32 passed.
- Targeted strict mypy — passed for 10 files.
- Ruff check and format — passed.
- Candidate coverage report generation — passed deterministically.

## Limitations and next task

The T022 slice is exploratory and contains canonical records without T027
structure metadata, so it cannot validate table/definition-list recall. The
generators enumerate possibilities and do not accept or score them. T034 is
now dependency-ready (T028, T029, T033 and T046 are complete).
