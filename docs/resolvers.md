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

## Learned scorer adapter

`learned_scorer` hosts a persisted T015 scorer behind the same resolver
contract. Its parameters select a candidate pipeline, feature set, scorer
configuration, and model artifact path. It generates candidates and features
per canonical document, applies the explicitly configured calibration and
selection hooks, and returns ordinary `AbbreviationDefinition` predictions.
The adapter performs inference only; training labels, split manifests, and
model fitting remain explicit application steps.

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
provenance. New cache keys include a verified T018 installation identity:
the manifest, executable, all semantic WordData resources, and wrapper/parser
versions. The identity is content-based rather than path-based, so an
unchanged installation may be replayed after relocation. Changed content,
schema, resources, incompatible provenance, or a missing identity/entry is an
explicit cache miss; label-only legacy entries are rejected and must be
rebuilt. Excluding the backend allows a subprocess-populated cache to be
consumed by `cache_only`, including on Windows without a local Linux binary.
Successful zero-output Ab3P runs are cached and replayed as legitimate zero
predictions. Cached stdout goes through the same parser and canonical span
reconstruction code as live output.

### Native offset output

T021 adds an opt-in `output_format: offset_jsonl` path. The task-owned
`identify_abbr_offsets` frontend calls the unchanged Ab3P library once per
input line and emits versioned JSONL containing the detected pair, precision,
strategy, line identity, and native `sf_offset`/`lf_offset` byte offsets.
Those offsets are checked against the exact UTF-8 input (including CRLF),
converted to Python character intervals, and rejected if they do not land on
UTF-8 boundaries or slice to the reported forms. No occurrence search is
performed, so repeated definitions and later short-form reuse retain their
actual positions. Legacy `output_format: text` remains a separately
identified replay path and raises an ambiguity error when text-only
reconstruction cannot identify exactly one pair.

The offset executable must be selected explicitly in the installation because
it is a wrapper around the same upstream library:

```yaml
resolver:
  type: ab3p
  params:
    backend: subprocess
    output_format: offset_jsonl
    installation:
      manifest: docs/artifacts/ab3p-installation-manifest.json
      root: /opt/ab3p
      executable: identify_abbr_offsets
      resource_directory: WordData
    cache:
      path: artifacts/ab3p-offset-cache
      read: true
      write: true
```

The output schema is `ab3p-offsets-v1`; output format and schema identity are
part of the cache key, so text and native-offset artifacts cannot be mixed.

Example Linux configuration:

```yaml
resolver:
  type: ab3p
  params:
    backend: subprocess
    timeout_seconds: 60
    installation:
      manifest: docs/artifacts/ab3p-installation-manifest.json
      root: /opt/ab3p
      executable: identify_abbr
      resource_directory: WordData
    cache:
      path: artifacts/ab3p-cache
      read: true
      write: true
```

`installation.root` is the copied T018 build directory. ABREX verifies the
manifest-declared files before running and passes that root as subprocess
`cwd`, allowing Ab3P's `path_Ab3P` lookup to work from any caller directory.
For offline replay, omit `root`; the manifest identity is still checked and a
Linux executable is not required. The older `installation_label`-only form is
not accepted for new cache entries.

Copy `artifacts/ab3p-cache` and the installation manifest to the Windows
checkout and change only the backend to `cache_only` (retaining the cache path
and manifest identity).
Cache population uses the existing resolver command, for example
`abrex resolver run docs/examples/resolver-ab3p-cache.yaml --input
data/processed/benchmark.jsonl --output artifacts/ab3p-predictions.jsonl`.
Live integration tests are intentionally separate and should be enabled only
when an executable is configured; ordinary tests do not require Ab3P.

The reproducible supplied-source build is documented in
[`docs/development-environments.md`](development-environments.md), with its
verified executable, library, and WordData identities in
[`docs/artifacts/ab3p-installation-manifest.json`](artifacts/ab3p-installation-manifest.json).
The upstream executable reads `path_Ab3P` from its current working directory;
an invocation from another directory must provide that file with a Linux path
to `WordData`, or change into the installation directory first. The verified
build requires Ubuntu/WSL execution and does not provide a native Windows
binary.

Cache identity correction: the backend is intentionally excluded from the
cache key so a live subprocess cache can be read by `cache_only`. A verified
installation manifest is the preferred identity. Digest-only configurations
remain an explicit compatibility mode with unverified resources; a stable
label alone cannot read or write a cache.

## Schwartz--Hearst baseline

`schwartz_hearst` is a dependency-free implementation of the published
Schwartz--Hearst backwards character-alignment heuristic. It scans canonical
text for `long form (SHORT)` constructions, ignores non-alphanumeric
characters by default, and returns spans in the unchanged document coordinate
space. `max_long_form_words` defaults to
`min(len(short) + 5, 2 * len(short))`; `minimum_short_form_length`,
`ignore_non_alphanumeric`, and `case_sensitive` are explicit configuration
parameters. The baseline supports parenthetical short forms after their long
forms only. Reverse-order and nested-parenthesis constructions are
intentionally not accepted, and no deduplication or evaluator-specific policy
is applied.

The source algorithm is Schwartz and Hearst, “A Simple Algorithm for
Identifying Abbreviation Definitions in Biomedical Text,” *Pacific Symposium
on Biocomputing* 8 (2003), 451–462:
<https://pubmed.ncbi.nlm.nih.gov/12603049/>.

The default candidate window is the published
`min(len(short) + 5, 2 * len(short))` word bound, and the first short-form
character must match a long-form word initial. These constraints are enforced
before a canonical span is emitted.

```yaml
resolver:
  type: schwartz_hearst
  params:
    minimum_short_form_length: 2
    max_long_form_words: null
    ignore_non_alphanumeric: true
    case_sensitive: false
```

## PLODv2 independent span detection

The optional `plodv2` resolver loads the pinned Flair checkpoint described in
[`plod-runtime.md`](plod-runtime.md). It emits one prediction per detected
short-form (`AC` is mapped explicitly to `SF`) or long-form (`LF`); it does
not pair spans or treat span scores as pair probabilities. The checkpoint,
runtime, segmentation, window overlap, and duplicate policy are part of the
resolver cache identity.

```yaml
resolver:
  type: plodv2
  params:
    checkpoint_path: /path/to/pytorch_model.bin
    checkpoint_sha256: 3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277
    device: cpu
    max_chars_per_window: 4096
    window_overlap: 128
    duplicate_policy: deduplicate
```

The detector also exposes `PlodSpanRecord` and `serialize_span_record` for
artifacts containing raw labels, translated canonical offsets, scores, window
origins, and validation diagnostics. Flair and PyTorch remain optional and
are imported only when this component is constructed.

## PLODv2 pairing

`plodv2_pairing` composes the detector with an explicit pairing strategy. The
default `position_anchored` strategy evaluates only the text between each
candidate's actual spans, uses deterministic cost ordering and one-to-one
selection, and retains local rejection diagnostics through `pair_record`.
`pattern_greedy` is available as a named compatibility strategy; it is not
claimed to be globally optimal. Set `selection: shared_long_form` when the
scientific protocol permits several short forms for one long form, and set
`require_local_pattern: true` to abstain when the candidate-position pattern
does not match.

```yaml
resolver:
  type: plodv2_pairing
  params:
    checkpoint_path: /path/to/pytorch_model.bin
    checkpoint_sha256: 3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277
    strategy: position_anchored
    selection: one_to_one
    allow_reverse_order: true
    max_gap: 160
    require_local_pattern: false
```

Standalone model span scores are preserved in provenance notes and raw span
artifacts; the prediction score is the separately computed pair score.
