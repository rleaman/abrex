from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.run_t060_reviewer import readiness_report

from abrex.corpora import (
    build_dataset_manifest,
    fingerprint_records,
    write_canonical_jsonl,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    PredictionMetadata,
    TextSpan,
)
from abrex.literature.development_comparison import (
    _classify_predictions,
    materialize_development_comparison,
)
from abrex.literature.review_models import (
    ReviewCase,
    ReviewPacket,
    ReviewSelection,
    fingerprint,
    packet_identity_payload,
    validate_packet_identity,
)
from abrex.resolvers import (
    PredictionArtifact,
    PredictionRecord,
    ResolverMetadata,
    write_prediction_artifact,
)


def _prediction(
    *, short: tuple[int, int], long: tuple[int, int]
) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        document_id="document-1",
        short_form=TextSpan(*short),
        long_form=TextSpan(*long),
        short_form_text="SF",
        long_form_text="long form",
        prediction=PredictionMetadata(component="test", component_version="1"),
    )


def _artifact(name: str, *predictions: AbbreviationDefinition) -> PredictionArtifact:
    return PredictionArtifact(
        resolver=ResolverMetadata(name, "1"),
        records=(PredictionRecord("document-1", tuple(predictions)),),
    )


def test_prediction_linkage_deduplicates_review_proposals_across_methods() -> None:
    strict_key = ("document-1", 10, 12, 0, 9)
    known_key = ("document-1", 20, 22, 13, 19)
    novel = _prediction(short=(30, 32), long=(23, 29))
    queued, linkage = _classify_predictions(
        {
            "first": _artifact(
                "first",
                _prediction(short=(10, 12), long=(0, 9)),
                _prediction(short=(20, 22), long=(13, 19)),
                novel,
            ),
            "second": _artifact("second", novel),
        },
        {
            strict_key: {"status": "correct", "disposition": "strict"},
            known_key: {"status": "incorrect", "disposition": "diagnostic"},
        },
        {strict_key},
    )

    assert list(queued) == [("document-1", 30, 32, 23, 29)]
    assert [method for method, _ in next(iter(queued.values()))] == [
        "first",
        "second",
    ]
    assert linkage["method_counts"] == {
        "first": {
            "prior_incorrect": 1,
            "queued_for_review": 1,
            "strict_exact": 1,
        },
        "second": {"queued_for_review": 1},
    }


def test_frozen_t060_packet_is_valid_and_exhaustive() -> None:
    root = Path(__file__).parents[2]
    packet = ReviewPacket.model_validate_json(
        (root / "evidence/T060/review-packet-split-v2.json").read_text(encoding="utf-8")
    )
    comparison = json.loads(
        (root / "docs/artifacts/T060-development-comparison-split-v2.json").read_text(
            encoding="utf-8"
        )
    )

    validate_packet_identity(packet)
    suggestions = [item for case in packet.cases for item in case.suggestions]
    assert len(packet.cases) == 11
    assert len(suggestions) == 33
    assert len({item.suggestion_id for item in suggestions}) == 33
    assert comparison["assisted_review"]["exhaustive"] is True
    assert comparison["assisted_review"]["packet_id"] == packet.packet_id


def test_t061_readiness_check_starts_from_corrected_packet(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]

    complete, report = readiness_report(
        root / "evidence/T060/review-packet-split-v2.json",
        tmp_path / "t061.annotations.json",
    )

    assert complete is False
    assert "Progress: 0/11 passages complete" in report
    assert "44 required decisions remain" in report


