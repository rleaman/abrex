# Resolver Extension Point

`abrex.resolvers.Resolver` is the application-facing contract for every
abbreviation resolver. A resolver receives one canonical `Document` and
returns an iterable of `AbbreviationDefinition` predictions. It must use the
document text and Unicode half-open offsets exactly as supplied; text
normalization and coordinate conversion belong outside this boundary.

Resolver implementations expose a non-empty `identity` and `version` and are
selected by a stable key in the injectable `RESOLVERS` registry. Configuration
uses the same typed component shape as other plugins:

```yaml
resolver:
  type: toy
  params:
    confidence: 1.0
```

`create_resolver_executor` validates parameters, records the registry key and
implementation version, and returns a `ResolverExecutor`. The executor has
single-document (`resolve_document`) and batch (`resolve_documents` or
`resolve_batch`) methods. It validates document identity, bounds, and captured
text. Duplicate predictions are retained; no scoring or deduplication policy
is applied.

Validation is strict by default and raises `PredictionValidationError` after
collecting all invalid-output diagnostics. `validation_mode: permissive` drops
invalid predictions while retaining structured diagnostics. Resolver failures
are structured as `ResolverExecutionError`; batch callers may explicitly use
`error_policy: collect` to continue and retain an execution diagnostic.

Prediction output is serialized separately from canonical gold data as
deterministic `predictions-v1` JSONL. Each line contains resolver metadata,
the document/record identifier, predictions, and diagnostics, but no
`gold_annotations` field. A prediction artifact can carry the canonical
dataset fingerprint used to generate it; the resolver CLI records this
automatically, while library callers can pass `dataset_fingerprint` to
`PredictionArtifact.from_run` or `write_prediction_artifact`. Readback and
evaluation can verify that fingerprint against the intended canonical build.
The artifact can also be fingerprinted and read back with
`read_prediction_artifact`.
