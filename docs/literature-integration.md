# Local PMC/PubMed article integration

T016 adds `abrex.literature`, an offline adapter boundary for article data
that has already been retrieved. It does not import NCBI clients, make HTTP
requests, parse remote responses, or change the resolver/evaluator contracts.

## Local article representation

The checked-in interchange shape is JSON with article identifiers and source
sections:

```json
{
  "article_id": "local-pmc-1",
  "pmid": "12345",
  "pmcid": "PMC12345",
  "title": "Synthetic article",
  "sections": [
    {"section_id": "abstract", "title": "Abstract", "text": "..."},
    {"section_id": "body", "title": "Body", "text": "..."}
  ]
}
```

`article_id` is preferred for canonical document identity. If it is absent,
the PMCID and then PMID is used deterministically. Section IDs must be unique;
when reading local JSON, a missing section ID is represented as
`section-{index}`. Source text is passed unchanged to the resolver.

## Segmentation and resolution

Segmentation is a registry-backed choice in the `literature` YAML section:

```yaml
resolver:
  type: toy
  params: {}

literature:
  segmentation:
    type: sections
    params:
      include_empty_sections: true
```

The `sections` policy creates one canonical `Document` per source section.
The `article` policy creates one document by joining sections with its
configured `separator` (default `"\\n\\n"`). The joined document records
the canonical interval of every source section. It does not insert section
titles. These policies are explicit because segmentation and separator
choices affect resolver offsets and downstream scientific interpretation.

Run one local article without network access:

```console
python -m abrex article resolve docs/examples/article-resolution.yaml \
  --input docs/examples/local-article.json \
  --output data/article-resolution.json
```

The output is `article-resolutions-v1`. Each record contains the canonical
document, article/section provenance, the ordinary T005 prediction record,
and `ArticleEntity` values for downstream entity-linking consumers. Canonical
spans remain present. Section-local spans are populated only when a span is
fully contained in exactly one source section; spans in separators or across
section boundaries are retained with a `mapping_issues` diagnostic rather than
being assigned silently.

Embedding applications can use `create_article_resolution_service` with an
injected resolver or segmenter registry. `read_article_json` is only a local
file adapter; retrieval and licensing remain application responsibilities.

T043 adds `resolve_and_link_mentions`, which composes that selected resolver
with the explicit `MentionLinkConfig` policy. Links retain mention spans,
chosen definition references, scope, status and evidence. Nearest-preceding,
article-scope and section-scope behavior, redefinitions, conflicts, before-
definition mentions, case/plural handling and undefined forms remain explicit;
the linker never invents a definition or changes article text.

## Bounded PubMed acquisition

T025 adds a narrow application adapter for a fixed list of PubMed IDs. It uses
NCBI EFetch and writes raw XML responses separately from the later offline
parsers. The checked-in [pilot configuration](../configs/literature/T025-pubmed-pilot.yaml)
contains two IDs and is an example, not an instruction to download a corpus:

```console
python -m abrex literature acquire configs/literature/T025-pubmed-pilot.yaml --dry-run
python -m abrex literature acquire configs/literature/T025-pubmed-pilot.yaml
python -m abrex literature replay .artifacts/T025/pubmed-pilot/manifest.json
```

The manifest pins the identifier list, request URLs, retrieval time, raw-file
hashes, access metadata and missing/failed/partial counts. A rerun reuses a
matching raw request after verifying its hash. Interrupted writes remain in a
`.part` file and are never presented as a successful response.

NCBI's current E-utilities guidance requires requests to use the E-utilities
host, stay within the published request-rate limits, and identify distributed
software with registered `tool` and `email` values; an API key is optional for
this bounded pilot and is read only from the configured environment variable.
See the [NCBI E-utilities guidance](https://www.ncbi.nlm.nih.gov/books/NBK25497/)
and [NCBI policies](https://www.ncbi.nlm.nih.gov/home/about/policies/). Article
reuse and redistribution remain source-specific decisions; acquisition does
not assert a license for downstream publication.

## JATS structure

T027 adds `parse_jats_xml` and `read_jats_xml`. The parser keeps textual
sections and a separate `Article.structures` stream. Table wraps, captions,
headers, cells, footnotes, definition lists and terms/definitions carry stable
source paths and parent IDs. Each table cell is also an independent section;
the parser never joins cells or accepts a pair. Image assets produce an
`unsupported-image-asset` structure and diagnostic; caption text remains
available, but figure pixels are not parsed.

The structure extension and its compatibility policy are recorded in
[ADR-002](decisions/ADR-002-jats-structure-alongside-article-text.md).

