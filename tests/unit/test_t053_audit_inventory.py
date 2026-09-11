"""Focused contracts for the T053 frozen-input audit inventory."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.audit_inventory import _current_decisions, _selection
from abrex.literature.review_models import (
    AnnotationSubmission,
    CaseSubmission,
    DecisionSnapshot,
    PairDecision,
    apply_submission,
    empty_annotation_state,
)
from abrex.literature.review_packet import build_review_fixture


def test_selection_deduplicates_cases_and_preserves_all_reasons(tmp_path: Path) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    case = packet.cases[0]
    suggestion = case.suggestions[0]
    state = apply_submission(
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
                                decision_id="corrected",
                                suggestion_id=suggestion.suggestion_id,
                                status="incorrect",
                                origin="corrected",
                                short_form=suggestion.short_form,
                                long_form=suggestion.long_form,
                            ),
                            PairDecision(
                                decision_id="added",
                                proposal_kind="span",
                                status="unsure",
                                origin="added",
                                short_form=suggestion.short_form,
                            ),
                        ),
                        missed_definition="none",
                    ),
                )
            },
        ),
    )
    selected, metadata = _selection(packet, state, 20260908)
    row = next(item for item in selected if item["case_id"] == case.case_id)
    assert row["selection_reasons"] == [
        "added_pair",
        "corrected_suggestion",
        "rejected_suggestion",
    ]
    assert metadata["targeted_case_count"] == 1


def test_current_decisions_excludes_revision_history(tmp_path: Path) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    case = packet.cases[0]
    suggestion = case.suggestions[0]
    submission = AnnotationSubmission(
        packet_id=packet.packet_id,
        packet_content_sha256=packet.content_sha256,
        annotations={
            case.case_id: CaseSubmission(
                expected_revision=0,
                decision=DecisionSnapshot(
                    pairs=(
                        PairDecision(
                            decision_id="first",
                            suggestion_id=suggestion.suggestion_id,
                            status="correct",
                            short_form=suggestion.short_form,
                            long_form=suggestion.long_form,
                        ),
                    ),
                    missed_definition="none",
                ),
            )
        },
    )
    state = apply_submission(packet, empty_annotation_state(packet), submission)
    updated = apply_submission(
        packet,
        state,
        submission.model_copy(
            update={
                "annotations": {
                    case.case_id: CaseSubmission(
                        expected_revision=1,
                        decision=DecisionSnapshot(
                            pairs=(
                                PairDecision(
                                    decision_id="second",
                                    suggestion_id=suggestion.suggestion_id,
                                    status="correct",
                                    origin="corrected",
                                    short_form=suggestion.short_form,
                                    long_form=suggestion.long_form,
                                ),
                            ),
                            missed_definition="none",
                        ),
                    )
                }
            }
        ),
    )
    decisions = _current_decisions(packet, updated)
    assert [item["decision_id"] for item in decisions] == ["second"]
