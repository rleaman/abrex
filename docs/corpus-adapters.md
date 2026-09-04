# Corpus Adapter and Normalization Extension Point

T003 introduces the `abrex.corpora` boundary for turning a source corpus into
canonical `CorpusRecord` values. A `CorpusAdapter` has two deliberately
separate operations:

1. `parse(resource, diagnostics)` yields typed `ParsedSourceRecord` values;
2. `map_record(source_record)` creates domain objects and preserves source
   fields in `AnnotationProvenance`.

Adapters own the meaning of source coordinates. The shared
`map_source_record` helper is only appropriate when source offsets already use
Unicode Python character offsets and half-open intervals. Other adapters must
perform their own mapping and retain original coordinates in provenance.

`NormalizationPipeline` applies an ordered tuple of `NormalizationStep` plugins
to new immutable records, and `CorpusPipeline` validates them afterward. Each repair must append a
provenance transformation note and emit an `AdapterDiagnostic`. Invalid rows
are retained in the diagnostics summary as dropped records in permissive mode;
`strict: true` raises `CorpusBuildError` after collecting the same summary.
Duplicate record identifiers are preserved and reported rather than silently
collapsed.

## YAML composition

```yaml
corpus:
  adapter:
    type: fixture
    params: {}
  source:
    identifier: embedded-fixture
  normalizers:
    - type: trim_captured_text
      params: {}
  strict: false
```

Validate the resolved section with `CorpusConfig`, then pass it to
`create_corpus_pipeline`. Production code should inject local registries when
embedding the framework or testing a plugin; the default registries provide
the `fixture`, `identity`, and `trim_captured_text` components.

## Canonical artifact output

T004 adds the versioned JSONL artifact boundary. A build can be run directly
from the YAML composition above:

```console
python -m abrex corpus build docs/examples/corpus-fixture.yaml \
  --output data/processed/fixture.jsonl
```

The command writes a sibling manifest containing adapter/normalizer identity,
source and configuration fingerprints where available, deterministic record
counts, and all observed, repaired, dropped, ambiguous, and unscoreable
validation events. See `docs/canonical-artifacts.md` for the read/verify API.
