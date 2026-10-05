"""Prediction-isolation, persistence, uncertainty, and locking tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abrex.literature.blind_review import (
    BlindReviewCase,
    create_blind_packet,
    read_blind_packet,
    write_blind_packet,
)
from abrex.literature.blind_reviewer_ui import BLIND_REVIEWER_HTML
from abrex.literature.review import _ReviewerState
from abrex.literature.review_models import ReviewError


def _packet(path: Path) -> Path:
    text = "🧬 Tumor necrosis factor (TNF) differs from TNF elsewhere."
    case = BlindReviewCase(
        case_id="blind-1",
        article_id="article-1",
        article_group_id="group-1",
        title="Source title",
        arm="pmc_cc_by",
        source_url="https://example.invalid/article-1",
        source_kind="table",
        section_id="table-1",
        section_heading="Abbreviations",
        canonical_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        passage_start=0,
        passage_end=len(text),
        text=text,
        structures=(),
    )
    write_blind_packet(
        create_blind_packet((case,), protocol_id="fixture-v1", seed=20261002), path
    )
    return path


def _complete_zero_submission(app: _ReviewerState) -> bytes:
    return json.dumps(
        {
            "schema_version": "t052-annotation-submission-v2",
            "packet_id": app.packet.packet_id,
            "packet_content_sha256": app.packet.content_sha256,
            "current_case_id": "blind-1",
            "annotations": {
                "blind-1": {
                    "expected_revision": 0,
                    "decision": {
                        "pairs": [],
                        "missed_definition": "none",
                        "notes": "Whole passage searched.",
                    },
                }
            },
        }
    ).encode()


def test_blind_packet_and_html_contain_no_assisted_output_fields(
    tmp_path: Path,
) -> None:
    path = _packet(tmp_path / "packet.json")
    app = _ReviewerState(path, mode="blind")
    payload = app.packet_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "abrex-blind-review-packet-v1"
    for forbidden in (
        "suggestions",
        "method_ids",
        "method_diagnostics",
        "source_comparisons",
        "confidence",
        "inventory_category",
        "selection_reason",
    ):
        assert forbidden not in serialized
        assert forbidden not in BLIND_REVIEWER_HTML
    for control in (
        "Add relation",
        "Save draft",
        "Searched this passage; no in-scope definition found.",
        "Import JSON",
        "Lock completed annotation",
        "Table/list structure",
    ):
        assert control in BLIND_REVIEWER_HTML
    for independent_scroll_contract in (
        'id="independent-panes"',
        ".app>main.panel",
        ".app>aside.panel:last-child",
        "overflow-y:auto",
        "overscroll-behavior:contain",
    ):
        assert independent_scroll_contract in BLIND_REVIEWER_HTML


def test_blind_state_locks_only_after_search_and_rejects_later_edits(
    tmp_path: Path,
) -> None:
    path = _packet(tmp_path / "packet.json")
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "lock.json"
    app = _ReviewerState(path, mode="blind", state_path=state_path, lock_path=lock_path)

    with pytest.raises(ReviewError, match="not ready"):
        app.lock_annotations()
    app.save_submission(_complete_zero_submission(app))
    locked = app.lock_annotations()

    assert locked["locked"] is True
    assert locked["predictions_exposed"] is False
    assert lock_path.is_file()
    assert app.locked_export()["schema_version"] == ("abrex-blind-annotation-export-v1")
    with pytest.raises(ReviewError, match="state is locked"):
        app.save_submission(_complete_zero_submission(app))

    reopened = _ReviewerState(
        path, mode="blind", state_path=state_path, lock_path=lock_path
    )
    assert reopened.lock_payload()["locked"] is True


def test_assisted_packet_cannot_be_opened_as_blind(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "evidence/T052/review-packet-v2.json"
    with pytest.raises(ValueError, match="invalid blind review packet"):
        _ReviewerState(source, mode="blind", state_path=tmp_path / "state.json")


def test_blind_packet_identity_detects_changes(tmp_path: Path) -> None:
    path = _packet(tmp_path / "packet.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["cases"][0]["text"] += " changed"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid blind review packet"):
        read_blind_packet(path)
