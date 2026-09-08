# T026 completion: PubMed and BioC source parsing

Status: Complete for the local parser and bounded live round-trip scope.

## Delivered

- Extended `Article` and `ArticleSection` with source format/version/hash,
  coordinate-system, source passage ID and source offset metadata while
  retaining backward-compatible local JSON serialization.
- Added strict offline `read_pubmed_xml`/`parse_pubmed_xml` and
  `read_bioc_json`/`parse_bioc_json` adapters with explicit diagnostics for
  duplicate IDs and unsupported/empty passages.
- Added an `article convert` CLI command for local PubMed XML or BioC JSON to
  the existing article interchange format. Networking is not imported by the
  readers.
- Added synthetic coverage for structured abstracts, nonzero BioC offsets,
  Unicode/entity and inline-markup text, title inclusion, duplicate IDs,
  malformed passages and source metadata round trips.

## Verification and evidence

The acquired two-PMID XML response was parsed as PMID `12603049` with one
abstract section, zero diagnostics and the retained source hash
`0734a0d3a1680cd121dfd1bcbdc0cec81d8ed645d95603b34b9d91316fad8ac8`. One
bounded live BioC response for the same PMID was parsed as one article with
one passage section and zero diagnostics; it flowed through the existing
`ArticleResolutionService` as one canonical record. BioC response hash:
`3236efdc9e937e3fc4d12b87c92ecfba4a6d3cc59066554dccfb15922cf450ad8`.
The small evidence report is [T026-literature-parser-pilot-report.json](../../artifacts/T026-literature-parser-pilot-report.json).

The repository fast gate passed with 203 unit/contract tests. The full suite
passed 207 tests with 95.04% coverage; Ruff, formatting and strict mypy also
passed.

## Decisions and limitations

The parser preserves original source bytes through a SHA-256 hash but exposes
logical text coordinates after XML entity/inline-markup decoding. PubMed
titles remain metadata unless `include_title` is explicitly selected. BioC
passage coordinates are retained under the declared BioC character-offset
coordinate system. No claim is made that every source passage is
redistributable, and no JATS table/caption semantics are flattened here.

Next dependency-ready task: T027, JATS tables, captions and definition lists.
