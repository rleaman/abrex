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

## Historical source formats (T011)

Historical adapters are offline readers: source files must be downloaded and
licensed by the user. `schwartz_hearst`,
`ab3p_corpus`, `medstract`, and `bioadi` read BioC XML or JSON. BioC
annotation locations are document character offsets; `ShortForm`/`LongForm`
entities are paired through BioC relation nodes, with deterministic fallback
pairing by entity order when no relations are present.

T019 makes the BioC choices explicit through three adapter parameters:

```yaml
params:
  pairing_policy: relations_or_order_fallback
  text_policy: preserve_source
  location_policy: first_location
```

`relations_or_order_fallback` is a named policy for the original BioC
benchmark exports only. It uses order pairing only when a document has no
relation nodes, and emits `BIOC_ORDER_FALLBACK_USED`. `relations_only` retains
unpaired source entities as partial annotations. Dangling or ambiguous
relation endpoints, duplicate source IDs, unequal fallback lists, unpaired
entities, invalid locations and discontinuous locations all emit structured
diagnostics; no endpoint or extra entity is silently discarded.

`preserve_source` is the default text policy. Annotation-captured text is
provenance, not an instruction to rewrite resolver input. The optional
`overlay_annotation_text` policy is restricted to equal-length overlays and
records `bioc_annotation_text_overlay` in record provenance, producing a
distinct canonical fingerprint. `first_location` is retained for the legacy
single-span domain model but reports every multi-location annotation and its
source locations; `reject_discontinuous` drops that annotation with a
diagnostic instead.

The reproducible real-source audit is run with:

```console
python scripts/audit_historical_corpora.py --output docs/artifacts/historical-corpus-audit.json
```

The report contains source SHA-256 values, raw source-unit counts, parsed and
canonical counts, diagnostic counts, semantic configuration and artifact
fingerprints. Raw and generated canonical data remain outside version control.

The BADREX-corrected Schwartz & Hearst and MEDSTRACT variants are unavailable
and are not registered. Follow the [settled availability decision](badrex-availability.md);
their absence does not require investigation during routine work.

`sdu_aaai21_ai` reads the shared-task JSON array format (`id`, `tokens`,
`labels`) and converts `B-long`/`I-long` and `B-short`/`I-short` labels into
spans in the configured token-separator representation. `sdu_aaai22_ae` reads
`text`, independent `acronyms` and `long-forms` span lists, and the official
uppercase source `ID`; its source coordinates are half-open. Each source span remains a
single-form canonical annotation, so no acronym/long-form pairing is inferred.
This contract follows the fields read and independently scored by the
[official SDU@AAAI-22 AE scorer](https://github.com/amirveyseh/AAAI-22-SDU-shared-task-1-AE/blob/main/scorer.py).
Use `exact_span` with `span_prf` when evaluating this source. No source files
or licensed examples are redistributed.
Any future corrected variants must use separate registry keys so they cannot
replace an original artifact.
