"""Tests for the offline PubMed/PMC integration boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abrex.cli import main
from abrex.config import load_resolved_config
from abrex.domain import AbbreviationDefinition, PredictionMetadata, TextSpan
from abrex.literature import (
    Article,
    ArticleEntity,
    ArticleSection,
    ArticleSerializationError,
    SectionDocumentSegmenter,
    WholeArticleSegmenter,
    article_from_dict,
    article_resolution_to_dict,
    article_to_dict,
    create_article_resolution_service,
    read_article_json,
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
