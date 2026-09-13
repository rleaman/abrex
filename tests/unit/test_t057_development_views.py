from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from abrex.literature.development_views import (
    build_development_views,
    relation_eligibility,
    validate_relation_evidence,
)
from abrex.literature.review import _ReviewerState
from abrex.literature.review_models import (
    AnnotationSubmission,
    CaseSubmission,
    DecisionSnapshot,
    PairDecision,
    ReviewSpan,
    apply_submission,
    empty_annotation_state,
)
from abrex.literature.review_packet import build_review_fixture
from abrex.literature.review_readiness import review_readiness


def _pair(**changes: object) -> PairDecision:
    values: dict[str, object] = {
        "decision_id": "decision-1",
        "suggestion_id": "suggestion-1",
        "status": "correct",
        "origin": "assisted",
        "short_form": ReviewSpan(start=6, end=8, text="LF"),
        "long_form": ReviewSpan(start=0, end=4, text="Long"),
        "relation_kind": "abbreviation_expansion",
        "evidence_structure": "contiguous_shared",
        "context_requirement": "text_alone",
    }
    values.update(changes)
    return PairDecision.model_validate(values)


def test_policy_keeps_strict_diagnostic_and_unresolved_distinct() -> None:
    assert relation_eligibility(_pair()).reason == "eligible_strict_exact_pair"
    assert (
        relation_eligibility(
            _pair(relation_kind="other_naming_or_code_relation")
        ).reason
        == "outside_strict_target"
    )
    assert (
        relation_eligibility(_pair(evidence_structure="discontinuous")).reason
        == "not_representable_as_exact_pair"
    )
    assert (
        relation_eligibility(_pair(relation_kind="uncertain")).disposition
        == "unresolved"
    )


def test_discontinuous_evidence_fragments_must_not_overlap() -> None:
    pair = _pair(
        evidence_structure="discontinuous",
        evidence_spans=(ReviewSpan(start=2, end=4, text="ng"),),
    )
    with pytest.raises(ValueError, match="long form overlaps evidence fragment"):
        validate_relation_evidence(pair)


