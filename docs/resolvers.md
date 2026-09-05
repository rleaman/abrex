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

## Ab3P baseline

`ab3p` is an optional registry resolver for the original external Ab3P
executable; Ab3P is not an ABREX or build-time dependency. Use
`backend: subprocess` with an explicitly configured executable on Linux to
populate a portable cache, or use `backend: cache_only` on Windows/offline
machines. Native Windows execution is neither supported nor required.

The cache stores the canonical document ID and SHA-256, exact UTF-8 input,
raw stdout/stderr, exit status, adapter/cache schema, and execution
provenance. Its key is based on document content, exact input, adapter
version, backend, and installation label—not absolute paths. Consequently a
cache directory can be copied between systems. Changed content, schema,
semantic configuration, or a missing entry is an explicit cache miss; it is
never an empty successful result. Successful zero-output Ab3P runs are cached
and replayed as legitimate zero predictions. Cached stdout goes through the
same parser and canonical span reconstruction code as live output.

Example Linux configuration:

```yaml
resolver:
  type: ab3p
  params:
    backend: subprocess
    executable: /opt/ab3p/identify_abbr
    timeout_seconds: 60
    cache:
      path: artifacts/ab3p-cache
      read: true
      write: true
    installation_label: nlm-linux-ab3p
```

Copy `artifacts/ab3p-cache` to the Windows checkout and change only the
backend to `cache_only` (retaining the cache path and installation label).
Cache population uses the existing resolver command, for example
`abrex resolver run docs/examples/resolver-ab3p-cache.yaml --input
data/processed/benchmark.jsonl --output artifacts/ab3p-predictions.jsonl`.
Live integration tests are intentionally separate and should be enabled only
when an executable is configured; ordinary tests do not require Ab3P.

## Schwartz--Hearst baseline

`schwartz_hearst` is a dependency-free implementation of the published
Schwartz--Hearst backwards character-alignment heuristic. It scans canonical
text for `long form (SHORT)` constructions, ignores non-alphanumeric
characters by default, and returns spans in the unchanged document coordinate
space. `max_long_form_words` defaults to the original `2 * len(short) - 1`
candidate window; `minimum_short_form_length`, `ignore_non_alphanumeric`, and
`case_sensitive` are explicit configuration parameters. The baseline supports
parenthetical short forms after their long forms only. Reverse-order and
nested-parenthesis constructions are intentionally not accepted, and no
deduplication or evaluator-specific policy is applied.

The source algorithm is Schwartz and Hearst, “A Simple Algorithm for
Identifying Abbreviation Definitions in Biomedical Text,” *Pacific Symposium
on Biocomputing* 8 (2003), 451–462:
<https://pubmed.ncbi.nlm.nih.gov/12603049/>.

```yaml
resolver:
  type: schwartz_hearst
  params:
    minimum_short_form_length: 2
    max_long_form_words: null
    ignore_non_alphanumeric: true
    case_sensitive: false
```