def test_materializes_comparison_packet_and_manifest(tmp_path: Path) -> None:
    text = "long form (SF) and other term (OT)."
    document = Document("document-1", text)
    gold = AbbreviationDefinition(
        "document-1",
        short_form=TextSpan(11, 13),
        long_form=TextSpan(0, 9),
        short_form_text="SF",
        long_form_text="long form",
    )
    records = (CorpusRecord(document, (gold,)),)
    corpus = tmp_path / "evidence/T059/corpus.jsonl"
    corpus.parent.mkdir(parents=True)
    manifest_path = corpus.with_suffix(".manifest.json")
    write_canonical_jsonl(records, corpus)
    manifest = build_dataset_manifest(records, dataset_id="test-development")
    manifest_path.write_text(manifest.to_json(), encoding="utf-8", newline="\n")

    source_packet_path = tmp_path / "source-packet.json"
    source_case = ReviewCase(
        case_id="document-1",
        inventory_id="inventory-1",
        article_id="article-1",
        article_group_id="group-1",
        title="Test article",
        arm="pubmed_abstract",
        source_url="https://example.test/article-1",
        source_kind="abstract",
        section_id="abstract",
        section_heading="Abstract",
        category="diagnostic",
        inventory_category="test",
        canonical_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        passage_start=0,
        passage_end=len(text),
        text=text,
        selection_reason="test source case",
    )
    selection = ReviewSelection(
        targets={"cases": 1},
        denominators={"cases": 1},
        selected={"cases": 1},
        shortages={"cases": 0},
        arm_counts={"pubmed_abstract": 1},
        per_article_cap=1,
    )
    provisional = ReviewPacket(
        packet_id="pending",
        content_sha256="0" * 64,
        source_manifest_sha256="1" * 64,
        source_run_id="test-source",
        seed=1,
        cases=(source_case,),
        selection=selection,
    )
    packet_digest = fingerprint(packet_identity_payload(provisional))
    source_packet = provisional.model_copy(
        update={
            "packet_id": f"t052-{packet_digest[:20]}",
            "content_sha256": packet_digest,
        }
    )
    source_packet_path.write_text(
        source_packet.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    diagnostic_path = tmp_path / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "document-1",
                        "article_group_id": "group-1",
                        "relations": [
                            {
                                "status": "correct",
                                "disposition": "strict",
                                "short_form": {"start": 11, "end": 13},
                                "long_form": {"start": 0, "end": 9},
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    novel = AbbreviationDefinition(
        "document-1",
        short_form=TextSpan(31, 33),
        long_form=TextSpan(19, 29),
        short_form_text="OT",
        long_form_text="other term",
        provenance=AnnotationProvenance(
            adapter_identity="test-adapter", transformation_notes=("test",)
        ),
        prediction=PredictionMetadata(
            confidence=0.8,
            score=1.0,
            component="test",
            component_version="1",
            model_artifact_fingerprint="model-1",
        ),
    )
    prediction_paths: dict[str, Path] = {}
    dataset_fingerprint = fingerprint_records(records)
    for name, predictions in {
        "first": (gold, novel),
        "second": (novel,),
    }.items():
        path = tmp_path / f"{name}.jsonl"
        artifact = PredictionArtifact(
            ResolverMetadata(name, "1"),
            (PredictionRecord("document-1", predictions),),
            dataset_fingerprint=dataset_fingerprint,
        )
        write_prediction_artifact(artifact, path)
        prediction_paths[name] = path
    result_path = tmp_path / "first-result.json"
    result_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "elapsed_seconds": 1.25,
                "result_id": "result-1",
                "bundle_id": "bundle-1",
                "environment": {"python": "test"},
            }
        ),
        encoding="utf-8",
    )
    comparison_path = tmp_path / "comparison.json"
    review_path = tmp_path / "review.json"
    output_manifest = tmp_path / "t060-manifest.json"

    result = materialize_development_comparison(
        corpus_path=corpus,
        corpus_manifest_path=manifest_path,
        diagnostic_view_path=diagnostic_path,
        source_packet_path=source_packet_path,
        prediction_paths=prediction_paths,
        comparison_path=comparison_path,
        review_packet_path=review_path,
        evidence_manifest_path=output_manifest,
        job_result_paths={"first": result_path},
        seed=2,
        bootstrap_samples=2,
    )

    review = ReviewPacket.model_validate_json(review_path.read_text(encoding="utf-8"))
    validate_packet_identity(review)
    assert result["status"] == "review_and_plod_span_audit_pending"
    assert len(review.cases) == 1
    assert len(review.cases[0].suggestions) == 1
    assert review.cases[0].suggestions[0].method_ids == ("first", "second")
    assert comparison_path.is_file()
    assert output_manifest.is_file()