def test_real_bundle_is_frozen_and_preserves_corrected_offsets(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = build_development_views(
        root / "evidence/T052/review-packet-v2.json",
        root / "evidence/T052/review-packet-v2.annotations.final.json",
        root / "evidence/T052/review-packet-v2.annotations.json",
        root / "evidence/T057/accepted-mechanical-corrections.json",
        root / "evidence/T053/inventory.json",
        root / "evidence/T053/audit-packet.json",
        root / "docs/annotation-guidelines/2026-09-12-development-supplement-v1.md",
        root / "docs/scientific-model/2026-09-12-development-challenge.md",
        tmp_path,
    )
    assert manifest["counts"]["cases"] == 60
    assert manifest["counts"]["challenge_cases"] == 20
    assert manifest["counts"]["relations"] == 111
    assert manifest["counts"]["strict_relations"] == 59
    assert manifest["status"] == "frozen"
    assert manifest["human_review"]["complete_cases"] == 20
    assert manifest["sources"]["accepted_mechanical_corrections"]["corrections"] == 6
    assert manifest["sources"]["packet"]["path"] == (
        "evidence/T052/review-packet-v2.json"
    )

    ledger = json.loads((tmp_path / "eligibility-ledger.json").read_text("utf-8"))
    packet = json.loads(
        (root / "evidence/T052/review-packet-v2.json").read_text("utf-8")
    )
    texts = {case["case_id"]: case["text"] for case in packet["cases"]}
    for case in ledger["cases"]:
        for relation in case["relations"]:
            for name in ("short_form", "long_form"):
                span = relation[name]
                if span:
                    assert (
                        texts[case["case_id"]][span["start"] : span["end"]]
                        == span["text"]
                    )
    corrected = {
        relation["decision_id"]: relation
        for case in ledger["cases"]
        for relation in case["relations"]
        if relation["mechanical_corrections"]
    }
    assert (
        corrected["added-0655bb72-246b-46c0-a8be-6fffc0a4094f"]["short_form"]["text"]
        == "HDL4-PL"
    )
    assert corrected["added-0e2feed1-410d-4488-acd6-6a350e31ff66"]["long_form"][
        "text"
    ].startswith("free cholesterol")
    assert len(corrected["decision-suggestion-82605f4667733c5a"]["evidence_spans"]) == 1
    assert corrected["decision-suggestion-09e5ad7e87e8434a"]["long_form"]["text"] == "2"
    assert (
        corrected["decision-suggestion-09e5ad7e87e8434a"]["evidence_spans"][0]["text"]
        == "phospholipids in large buoyant HDL subclasses"
    )
    assert (
        corrected["added-5a838721-3eb5-4e0f-babe-79c1a82ceb2e"]["long_form"]["text"]
        == "small dense HDL subclass 4"
    )
    unresolved_case = next(
        case
        for case in ledger["cases"]
        if "contains_unresolved_relation" in case["eligibility_reasons"]
    )
    assert unresolved_case["metric_eligible"] is False


def test_incomplete_passage_cannot_become_a_clean_negative(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "evidence/T052/review-packet-v2.annotations.json"
    state = json.loads(source.read_text("utf-8"))
    case_id = "case-26dd218284ba83169652"
    annotation = state["annotations"][case_id]
    annotation["current"]["missed_definition"] = "missed"
    annotation["history"][-1]["snapshot"]["missed_definition"] = "missed"
    incomplete_path = tmp_path / "incomplete-annotations.json"
    incomplete_path.write_text(json.dumps(state), encoding="utf-8")
    corrections = json.loads(
        (root / "evidence/T057/accepted-mechanical-corrections.json").read_text("utf-8")
    )
    corrections["source_annotations_sha256"] = hashlib.sha256(
        incomplete_path.read_bytes()
    ).hexdigest()
    corrections_path = tmp_path / "accepted-corrections.json"
    corrections_path.write_text(json.dumps(corrections), encoding="utf-8")

    build_development_views(
        root / "evidence/T052/review-packet-v2.json",
        root / "evidence/T052/review-packet-v2.annotations.final.json",
        incomplete_path,
        corrections_path,
        root / "evidence/T053/inventory.json",
        root / "evidence/T053/audit-packet.json",
        root / "docs/annotation-guidelines/2026-09-12-development-supplement-v1.md",
        root / "docs/scientific-model/2026-09-12-development-challenge.md",
        tmp_path / "bundle",
    )
    ledger = json.loads(
        (tmp_path / "bundle/eligibility-ledger.json").read_text("utf-8")
    )
    case = next(item for item in ledger["cases"] if item["case_id"] == case_id)
    assert case["metric_eligible"] is False
    assert "passage_search_incomplete" in case["eligibility_reasons"]


def test_acceptance_corrections_are_bound_to_annotation_content(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    corrections = json.loads(
        (root / "evidence/T057/accepted-mechanical-corrections.json").read_text("utf-8")
    )
    corrections["source_annotations_sha256"] = "0" * 64
    corrections_path = tmp_path / "stale-corrections.json"
    corrections_path.write_text(json.dumps(corrections), encoding="utf-8")

    with pytest.raises(ValueError, match="different adjudicated annotation file"):
        build_development_views(
            root / "evidence/T052/review-packet-v2.json",
            root / "evidence/T052/review-packet-v2.annotations.final.json",
            root / "evidence/T052/review-packet-v2.annotations.json",
            corrections_path,
            root / "evidence/T053/inventory.json",
            root / "evidence/T053/audit-packet.json",
            root / "docs/annotation-guidelines/2026-09-12-development-supplement-v1.md",
            root / "docs/scientific-model/2026-09-12-development-challenge.md",
            tmp_path / "bundle",
        )


def test_readiness_requires_all_policy_fields(tmp_path: Path) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    case = packet.cases[0]
    suggestion = case.suggestions[0]
    other_decisions = tuple(
        PairDecision(
            decision_id=f"decision-{item.suggestion_id}",
            suggestion_id=item.suggestion_id,
            status="incorrect",
            short_form=item.short_form,
            long_form=item.long_form,
        )
        for item in case.suggestions[1:]
    )
    incomplete = apply_submission(
        packet,
        empty_annotation_state(packet),
        AnnotationSubmission(
            packet_id=packet.packet_id,
            packet_content_sha256=packet.content_sha256,
            annotations={
                case.case_id: CaseSubmission(
                    expected_revision=0,
                    decision=DecisionSnapshot(
                        pairs=(
                            PairDecision(
                                decision_id=f"decision-{suggestion.suggestion_id}",
                                suggestion_id=suggestion.suggestion_id,
                                status="correct",
                                short_form=suggestion.short_form,
                                long_form=suggestion.long_form,
                            ),
                            *other_decisions,
                        ),
                        missed_definition="none",
                    ),
                )
            },
        ),
    )
    result = review_readiness(packet, incomplete, (case.case_id,))
    assert result.complete is False
    assert {issue.kind for issue in result.cases[0].issues} == {
        "relation_kind",
        "evidence_structure",
        "context_requirement",
    }

    pair = (
        incomplete.annotations[case.case_id]
        .current.pairs[0]
        .model_copy(
            update={
                "relation_kind": "abbreviation_expansion",
                "evidence_structure": "contiguous_shared",
                "context_requirement": "text_alone",
            }
        )
    )
    complete = apply_submission(
        packet,
        incomplete,
        AnnotationSubmission(
            packet_id=packet.packet_id,
            packet_content_sha256=packet.content_sha256,
            annotations={
                case.case_id: CaseSubmission(
                    expected_revision=1,
                    decision=DecisionSnapshot(
                        pairs=(pair, *other_decisions), missed_definition="none"
                    ),
                )
            },
        ),
    )
    assert review_readiness(packet, complete, (case.case_id,)).complete is True


def test_bounded_reviewer_exposes_only_required_cases(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    packet = build_review_fixture(packet_path)
    required = (packet.cases[1].case_id,)
    app = _ReviewerState(
        packet_path,
        required_case_ids=required,
        workflow_name="Finish T057",
    )
    payload = cast(dict[str, Any], app.packet_payload())
    assert [case["case_id"] for case in payload["cases"]] == list(required)
    assert payload["_workflow"]["name"] == "Finish T057"
    assert app.readiness_payload()["required_cases"] == 1
