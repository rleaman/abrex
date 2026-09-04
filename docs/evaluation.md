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
