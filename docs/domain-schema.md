# Canonical Domain Schema

The `abrex.domain` package contains format-neutral scientific value objects.
It has no YAML, filesystem, subprocess, adapter, evaluator, or serialization
dependencies.

`TextSpan` uses Unicode Python string character offsets with half-open
intervals, `[start, end)`. Negative and reversed coordinates are invalid;
zero-length intervals are representable. `Document.validate_span` and
`Document.text_for` validate bounds against canonical document text. When an
annotation also stores captured text, `AbbreviationDefinition.validate_against`
checks that text against the document.

`AbbreviationDefinition` permits a missing short-form or long-form span and/or
captured text. This represents incomplete source data explicitly; the domain
model never infers a coordinate. `SourceTextSpan` preserves source-space
coordinates and text independently in `AnnotationProvenance`, including the
case where only one is available.

Resolver-only information belongs in `PredictionMetadata`, which is attached
through the separate `prediction` field. The optional `confidence` value is a
finite number in `[0, 1]`; arbitrary finite resolver scores use `score` and are
not interpreted by the domain model. Gold/source fields remain independent of
these prediction fields.

`CorpusRecord` groups one canonical `Document` with its gold definitions for
downstream evaluation. It does not define duplicate handling, partial-annotation
scoreability, matching, or other evaluation policy; those choices belong to
later named policies.
