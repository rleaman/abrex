# T027 completion: JATS tables, captions and definition lists

Status: Complete for structural preservation and bounded validation.

## Delivered

- Added immutable `ArticleStructure` values and backward-compatible local
  article JSON serialization for structural metadata.
- Added an offline `parse_jats_xml`/`read_jats_xml` adapter that preserves
  source paths, parent membership, cell attributes such as `rowspan` and
  `colspan`, repeated-cell identity, captions, table footnotes, definition
  lists, terms/definitions and image-asset diagnostics.
- Kept table cells as separate `ArticleSection` values so canonical text
  mapping identifies the source cell and no cross-cell pair is invented.
- Added [ADR-002](../../decisions/ADR-002-jats-structure-alongside-article-text.md),
  literature documentation and synthetic parser/serialization coverage.

## Verification and evidence

The bounded real PMC EFetch pilot used `PMC4051513`. The 49,080-byte JATS
response had 3 table wraps and 3 figure assets; parsing yielded 137 textual
sections and 124 structures, with 3 explicit unsupported-image diagnostics.
The source SHA-256 is
`2030e0547ed486539e8a666db063070a65180740e9807fff8171a1756917e301`.
The small evidence report is [T027-jats-parser-pilot-report.json](../../artifacts/T027-jats-parser-pilot-report.json).

The synthetic fixture verified 3 table cells, 2 header cells, caption and
footnote provenance, one definition list with term/definition membership,
`rowspan` preservation, repeated-cell distinction and zero cross-cell pair
invention. The repository fast gate passed with 207 unit/contract tests; the
full suite passed 211 tests at 95.06% coverage. Ruff, formatting, strict mypy
and `git diff --check` passed.

## Decisions and limitations

JATS XML is decoded into logical text while the source byte hash is retained.
Table structures remain alongside text rather than being flattened into one
candidate stream. Figure pixels are not interpreted; image references are
reported explicitly and captions are retained. The real pilot did not contain
a definition list, so that path remains synthetic evidence pending a source
with that structure. OCR, table-pair acceptance and scientific sampling are
future tasks.

Next ready task: T028, lexical resource ingestion. T029 remains blocked until
its T027 dependency is accepted in the task graph and will remain
scientifically provisional until its sampling frame is reviewed.
