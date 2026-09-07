# Scientific Contracts - Freeze Before Optimization

This file identifies decisions that must be explicit because small implementation choices can materially change benchmark results.

## 1. Canonical text and offsets

Default target convention: Unicode Python string character offsets, half-open `[start, end)` spans, measured against the canonical document text stored in the same record.

Any normalization that changes text length must either preserve an offset mapping or create a new canonical text artifact with explicit provenance. Never quietly normalize text and retain old offsets.

## 2. Definition object

A gold or predicted abbreviation definition should minimally capture:

- document identifier;
- short-form span and text;
- long-form span and text;
- optional confidence for predictions;
- optional method/component metadata;
- provenance.

The model must support cases where source corpora provide incomplete span information, but incompleteness must be represented explicitly rather than fabricated.

## 3. Pair identity

Do not assume a pair is identified only by normalized text. Evaluation may need to distinguish repeated definitions by position.

Exact pair scoring should be able to require both short-form and long-form spans to match exactly.

Relaxed policies, if used, must be separate named policies with their own tests.

## 4. Matching

Prediction-to-gold matching is a bipartite assignment problem whenever multiple plausible matches exist. Do not use order-dependent greedy matching unless a policy intentionally specifies it and tests demonstrate the intended behavior.

The matching layer should expose detailed match records so errors can be analyzed, not only aggregate TP/FP/FN counts.

## 5. Duplicates

Duplicate handling must be explicit. Potential policies include preserving duplicates, collapsing identical span pairs, or treating duplicate predictions as false positives after the first match. Do not choose silently.

## 6. Partial annotations

Some corpora may have annotation peculiarities or incomplete spans. Adapter logic may represent these source facts; the evaluator decides what is scoreable under a named policy.

## 7. Dataset splits

Never invent train/dev/test splits without a checked-in manifest and rationale. Splits should be deterministic and document-level unless explicitly justified otherwise.

## 8. Corpus corrections

Corrected versions of historical corpora must be treated as separate dataset variants with distinct identifiers and fingerprints. Do not overwrite original annotations.

## 9. Metric reporting

At minimum support pair-level precision, recall, and F1 with raw TP/FP/FN counts. Additional span-level or component-level metrics may be added as separate metric plugins.

Aggregate metrics should retain per-document match outcomes so confidence intervals and stratified analysis can be computed later without rerunning resolvers.

## 10. Bootstrap/confidence intervals

Do not bake one inferential procedure into the core evaluator. Statistical uncertainty should be a downstream metric/analysis plugin operating on document-level evaluation records.

## 11. T006 exact evaluation defaults

The initial evaluator provides the named `exact_pair` policy. A pair is
scoreable only when both annotations have short-form and long-form spans; the
document ID and both half-open spans must then be equal. Incomplete annotations
are retained in detailed results as `unscoreable` outcomes and are excluded
from TP/FP/FN counts. This is an explicit initial policy, not an inference
about how every corpus should treat partial annotations.

Duplicate annotations are retained. Exact duplicate predictions beyond the
one-to-one matches are reported as false positives, and duplicate gold
annotations beyond the matches are reported as false negatives. Pair-level
precision, recall, and F1 use micro counts. The default `zero_division: zero`
reports `0.0` when a metric denominator is zero; a configured `raise` mode is
available for runs that require an empty denominator to fail.

## 12. T019 historical corpus semantics

Historical variants declare their annotation unit, coordinate convention,
official split, source status and eligible metric in the typed `semantics`
configuration section. Original BioC variants use the named
`relations_or_order_fallback` policy: explicit relation nodes take precedence;
order pairing is used only for a relation-free BioC document under that
source-specific contract. SDU@AAAI-22 AE is independent-span gold and never
uses list-order pairing. SDU@AAAI-21 AD retains acronym coordinates and
expansion text without manufacturing a long-form document span, so it is not
eligible for the local `exact_pair` metric.

BioC document text is rendered from source passages and preserved by default.
Annotation text disagreement, dangling relations, duplicate IDs, unpaired
entities, unequal fallback lists and multiple locations are reported as
diagnostics and are included in the build manifest. A canonical build with no
eligible scoreable units must be rejected or reported as not scoreable by the
benchmark configuration; a zero-valued metric is not evidence of a successful
pair evaluation. The BADREX-corrected variants remain excluded under the
[settled availability decision](badrex-availability.md).
