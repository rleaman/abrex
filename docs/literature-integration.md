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

