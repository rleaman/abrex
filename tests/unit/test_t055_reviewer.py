"""Regression coverage for the additive T055 reviewer contract."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.review_models import (
    DecisionSnapshot,
    PairDecision,
    ReviewSpan,
    validate_snapshot,
)
from abrex.literature.review_packet import build_review_fixture
from abrex.literature.reviewer_ui import REVIEWER_HTML


def test_t055_ui_exposes_bounded_assisted_review_controls() -> None:
    for text in (
        "Passage to review",
        "Assisted review",
        "Supported",
        "Unsupported",
        "Not sure",
        "Add evidence fragment",
        "Interpretation — not a quotation",
        "Search this whole passage for additional definitions.",
        "Technical details",
        "Import JSON",
    ):
        assert text in REVIEWER_HTML


def test_t055_additive_fields_round_trip_and_validate_exact_fragments(
    tmp_path: Path,
) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    case = packet.cases[0]
    sf_start = case.text.index("TNF", case.text.index("Tumor necrosis factor"))
    lf_start = case.text.index("Tumor necrosis factor")
    decision = PairDecision(
        decision_id="added-relation",
        proposal_kind="definition",
        status="unsure",
        origin="added",
        short_form=ReviewSpan(start=sf_start, end=sf_start + 3, text="TNF"),
        long_form=ReviewSpan(
            start=lf_start, end=lf_start + 21, text="Tumor necrosis factor"
        ),
        relation_kind="abbreviation_expansion",
        evidence_structure="discontinuous",
        context_requirement="document_structure",
        evidence_spans=(
            ReviewSpan(start=lf_start, end=lf_start + 5, text="Tumor"),
            ReviewSpan(start=lf_start + 6, end=lf_start + 21, text="necrosis factor"),
        ),
        interpretation="Tumor necrosis factor",
        source_error=False,
    )
    validate_snapshot(case, DecisionSnapshot(pairs=(decision,)))
    assert decision.evidence_spans[1].text == "necrosis factor"
