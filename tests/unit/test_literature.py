"""Tests for the offline PubMed/PMC integration boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

import abrex.literature.jats as jats
from abrex.cli import main
from abrex.config import load_resolved_config
from abrex.domain import AbbreviationDefinition, PredictionMetadata, TextSpan
from abrex.literature import (
    Article,
    ArticleEntity,
    ArticleParseDiagnostic,
    ArticleParseError,
    ArticleSection,
    ArticleSerializationError,
    ArticleStructure,
    SectionDocumentSegmenter,
    WholeArticleSegmenter,
    article_from_dict,
    article_resolution_to_dict,
    article_to_dict,
    create_article_resolution_service,
    parse_bioc_json,
    parse_jats_xml,
    parse_pubmed_xml,
    read_article_json,
    read_bioc_json,
    read_jats_xml,
    read_pubmed_xml,
    serialize_article_resolution,
)
from abrex.resolvers import ResolverMetadata


def _article() -> Article:
    return Article(
        pmid="12345",
        pmcid="PMC12345",
        sections=(
            ArticleSection("abstract", "Background only."),
            ArticleSection("body", "Tumor necrosis factor (TNF) was measured."),
        ),
    )


def _config(tmp_path: Path, *, segmentation: dict[str, object]) -> Path:
    path = tmp_path / "article.yaml"
    path.write_text(
        """
resolver:
  type: toy
  params:
    confidence: 0.8
literature:
  segmentation:
    type: sections
    params: {}
