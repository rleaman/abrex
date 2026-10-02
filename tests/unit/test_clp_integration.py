"""Contract tests for the CellLiteraturePipeline integration boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.candidates.clp_table import CLPTableCandidateGenerator
from abrex.candidates.clp_worker import (
    CLPWorkerDocument,
    CLPWorkerDocumentResult,
    CLPWorkerPair,
    CLPWorkerProtocolError,
    CLPWorkerRequest,
    CLPWorkerResponse,
    map_clp_worker_response,
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
