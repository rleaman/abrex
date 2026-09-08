# Evaluation Extension Point

The `abrex.evaluation` package evaluates canonical `CorpusRecord` values
against resolver prediction records. Evaluation does not import resolver
implementations; it consumes the narrow prediction-record shape and applies
named matching and metric plugins.

## YAML composition

The top-level configuration selects a matching policy and an ordered list of
metrics:

```yaml
matching:
  type: exact_pair
  params: {}

metrics:
  - type: pair_prf
    params:
      averaging: micro
      zero_division: zero
```

For corpora whose acronym and long-form spans are supplied independently, such
as SDU@AAAI-22 AE, use the span-level policy and metric instead:

```yaml
matching:
  type: exact_span
  params: {}

metrics:
  - type: span_prf
    params:
      averaging: micro
      zero_division: zero
```

`exact_span` projects each populated side of an annotation into an independent
single-form span and matches short and long spans separately. It never infers
a relationship from source list order. `span_prf` reports span counts, whereas
`pair_prf` reports complete abbreviation-pair counts.

Use `evaluation_config_from_resolved` and `create_evaluator` at the
application-composition boundary. Callers embedding the package should pass
local `Registry` instances to both functions when registering custom plugins.

## Initial policies and metrics

`ExactPairMatchingPolicy` requires equal document IDs, short-form spans, and
long-form spans. It performs deterministic one-to-one assignment and retains
duplicates. Missing spans become explicit `unscoreable` outcomes under the
initial policy. It does not normalize text, punctuation, case, or boundaries.

`PairPRFMetric` reports micro pair-level `tp`, `fp`, `fn`, `precision`, `recall`,
and `f1`. Its default zero-denominator behavior is an explicit `0.0`; set
`zero_division: raise` to reject empty denominators.

The evaluator returns immutable per-document `DocumentEvaluation` records and
an immutable `EvaluationResult` containing detailed `MatchOutcome` values.
This preserves the inputs needed by later reporters and uncertainty plugins.

Evaluation is driven by the gold document set. Every gold document must have
exactly one prediction record; an omitted record is a coverage error, and an
unknown or duplicate prediction document ID is rejected. A resolver that
successfully found no pairs must therefore emit an explicit empty
`PredictionRecord`, which is scored normally. Resolver execution failures are
diagnosed and are never treated as empty predictions.

When evaluating a `PredictionArtifact`, pass
`expected_dataset_fingerprint` to verify that it was generated from the same
canonical dataset build.

## Reporting

`abrex.reporting.ReportContext` packages an immutable evaluation result with
run metadata, configuration identity, and optional canonical documents. The
`json`, `error_table`, and `html_error_report` registry components render the
same stored match outcomes; reporting does not rerun resolution or matching.
Configure them with a list such as:

```yaml
reporting:
  reporters:
    - type: json
    - type: html_error_report
      params:
        context_chars: 120
```

Stratification dimensions are explicit hooks. A dimension returning `None`
for an outcome excludes it from that dimension; no corpus, positional, or
parenthetical classifier is inferred by the framework.

## Comparative resolver analysis

`abrex.evaluation.compare_resolvers` evaluates several complete prediction
sets on the same document universe under one named policy. It reports
standalone counts, per-resolver correct occurrences, unique correct
occurrences, a gold-assisted union-recall oracle, and seeded article-group
bootstrap intervals. Duplicate gold occurrences remain distinct through their
deterministic match positions. Use `mode: exact_pair` and `PairPRFMetric` for
paired corpora, or a separate `mode: exact_span` analysis for independent span
corpora; the results are never pooled. `write_comparative_report` writes a
deterministic JSON evidence artifact.

The reproducible historical T031 matrix is built with
[`scripts/build_t031_comparison.py`](../scripts/build_t031_comparison.py) and
the pinned configuration
[`T031-smoke-plodv2-pairing.yaml`](../configs/benchmarks/T031-smoke-plodv2-pairing.yaml).
Its tracked evidence report is
[`T031-comparative-analysis-report.json`](artifacts/T031-comparative-analysis-report.json).
On the 64-document T022 smoke slice, native-offset Ab3P, PLODv2 pairing and
Schwartz--Hearst obtain 121/143, 104/143 and 110/143 exact-pair true
positives respectively; their gold-assisted union reaches 130/143 (0.9091)
and is reported only as an exploratory oracle. The report includes seeded
document-group bootstrap intervals, artifact fingerprints, and explicit
limitations of the historical slice.

The oracle is not a deployable resolver score. It measures attainable union
recall on the supplied document universe and must retain its denominator,
matching policy, duplicate policy, execution failures, and corpus limitations.