""".replace("type: sections", f"type: {segmentation['type']}"),
        encoding="utf-8",
    )
    return path


def test_article_derives_stable_id_and_round_trips_local_json() -> None:
    article = _article()
    encoded = article_to_dict(article)
    assert encoded["article_id"] == "PMC12345"
    decoded = article_from_dict(
        {
            "id": "local-1",
            "pmid": "12345",
            "sections": [{"id": "s1", "text": "A"}],
        }
    )
    assert decoded.stable_id == "local-1"
    assert decoded.sections[0].section_id == "s1"
    assert decoded.sections[0].text == "A"


def test_article_rejects_missing_or_duplicate_source_sections() -> None:
    with pytest.raises(ValueError, match="at least one section"):
        Article(article_id="a")
    with pytest.raises(ValueError, match="section IDs must be unique"):
        Article(
            article_id="a",
            sections=(ArticleSection("s", "one"), ArticleSection("s", "two")),
        )
    with pytest.raises(ArticleSerializationError, match=r"sections\[0\]"):
        article_from_dict({"article_id": "a", "sections": [{"text": 1}]})


def test_segmenters_preserve_text_and_map_section_offsets() -> None:
    article = _article()
    section_documents = SectionDocumentSegmenter().segment(article)
    assert [item.document.document_id for item in section_documents] == [
        "PMC12345/section/abstract",
        "PMC12345/section/body",
    ]
    assert section_documents[1].document.text == article.sections[1].text
    assert section_documents[1].location_for_span(TextSpan(0, 5)) == (
        "body",
        TextSpan(0, 5),
    )

    whole = WholeArticleSegmenter(separator="|").segment(article)[0]
    assert (
        whole.document.text
        == "Background only.|Tumor necrosis factor (TNF) was measured."
    )
    assert whole.provenance.section_id is None
    assert whole.location_for_span(TextSpan(17, 22)) == ("body", TextSpan(0, 5))
    assert whole.location_for_span(TextSpan(16, 17)) is None


def test_segmenter_can_explicitly_exclude_empty_sections() -> None:
    article = Article(
        article_id="a",
        sections=(ArticleSection("empty", ""), ArticleSection("body", "text")),
    )
    result = SectionDocumentSegmenter(include_empty_sections=False).segment(article)
    assert [item.provenance.section_id for item in result] == ["body"]


def test_yaml_selected_resolver_runs_and_maps_article_provenance(
    tmp_path: Path,
) -> None:
    config = load_resolved_config(
        (_config(tmp_path, segmentation={"type": "sections"}),)
    )
    result = create_article_resolution_service(config).resolve(_article())
    assert result.article_id == "PMC12345"
    assert result.pmid == "12345"
    assert result.pmcid == "PMC12345"
    assert len(result.records) == 2
    assert len(result.entities) == 1
    entity = result.entities[0]
    assert entity.article_id == "PMC12345"
    assert entity.document_section_id == "body"
    assert entity.short_form_section_id == "body"
    assert entity.long_form_section_id == "body"
    assert entity.resolver.key == "toy"
    assert entity.resolver.version == "1"


def test_whole_article_mapping_exposes_cross_section_issue() -> None:
    source = WholeArticleSegmenter(separator="|").segment(_article())[0]
    prediction = AbbreviationDefinition(
        source.document.document_id,
        short_form=TextSpan(0, 20),
        long_form=TextSpan(0, 20),
        prediction=PredictionMetadata(confidence=0.5),
    )
    entity = ArticleEntity.from_prediction(
        source, prediction, ResolverMetadata("toy", "1")
    )
    assert entity.short_form_section_id is None
    assert "short_form_not_contained_in_one_section" in entity.mapping_issues


def test_local_article_io_and_cli_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    article_path = tmp_path / "article.json"
    article_path.write_text(json.dumps(article_to_dict(_article())), encoding="utf-8")
    assert read_article_json(article_path).stable_id == "PMC12345"
    output_path = tmp_path / "out.json"
    exit_code = main(
        [
            "article",
            "resolve",
            str(_config(tmp_path, segmentation={"type": "sections"})),
            "--input",
            str(article_path),
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == (
        "article-resolutions-v1"
    )
    assert json.loads(capsys.readouterr().out)["entity_count"] == 1


def test_cli_can_write_json_to_stdout_and_reports_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    article_path = tmp_path / "article.json"
    article_path.write_text(json.dumps(article_to_dict(_article())), encoding="utf-8")
    exit_code = main(
        [
            "article",
            "resolve",
            str(_config(tmp_path, segmentation={"type": "sections"})),
            "--input",
            str(article_path),
        ]
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["article"]["article_id"] == "PMC12345"

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ArticleSerializationError, match="root"):
        read_article_json(bad_path)


def test_serialized_resolution_contains_source_and_downstream_records(
    tmp_path: Path,
) -> None:
    config = load_resolved_config(
        (_config(tmp_path, segmentation={"type": "sections"}),)
    )
    result = create_article_resolution_service(config).resolve(_article())
    mapping = article_resolution_to_dict(result)
    assert mapping["schema_version"] == "article-resolutions-v1"
    records = cast(list[dict[str, object]], mapping["records"])
    assert records[1]["provenance"]
    assert records[1]["entities"]
    assert '"article-resolutions-v1"' in serialize_article_resolution(result)


def test_pubmed_parser_preserves_structured_abstract_inline_text_and_source_hash() -> (
    None
):
    payload = b"""<PubmedArticleSet>
      <PubmedArticle><MedlineCitation><PMID Version=\"2\">42</PMID><Article>
        <ArticleTitle>Alpha &amp; <i>beta</i></ArticleTitle><Abstract>
          <AbstractText Label=\"BACKGROUND\">A <b>bold</b> SF (AB).</AbstractText>
          <AbstractText Label=\"BACKGROUND\">Second.</AbstractText>
        </Abstract></Article></MedlineCitation><PubmedData><ArticleIdList>
          <ArticleId IdType=\"pmc\">PMC42</ArticleId>
        </ArticleIdList></PubmedData></PubmedArticle>
    </PubmedArticleSet>"""
    result = parse_pubmed_xml(payload)
    assert result.article.stable_id == "PMC42"
    assert result.article.title == "Alpha & beta"
    assert result.article.source_version == "2"
    assert result.article.source_sha256 is not None
    assert [section.section_id for section in result.article.sections] == [
        "background",
        "background-2",
    ]
    assert result.article.sections[0].text == "A bold SF (AB)."
    assert result.diagnostics[0].code == "duplicate-passage-id"
    with_title = parse_pubmed_xml(payload, include_title=True).article
    assert [section.section_id for section in with_title.sections] == [
        "title",
        "background",
        "background-2",
    ]
    triple = payload.replace(
        b"Second.",
        b'Second.</AbstractText><AbstractText Label="BACKGROUND">Third.',
    )
    assert parse_pubmed_xml(triple).article.sections[-1].section_id == "background-3"


def test_bioc_parser_preserves_passage_offsets_and_duplicate_diagnostics() -> None:
    payload = json.dumps(
        [
            {
                "source": "PubMed",
                "version": "1.0",
                "documents": [
                    {
                        "id": "42",
                        "infons": {"pmid": "42", "pmcid": "PMC42"},
                        "passages": [
                            {
                                "offset": 10,
                                "length": 5,
                                "text": "Title",
                                "infons": {"type": "title"},
                                "id": "p",
                            },
                            {
                                "offset": 15,
                                "length": 6,
                                "text": "A & B.",
                                "infons": {"section": "ABSTRACT"},
                                "id": "p",
                            },
                            {
                                "offset": 21,
                                "length": 0,
                                "text": "",
                                "infons": {},
                                "id": "empty",
                            },
                        ],
                    }
                ],
            }
        ]
    ).encode()
    result = parse_bioc_json(payload)
    assert result.article.source_coordinate_system == "bioc-character-offsets"
    assert result.article.title == "Title"
    assert len(result.article.sections) == 1
    section = result.article.sections[0]
    assert section.section_id == "p-2"
    assert section.source_id == "p"
    assert (section.source_offset, section.source_length) == (15, 6)
    assert {item.code for item in result.diagnostics} == {
        "duplicate-passage-id",
        "unsupported-passage",
    }
    with_title = parse_bioc_json(payload, include_title=True).article
    assert [item.section_id for item in with_title.sections] == ["p", "p-2"]


def test_source_readers_and_conversion_cli_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    xml = tmp_path / "article.xml"
    xml.write_text(
        "<PubmedArticle><MedlineCitation><PMID>7</PMID><Article><ArticleTitle>T</ArticleTitle><Abstract><AbstractText>TNF.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>",
        encoding="utf-8",
    )
    parsed = read_pubmed_xml(xml)
    article_json = tmp_path / "article.json"
    article_json.write_text(
        json.dumps(article_to_dict(parsed.article)), encoding="utf-8"
    )
    assert read_article_json(article_json).source_format == "pubmed-xml"
    result = main(["article", "convert", "--format", "pubmed-xml", "--input", str(xml)])
    assert result == 0
    assert json.loads(capsys.readouterr().out)["source_format"] == "pubmed-xml"

    bioc = tmp_path / "article.json.bioc"
    bioc.write_text(
        json.dumps({"documents": [{"id": "b", "passages": [{"text": "x"}]}]}),
        encoding="utf-8",
    )
    assert read_bioc_json(bioc).article.stable_id == "b"
    with pytest.raises(ArticleParseError, match="exactly one document"):
        parse_bioc_json('{"documents": []}')


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"not xml", "invalid PubMed XML"),
        (b"<PubmedArticle/>", "no PMID"),
        (
            b"<PubmedArticle><PMID>1</PMID><Abstract><AbstractText/></Abstract></PubmedArticle>",
            "no non-empty abstract",
        ),
    ],
)
def test_pubmed_parser_reports_malformed_or_empty_sources(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ArticleParseError, match=message):
        parse_pubmed_xml(payload)


def test_bioc_parser_reports_malformed_passages_and_missing_length() -> None:
    with pytest.raises(ArticleParseError, match="invalid BioC JSON"):
        parse_bioc_json("not json")
    with pytest.raises(ArticleParseError, match="no stable id"):
        parse_bioc_json('{"documents": [{"passages": [{"text": "x"}]}]}')
    with pytest.raises(ArticleParseError, match="passages must be an array"):
        parse_bioc_json('{"documents": [{"id": "x", "passages": null}]}')
    with pytest.raises(ArticleParseError, match="offset"):
        parse_bioc_json(
            '{"documents": [{"id": "x", "passages": [{"text": "x", "offset": -1}]}]}'
        )
    result = parse_bioc_json(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "x",
                        "passages": [None, {"text": "x", "offset": 0}],
                    }
                ]
            }
        )
    )
    assert result.article.sections[0].source_length == 1
    assert len(result.diagnostics) == 1
    with pytest.raises(ArticleParseError, match="no usable passages"):
        parse_bioc_json('{"documents": [{"id": "x", "passages": [{"text": ""}]}]}')


def test_article_source_metadata_and_section_coordinates_round_trip() -> None:
    article = Article(
        article_id="x",
        source_format="bioc-json",
        source_version="1",
        source_sha256="a" * 64,
        sections=(
            ArticleSection(
                "s", "text", source_id="p", source_offset=4, source_length=4
            ),
        ),
    )
    assert article_from_dict(article_to_dict(article)) == article
    with pytest.raises(ValueError, match="64-character"):
        Article(
            article_id="x", source_sha256="bad", sections=(ArticleSection("s", "x"),)
        )
    with pytest.raises(ValueError, match="source_id"):
        ArticleSection("s", "x", source_id="")
    with pytest.raises(ValueError, match="source_offset"):
        ArticleSection("s", "x", source_offset=-1)


def test_parser_fallback_and_missing_source_file(tmp_path: Path) -> None:
    result = parse_pubmed_xml(
        b"<Root><PMID>1</PMID><Abstract><AbstractText>text</AbstractText></Abstract></Root>"
    )
    assert result.article.pmid == "1"
    with pytest.raises(ArticleParseError, match="unable to read"):
        read_bioc_json(tmp_path / "missing.json")


def test_jats_parser_preserves_cells_captions_definitions_and_image_diagnostics(
    tmp_path: Path,
) -> None:
    payload = b"""<article article-version=\"1\"><front><article-meta>
      <article-id pub-id-type=\"pmc\">PMC7</article-id>
      <article-title>Alpha <italic>beta</italic></article-title>
    </article-meta></front>
    <abstract><p>Abstract text.</p></abstract>
    <body><sec><title>Body</title><p>TNF (TNF).</p>
      <table-wrap id=\"t1\"><caption><p>SF and LF</p></caption><table>
        <tr><th>SF</th><th>LF</th></tr>
        <tr><td rowspan=\"2\">AB</td><td>alpha beta</td></tr>
        <tr><td>gamma delta</td></tr></table>
        <table-wrap-foot><fn>Note.</fn></table-wrap-foot></table-wrap>
      <def-list><title>Terms</title><def-item><term>AB</term>
        <def><p>alpha beta</p></def></def-item></def-list>
      <fig id=\"f1\"><graphic href=\"figure.png\"/></fig>
    </sec></body></article>"""
    result = parse_jats_xml(payload)
    assert result.article.stable_id == "PMC7"
    assert result.article.title == "Alpha beta"
    assert result.article.source_version == "1"
    kinds = [structure.kind for structure in result.article.structures]
    assert "table" in kinds
    assert "caption" in kinds
    assert "table-header-cell" in kinds
    assert kinds.count("table-cell") == 3
    assert "table-footnote" in kinds
    assert "definition-list" in kinds
    assert "definition-term" in kinds
    assert "definition" in kinds
    assert "unsupported-image-asset" in kinds
    table_cell = next(
        item for item in result.article.structures if item.kind == "table-cell"
    )
    assert table_cell.parent_id == "table:article/body[1]/sec[1]/table-wrap[1]"
    assert ("rowspan", "2") in table_cell.attributes
    assert any(item.code == "unsupported-image-asset" for item in result.diagnostics)
    assert any(item.text == "alpha beta" for item in result.article.sections)
    assert article_from_dict(article_to_dict(result.article)) == result.article

    path = tmp_path / "article.xml"
    path.write_bytes(payload)
    assert read_jats_xml(path).article.source_sha256 == result.article.source_sha256
    with_title = parse_jats_xml(payload, include_title=True).article
    assert with_title.sections[0].section_id == "title"


def test_article_structure_validates_and_serializes() -> None:
    node = ArticleStructure("n", "caption", "text", "article/caption")
    assert node.parent_id is None
    with pytest.raises(ValueError, match="node_id"):
        ArticleStructure("", "caption", "text", "path")


def test_jats_parser_reports_invalid_ids_xml_and_table_grid(tmp_path: Path) -> None:
    with pytest.raises(ArticleParseError, match="invalid JATS XML"):
        parse_jats_xml("not xml")
    with pytest.raises(ArticleParseError, match="no stable id"):
        parse_jats_xml("<article><body><p>text</p></body></article>")
    with pytest.raises(ArticleParseError, match="no usable textual"):
        parse_jats_xml('<article id="x"><body><fig><graphic/></fig></body></article>')
    result = parse_jats_xml(
        '<article id="x"><body><table-wrap><caption>Caption</caption></table-wrap>'
        "</body></article>"
    )
    assert any(item.code == "unsupported-table" for item in result.diagnostics)
    with pytest.raises(ArticleParseError, match="unable to read"):
        read_jats_xml(tmp_path / "missing.xml")


def test_jats_duplicate_section_ids_are_disambiguated() -> None:
    diagnostics: list[ArticleParseDiagnostic] = []
    assert jats._unique("cell", {"cell", "cell-2"}, diagnostics) == "cell-3"
    assert diagnostics[0].code == "duplicate-section-id"
