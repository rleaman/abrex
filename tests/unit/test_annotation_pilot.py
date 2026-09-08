"""Auditable contemporary annotation-pilot workflow tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.corpora import (
    AdjudicationEvent,
    AnnotationCase,
    AnnotationLabel,
    AnnotationPilotConfig,
    AnnotationPilotError,
    AnnotationSpan,
    annotation_metadata_from_provenance,
    case_to_corpus_record,
    load_annotation_config,
    read_annotation_pilot,
    run_annotation_pilot,
    select_review_packet,
    write_annotation_pilot,
    write_canonical_annotation_artifact,
)
from abrex.corpora.serialization import read_canonical_jsonl


def _label(**overrides: object) -> AnnotationLabel:
    values: dict[str, object] = {
        "relation_id": "r1",
        "short_form": {"start": 11, "end": 13, "text": "LF"},
        "long_form": {"start": 0, "end": 9, "text": "long form"},
        "origin": "independent",
        "status": "accepted",
        "annotator_id": "ann",
    }
    values.update(overrides)
    return AnnotationLabel.model_validate(values)


def _case(**overrides: object) -> AnnotationCase:
    values: dict[str, object] = {
        "case_id": "case-1",
        "document_id": "doc-1",
        "article_group_id": "group-1",
        "role": "development",
        "text": "long form (LF) appears.",
        "guideline_version": "v1",
        "labels": (_label(),),
    }
    values.update(overrides)
    return AnnotationCase.model_validate(values)


def test_annotation_roundtrip_preserves_canonical_offsets_and_history(
    tmp_path: Path,
) -> None:
    history = AdjudicationEvent(
        event_id="e1", actor_id="ann", action="created", note="initial"
    )
    case = _case(labels=(_label(history=(history,)),))
    packet = tmp_path / "packet.json"
    fingerprint = write_annotation_pilot((case,), packet)
    assert read_annotation_pilot(packet) == (case,)
    output = tmp_path / "canonical.jsonl"
    output_fingerprint = write_canonical_annotation_artifact((case,), output)
    records = read_canonical_jsonl(output)
    assert records[0].document.text == case.text
    short_form = records[0].gold_annotations[0].short_form
    assert short_form is not None
    assert (short_form.start, short_form.end) == (11, 13)
    assert records[0].gold_annotations[0].provenance is not None
    provenance = records[0].gold_annotations[0].provenance
    assert provenance is not None
    metadata = annotation_metadata_from_provenance(provenance)
    assert metadata is not None
    assert metadata.relation_id == "r1"
    assert metadata.origin == "independent"
    assert metadata.status == "accepted"
    assert metadata.annotator_id == "ann"
    assert metadata.revision == 0
    assert metadata.history == (history,)
    assert metadata.article_group_id == "group-1"
    assert metadata.guideline_version == "v1"
    assert fingerprint != output_fingerprint


def test_annotation_report_separates_origins_unresolved_and_empty_cases() -> None:
    from abrex.corpora.annotation_pilot import annotation_report

    cases = (
        _case(),
        _case(
            case_id="assisted",
            document_id="doc-2",
            article_group_id="group-2",
            labels=(
                _label(
                    relation_id="r2",
                    origin="assisted",
                    suggestion_source="teacher",
                ),
            ),
        ),
        _case(
            case_id="unresolved",
            document_id="doc-3",
            article_group_id="group-3",
            labels=(
                _label(
                    relation_id="r3",
                    status="unresolved",
                    short_form=None,
                    long_form=None,
                    phenomenon_tags=("ambiguous", "table"),
                ),
            ),
        ),
        _case(
            case_id="empty",
            document_id="doc-4",
            article_group_id="group-4",
            labels=(),
            role="unlabeled_pilot",
        ),
    )
    report = annotation_report(cases)
    assert report["origin_counts"] == {"assisted": 1, "independent": 2}
    assert report["status_counts"] == {"accepted": 2, "unresolved": 1}
    assert report["empty_definition_case_count"] == 1
    assert report["claims_allowed"] is False


def test_review_packet_prioritizes_difficult_cases_deterministically() -> None:
    easy = _case(case_id="easy")
    difficult = _case(
        case_id="difficult",
        labels=(_label(status="unresolved", short_form=None, long_form=None),),
    )
    first = select_review_packet((easy, difficult), seed=4, max_cases=1)
    second = select_review_packet((easy, difficult), seed=4, max_cases=1)
    assert first == second == (difficult,)
    with pytest.raises(ValueError, match="positive"):
        select_review_packet((easy,), seed=1, max_cases=0)


def test_annotation_runner_writes_report_review_and_reads_config(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "packet.json"
    write_annotation_pilot((_case(),), input_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "annotation_pilot:\n"
        f"  input_path: {input_path}\n"
        f"  canonical_output: {tmp_path / 'canonical.jsonl'}\n"
        f"  report_output: {tmp_path / 'report.json'}\n"
        f"  review_packet_output: {tmp_path / 'review.json'}\n"
        "  review_packet_size: 1\n  seed: 2\n  guideline_version: v1\n",
        encoding="utf-8",
    )
    report = run_annotation_pilot(load_annotation_config(config_path))
    assert report["case_count"] == 1
    assert report["review_packet_case_count"] == 1
    assert (tmp_path / "canonical.jsonl").is_file()


def test_annotation_validation_and_import_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        AnnotationSpan(start=3, end=2)
    with pytest.raises(ValueError, match="empty values"):
        _label(phenomenon_tags=("",))
    with pytest.raises(ValueError, match="relation IDs"):
        _case(labels=(_label(relation_id=" "),))
    with pytest.raises(ValueError, match="suggestion source"):
        _label(origin="assisted")
    with pytest.raises(ValueError, match="independent labels"):
        _label(suggestion_source="resolver")
    with pytest.raises(ValueError, match="annotator_id"):
        _label(annotator_id=None)
    with pytest.raises(ValueError, match="resolver identity"):
        _case(role="evaluation", resolver_identity="ab3p")
    with pytest.raises(AnnotationPilotError, match="text mismatch"):
        case_to_corpus_record(
            _case(labels=(_label(short_form={"start": 11, "end": 13, "text": "XX"}),))
        )
    rejected = _label(status="rejected")
    assert case_to_corpus_record(_case(labels=(rejected,))).gold_annotations == ()
    with pytest.raises(AnnotationPilotError, match="unsupported"):
        path = tmp_path / "bad.json"
        path.write_text(
            json.dumps({"schema_version": "old", "cases": []}), encoding="utf-8"
        )
        read_annotation_pilot(path)
    with pytest.raises(AnnotationPilotError, match="Unable to read"):
        read_annotation_pilot(tmp_path / "missing.json")
    path.write_text(
        json.dumps({"schema_version": "contemporary-annotation-v1", "cases": "bad"}),
        encoding="utf-8",
    )
    with pytest.raises(AnnotationPilotError, match="array"):
        read_annotation_pilot(path)
    path.write_text(
        json.dumps(
            {
                "schema_version": "contemporary-annotation-v1",
                "cases": [{"case_id": "broken"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AnnotationPilotError, match="invalid annotation case"):
        read_annotation_pilot(path)
    config_path = tmp_path / "bad-config.yaml"
    config_path.write_text("other: true\n", encoding="utf-8")
    with pytest.raises(AnnotationPilotError, match="annotation_pilot"):
        load_annotation_config(config_path)
    mismatched = _case(guideline_version="v2")
    packet = tmp_path / "mismatched.json"
    write_annotation_pilot((mismatched,), packet)
    with pytest.raises(AnnotationPilotError, match="guideline version"):
        run_annotation_pilot(
            AnnotationPilotConfig(
                input_path=packet,
                canonical_output=tmp_path / "mismatched.jsonl",
                report_output=tmp_path / "mismatched-report.json",
                guideline_version="v1",
            )
        )
    with pytest.raises(AnnotationPilotError, match="unique"):
        path.write_text(
            json.dumps(
                {
                    "schema_version": "contemporary-annotation-v1",
                    "cases": [
                        _case().model_dump(mode="json"),
                        _case().model_dump(mode="json"),
                    ],
                }
            ),
            encoding="utf-8",
        )
        read_annotation_pilot(path)
