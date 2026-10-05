"""Contract tests for the CellLiteraturePipeline integration boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.candidates.clp_table import CLPTableCandidateGenerator
from abrex.candidates.clp_worker import (
    CLPWorkerDocument,
    CLPWorkerDocumentResult,
    CLPWorkerDocumentResultV2,
    CLPWorkerDocumentV2,
    CLPWorkerPair,
    CLPWorkerPairV2,
    CLPWorkerPassageV2,
    CLPWorkerProtocolError,
    CLPWorkerRequest,
    CLPWorkerRequestV2,
    CLPWorkerResponse,
    CLPWorkerResponseV2,
    CLPWorkerSpanV2,
    map_clp_worker_response,
    map_clp_worker_response_v2,
)
from abrex.candidates.registry import GENERATORS
from abrex.config import load_resolved_config
from abrex.corpora.adapters.clp_snapshot import (
    CLPAbbreviationSnapshotAdapter,
    export_clp_snapshot,
)
from abrex.corpora.base import CorpusPipeline, SourceResource
from abrex.corpora.config import corpus_config_from_resolved
from abrex.corpora.registry import CORPUS_ADAPTERS
from abrex.domain import Document, TextSpan
from abrex.literature.models import (
    ArticleDocument,
    ArticleDocumentProvenance,
    ArticleStructure,
)


def test_tracked_clp_snapshot_is_loadable_and_reports_unscorable_pairs() -> None:
    source = Path("resources/clp/abbr-v5-validation-v1.jsonl")
    result = CorpusPipeline(CLPAbbreviationSnapshotAdapter()).build(
        SourceResource("clp-v5.1", source, "clp-abbr-snapshot-v1")
    )

    assert len(result.records) == 200
    assert sum(len(record.gold_annotations) for record in result.records) == 3696
    assert result.source_annotation_count == 3696
    assert (
        sum(
            item.code == "CLP_PAIR_UNSCORABLE"
            for item in result.diagnostics.diagnostics
        )
        == 339
    )
    for record in result.records:
        for annotation in record.gold_annotations:
            record.document.validate_definition(annotation)


def test_clp_registry_keys_are_public_and_stable() -> None:
    assert CORPUS_ADAPTERS.get_entry("clp_abbr_snapshot_v1").key == (
        "clp_abbr_snapshot_v1"
    )
    assert GENERATORS.get_entry("clp_table_v5_1").key == "clp_table_v5_1"


def test_clp_development_config_declares_tracked_derivative() -> None:
    resolved = load_resolved_config(
        (Path("configs/development/clp-abbr-v5-validation.yaml"),)
    )
    config = corpus_config_from_resolved(resolved)

    assert config.adapter.type == "clp_abbr_snapshot_v1"
    assert config.semantics is not None
    assert config.semantics.source_status == "tracked_canonical_derivative"


def test_snapshot_export_never_guesses_repeated_occurrences(tmp_path: Path) -> None:
    items = [
        {
            "id": "section-1",
            "source": {
                "filename": "source.xml.gz",
                "document_id": "doc-1",
                "start_index": 1,
            },
            "selection_tags": ["test"],
            "document_context": {
                "passages": [
                    {
                        "index": 1,
                        "offset": 0,
                        "section_type": "ABBR",
                        "type": "paragraph",
                        "text": "ABC, alpha beta complex; ABC repeated",
                    }
                ],
                "annotated_passage_indexes": [1],
            },
        }
    ]
    annotations = {
        "annotations": {
            "section-1": {
                "done": True,
                "section_decision": "valid_abbreviation_section",
                "pairs": [
                    {
                        "short_form": "ABC",
                        "long_form": "alpha beta complex",
                        "source_passage_indexes": [1],
                        "source_first": "ABC",
                        "source_second": "alpha beta complex",
                        "orientation": "FIRST_IS_SF",
                    }
                ],
            }
        }
    }
    items_path = tmp_path / "items.json"
    annotations_path = tmp_path / "annotations.json"
    items_path.write_text(json.dumps(items), encoding="utf-8")
    annotations_path.write_text(json.dumps(annotations), encoding="utf-8")

    manifest = export_clp_snapshot(
        items_path=items_path,
        annotations_path=annotations_path,
        output_path=tmp_path / "snapshot.jsonl",
        manifest_path=tmp_path / "manifest.json",
        source_commit="a" * 40,
    )
    row = json.loads((tmp_path / "snapshot.jsonl").read_text("utf-8"))

    assert manifest["counts"] == {
        "sections": 1,
        "positive_sections": 1,
        "negative_sections": 0,
        "mapped_pairs": 0,
        "unscorable_pairs": 1,
    }
    assert row["annotations"][0]["short_span"] is None
    assert row["annotations"][0]["mapping_status"] == (
        "ambiguous_or_missing_short_form"
    )


def test_snapshot_export_repairs_legacy_section_saved_in_source_order(
    tmp_path: Path,
) -> None:
    items = [
        {
            "id": "section-reversed",
            "source": {
                "filename": "source.xml.gz",
                "document_id": "doc-1",
                "start_index": 1,
            },
            "selection_tags": ["test"],
            "document_context": {
                "passages": [
                    {
                        "index": 1,
                        "offset": 0,
                        "section_type": "ABBR",
                        "type": "paragraph",
                        "text": "alpha synuclein SYN; fetal bovine serum FBS",
                    }
                ],
                "annotated_passage_indexes": [1],
            },
        }
    ]
    annotations = {
        "annotations": {
            "section-reversed": {
                "done": True,
                "section_decision": "valid_abbreviation_section",
                "orientation": "SECOND_IS_SF",
                "pairs": [
                    {
                        "short_form": "alpha synuclein",
                        "long_form": "SYN",
                        "source_passage_indexes": [1],
                        "source_first": "alpha synuclein",
                        "source_second": "SYN",
                        "orientation": "SECOND_IS_SF",
                    },
                    {
                        "short_form": "fetal bovine serum",
                        "long_form": "FBS",
                        "source_passage_indexes": [1],
                        "source_first": "fetal bovine serum",
                        "source_second": "FBS",
                        "orientation": "SECOND_IS_SF",
                    },
                ],
            }
        }
    }
    items_path = tmp_path / "items.json"
    annotations_path = tmp_path / "annotations.json"
    items_path.write_text(json.dumps(items), encoding="utf-8")
    annotations_path.write_text(json.dumps(annotations), encoding="utf-8")

    manifest = export_clp_snapshot(
        items_path=items_path,
        annotations_path=annotations_path,
        output_path=tmp_path / "snapshot.jsonl",
        manifest_path=tmp_path / "manifest.json",
        source_commit="a" * 40,
    )
    row = json.loads((tmp_path / "snapshot.jsonl").read_text("utf-8"))

    counts = manifest["counts"]
    assert isinstance(counts, dict)
    assert counts["semantic_orientation_repairs"] == 2
    assert row["annotations"][0]["short_form"] == "SYN"
    assert row["annotations"][0]["long_form"] == "alpha synuclein"
    assert row["annotations"][0]["semantic_orientation_repair"] is True


def test_clp_table_generator_maps_only_unique_two_column_rows() -> None:
    document = Document(
        "table-1",
        "ABC\talpha beta complex\nXYZ\txylophone yield zone",
    )

    result = CLPTableCandidateGenerator().generate(document)

    assert len(result.candidates) == 2
    pairs = {
        (
            document.text_for(candidate.short_form),
            document.text_for(candidate.long_form),
        )
        for candidate in result.candidates
    }
    assert pairs == {
        ("ABC", "alpha beta complex"),
        ("XYZ", "xylophone yield zone"),
    }


def test_clp_table_generator_uses_jats_row_identity() -> None:
    document = Document("article-1", "ABC means alpha beta complex")
    article = ArticleDocument(
        document,
        ArticleDocumentProvenance(
            "article-1", None, None, None, "whole", None, None, None, ()
        ),
        (),
        (
            ArticleStructure(
                "cell-1",
                "table-cell",
                "ABC",
                "article/table/tr[1]/td[1]",
                "table-1",
            ),
            ArticleStructure(
                "cell-2",
                "table-cell",
                "alpha beta complex",
                "article/table/tr[1]/td[2]",
                "table-1",
            ),
        ),
    )

    result = CLPTableCandidateGenerator().generate_article(article)

    assert len(result.candidates) == 1
    assert result.candidates[0].short_form == TextSpan(0, 3)
    assert result.candidates[0].long_form == TextSpan(10, 28)


def test_clp_worker_protocol_maps_only_unique_accepted_source_text() -> None:
    request = CLPWorkerRequest(
        request_id="request-1",
        documents=(
            CLPWorkerDocument(
                document_id="d1",
                text="Tumor necrosis factor (TNF). TNF was measured.",
            ),
        ),
    )
    response = CLPWorkerResponse(
        request_id="request-1",
        worker_identity="CellLiteraturePipeline/table-parser",
        worker_version="5.1",
        documents=(
            CLPWorkerDocumentResult(
                document_id="d1",
                pairs=(
                    CLPWorkerPair(
                        pair_id="p1",
                        decision="accepted",
                        short_form="TNF",
                        long_form="Tumor necrosis factor",
                        rule="two_column",
                    ),
                    CLPWorkerPair(
                        pair_id="p2",
                        decision="rejected",
                        short_form="TNF",
                        long_form="Tumor necrosis factor",
                        rule="header",
                    ),
                ),
            ),
        ),
    )

    result = map_clp_worker_response(request, response)[0]

    assert result.candidates == ()
    assert {item.code for item in result.diagnostics} == {
        "clp_worker_ambiguous_mapping",
        "clp_worker_rejected",
    }
    assert "gold" not in request.model_dump_json()


def test_clp_worker_protocol_preserves_provenance_and_rejects_mismatches() -> None:
    request = CLPWorkerRequest(
        request_id="request-2",
        documents=(CLPWorkerDocument(document_id="d1", text="Alpha factor (AF)"),),
    )
    response = CLPWorkerResponse(
        request_id="request-2",
        worker_identity="clp",
        worker_version="5.1",
        documents=(
            CLPWorkerDocumentResult(
                document_id="d1",
                pairs=(
                    CLPWorkerPair(
                        pair_id="p1",
                        decision="accepted",
                        short_form="AF",
                        long_form="Alpha factor",
                        rule="two_column",
                    ),
                ),
            ),
        ),
    )

    candidate = map_clp_worker_response(request, response)[0].candidates[0]

    assert candidate.provenance is not None
    assert candidate.provenance.adapter_identity == "clp_worker_v1"
    assert candidate.provenance.adapter_version == "5.1"
    mismatch = response.model_copy(update={"request_id": "different"})
    with pytest.raises(CLPWorkerProtocolError, match="request_id"):
        map_clp_worker_response(request, mismatch)

    missing = response.model_copy(update={"documents": ()})
    with pytest.raises(CLPWorkerProtocolError, match="document IDs"):
        map_clp_worker_response(request, missing)


def test_clp_worker_protocol_rejects_duplicate_identities() -> None:
    document = CLPWorkerDocument(document_id="d1", text="text")
    with pytest.raises(ValueError, match="document IDs"):
        CLPWorkerRequest(request_id="r", documents=(document, document))

    pair = CLPWorkerPair(
        pair_id="p1",
        decision="unscorable",
        short_form="A",
        long_form="Alpha",
        rule="rule",
    )
    with pytest.raises(ValueError, match="pair IDs"):
        CLPWorkerDocumentResult(document_id="d1", pairs=(pair, pair))

    result = CLPWorkerDocumentResult(document_id="d1", pairs=(pair,))
    with pytest.raises(ValueError, match="document IDs"):
        CLPWorkerResponse(
            request_id="r",
            worker_identity="clp",
            worker_version="5.1",
            documents=(result, result),
        )


def test_clp_worker_v2_preserves_structure_and_explicit_occurrences() -> None:
    request = CLPWorkerRequestV2(
        request_id="request-v2",
        documents=(
            CLPWorkerDocumentV2(
                document_id="d1",
                source_filename="source.xml.gz",
                start_position=0,
                text="Abbreviations\nABC\talpha beta complex",
                passages=(
                    CLPWorkerPassageV2(
                        position=0,
                        source_index=4,
                        canonical_start=0,
                        source_offset=10,
                        section_type="ABBR",
                        passage_type="title",
                        text="Abbreviations",
                    ),
                    CLPWorkerPassageV2(
                        position=1,
                        source_index=5,
                        canonical_start=14,
                        source_offset=24,
                        section_type="TABLE",
                        passage_type="table",
                        text="ABC\talpha beta complex",
                        xml=(
                            "<table><tr><td>ABC</td>"
                            "<td>alpha beta complex</td></tr></table>"
                        ),
                    ),
                ),
            ),
        ),
    )
    response = CLPWorkerResponseV2(
        request_id="request-v2",
        worker_identity="CellLiteraturePipeline/full-clp",
        worker_version="323fd4f",
        policy_version="abbr-section-choice-v5.1",
        model_version="jev-1.13.0",
        documents=(
            CLPWorkerDocumentResultV2(
                document_id="d1",
                disposition="ACCEPTED",
                decision_source="DETERMINISTIC",
                pairs=(
                    CLPWorkerPairV2(
                        pair_id="pair-1",
                        decision="accepted",
                        short_form="ABC",
                        long_form="alpha beta complex",
                        short_span=CLPWorkerSpanV2(start=14, end=17),
                        long_span=CLPWorkerSpanV2(start=18, end=36),
                        rule="PATTERN_3:TWO_COLUMN_TABLE",
                        orientation="FIRST_IS_SF",
                        source_passage_indexes=(5,),
                        mapping_status="mapped",
                    ),
                ),
            ),
        ),
    )

    result = map_clp_worker_response_v2(request, response)[0]

    assert len(result.candidates) == 1
    assert result.candidates[0].short_form == TextSpan(14, 17)
    assert result.candidates[0].long_form == TextSpan(18, 36)
    assert result.candidates[0].provenance is not None
    assert result.candidates[0].provenance.adapter_identity == "clp_worker_v2"


def test_clp_worker_v2_rejects_span_text_mismatch() -> None:
    request = CLPWorkerRequestV2(
        request_id="request-v2",
        documents=(
            CLPWorkerDocumentV2(
                document_id="d1",
                source_filename="source.xml.gz",
                start_position=0,
                text="ABC alpha",
                passages=(
                    CLPWorkerPassageV2(
                        position=0,
                        source_index=0,
                        canonical_start=0,
                        source_offset=0,
                        section_type="ABBR",
                        passage_type="title",
                        text="ABC alpha",
                    ),
                ),
            ),
        ),
    )
    response = CLPWorkerResponseV2(
        request_id="request-v2",
        worker_identity="clp",
        worker_version="323fd4f",
        policy_version="v5.1",
        model_version="jev-1.13.0",
        documents=(
            CLPWorkerDocumentResultV2(
                document_id="d1",
                disposition="ACCEPTED",
                decision_source="DETERMINISTIC",
                pairs=(
                    CLPWorkerPairV2(
                        pair_id="bad",
                        decision="accepted",
                        short_form="XYZ",
                        long_form="alpha",
                        short_span=CLPWorkerSpanV2(start=0, end=3),
                        long_span=CLPWorkerSpanV2(start=4, end=9),
                        rule="test",
                        orientation="FIRST_IS_SF",
                        source_passage_indexes=(0,),
                        mapping_status="mapped",
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(CLPWorkerProtocolError, match="spans do not match"):
        map_clp_worker_response_v2(request, response)
