# ADR-002: Preserve JATS structure beside canonical article text

Status: Accepted for T027

## Context

Tables, captions, definition lists and image references carry abbreviation
evidence that is lost when full text is flattened into paragraphs. The
existing `Article` contract is used by resolver segmentation and must remain
compatible with local JSON fixtures.

## Decision

Keep the existing textual `ArticleSection` stream and add an immutable
`ArticleStructure` stream to the same `Article`. JATS table cells, captions,
footnotes, definition terms and definitions receive stable source paths and
parent IDs; table cells also remain separate textual sections. Source XML
bytes are identified by the existing source SHA-256 and logical text remains
the canonical coordinate system. `local-article-v1` gains optional fields and
continues to read older documents with empty structures.

Titles remain metadata unless the caller explicitly requests title inclusion.
Image pixels are unsupported; an image-asset structure and diagnostic are
emitted, while textual captions remain available. No parser operation joins
cells or asserts an abbreviation pair.

## Consequences

Downstream candidate generators can use structure without reverse-engineering
flattened text, and source paths distinguish repeated cells. Consumers that
only need ordinary article text can ignore `structures`. Any future change to
canonical joins or source coordinate semantics requires a new schema/ADR.
