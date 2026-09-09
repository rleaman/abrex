"""Focused contracts for the real-data pilot and v2 reviewer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abrex.literature.pilot import _is_exact_cc_by
from abrex.literature.review import _ReviewerState
from abrex.literature.review_interchange import import_bioc_xml, write_bioc_xml
from abrex.literature.review_models import (
    AnnotationSubmission,
    CaseSubmission,
    DecisionSnapshot,
    PairDecision,
    ReviewError,
    ReviewSpan,
    apply_submission,
    empty_annotation_state,
)
from abrex.literature.review_packet import (
    build_review_fixture,
    build_review_packet,
    read_review_packet,
)


def test_license_policy_rejects_restricted_variants() -> None:
    assert _is_exact_cc_by("https://creativecommons.org/licenses/by/4.0/", "CC BY")
    assert not _is_exact_cc_by(
        "https://creativecommons.org/licenses/by-nc/4.0/", "CC BY-NC"
    )
    assert not _is_exact_cc_by(None, "unknown")


def test_fixture_json_bioc_round_trip_preserves_unicode_and_identity(
    tmp_path: Path,
) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    assert read_review_packet(tmp_path / "packet.json") == packet
    state = empty_annotation_state(packet)
    case = packet.cases[0]
    suggestion = case.suggestions[0]
    pair = PairDecision(
        decision_id="decision-a",
        suggestion_id=suggestion.suggestion_id,
        short_form=suggestion.short_form,
        long_form=suggestion.long_form,
        status="correct",
    )
    submission = AnnotationSubmission(
        packet_id=packet.packet_id,
        packet_content_sha256=packet.content_sha256,
        current_case_id=case.case_id,
        annotations={
            case.case_id: CaseSubmission(
                expected_revision=0,
                decision=DecisionSnapshot(pairs=(pair,), missed_definition="none"),
            )
        },
    )
    state = apply_submission(packet, state, submission)
    xml = tmp_path / "packet.xml"
    write_bioc_xml(packet, xml, state)
    restored = import_bioc_xml(packet, xml.read_bytes())
    assert (
        restored.annotations[case.case_id].current
        == state.annotations[case.case_id].current
    )
    assert "🧬" in packet.cases[0].text


def test_submission_rejects_unknown_case_and_bad_span(tmp_path: Path) -> None:
    packet = build_review_fixture(tmp_path / "packet.json")
    state = empty_annotation_state(packet)
    with pytest.raises(ReviewError, match="unknown annotation case"):
        apply_submission(
            packet,
            state,
            AnnotationSubmission(
                packet_id=packet.packet_id,
                packet_content_sha256=packet.content_sha256,
                annotations={
                    "missing": CaseSubmission(
                        expected_revision=0, decision=DecisionSnapshot()
                    )
                },
            ),
        )
    case = packet.cases[0]
    bad = DecisionSnapshot(
        pairs=(
            PairDecision(
                decision_id="bad",
                proposal_kind="span",
                status="unsure",
                origin="added",
                short_form=ReviewSpan(start=0, end=1, text="wrong"),
            ),
        )
    )
    with pytest.raises(ReviewError, match="text mismatch"):
        apply_submission(
            packet,
            state,
            AnnotationSubmission(
                packet_id=packet.packet_id,
                packet_content_sha256=packet.content_sha256,
                annotations={
                    case.case_id: CaseSubmission(expected_revision=0, decision=bad)
                },
            ),
        )


def test_malformed_backup_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "old"}), encoding="utf-8")
    with pytest.raises(ValueError):
        read_review_packet(path)


def test_reviewer_state_sidecar_is_scoped_to_packet_filename(tmp_path: Path) -> None:
    packet_path = tmp_path / "review-packet-v2.json"
    build_review_fixture(packet_path)
    state = _ReviewerState(packet_path)
    assert state.state_path == tmp_path / "review-packet-v2.annotations.json"


def test_real_manifest_shape_builds_comparison_and_diagnostic_cases(
    tmp_path: Path,
) -> None:
    text = "Tumor necrosis factor (TNF) was measured."
    digest = hashlib.sha256(text.encode()).hexdigest()

    def output(method: str, *, status: str, pair_id: str | None) -> dict[str, object]:
        pairs = []
        if pair_id is not None:
            pairs = [
                {
                    "pair_id": pair_id,
                    "short_form": {"start": 23, "end": 26, "text": "TNF"},
                    "long_form": {
                        "start": 0,
                        "end": 21,
                        "text": "Tumor necrosis factor",
                    },
                    "provenance": {},
                }
            ]
        return {
            "method_id": method,
            "identity": method,
            "version": "fixture",
            "config_sha256": "0" * 64,
            "runtime": {},
            "status": status,
            "coverage": "complete" if status == "completed" else "none",
            "pairs": pairs,
            "spans": [],
            "diagnostics": [],
        }

    def record(
        article_id: str, category: str, status: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        pair_id = f"pair-{article_id}"
        methods = {
            "schwartz_hearst": output(
                "schwartz_hearst", status="completed", pair_id=pair_id
            ),
            "ab3p": output("ab3p", status=status, pair_id=None),
            "plodv2_pairing": output("plodv2_pairing", status=status, pair_id=None),
        }
        return {
            "article_id": article_id,
            "article_group_id": article_id,
            "arm": "pmc_cc_by",
            "title": article_id,
            "source_url": "https://example.test/article",
            "sections": [
                {
                    "section_id": "body",
                    "document_id": f"{article_id}/body",
                    "heading": "Body",
                    "source_kind": "paragraph",
                    "canonical_text": text,
                    "canonical_text_sha256": digest,
                    "source_locator": "/article/body",
                    "method_outputs": methods,
                    "structural_candidates": [],
                    "lexical_candidates": [],
                }
            ],
            "structures": [],
            "source_artifacts": [],
            "diagnostics": [],
        }, {
            "inventory_id": f"inventory-{article_id}",
            "article_id": article_id,
            "section_id": "body",
            "canonical_text_sha256": digest,
            "category": category,
            "pair_ids": [pair_id] if category == "relation_disagreement" else [],
            "span_ids": [],
            "methods": list(methods),
            "eligible_for_review": category != "method_failure",
            "heuristic": None,
        }

    comparison_record, comparison_inventory = record(
        "PMC-COMPARISON", "relation_disagreement", "failed"
    )
    diagnostic_record, diagnostic_inventory = record(
        "PMC-DIAGNOSTIC", "method_failure", "failed"
    )
    manifest = {
        "schema_version": "random-literature-pilot-v2",
        "run_id": "fixture-run",
        "records": [comparison_record, diagnostic_record],
        "inventories": [comparison_inventory, diagnostic_inventory],
        "source_comparisons": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    packet = build_review_packet(manifest_path, tmp_path / "packet.json")
    assert packet.selection.selected["disagreement"] == 1
    assert packet.selection.selected["diagnostic"] == 1
    assert {case.category for case in packet.cases} == {"disagreement", "diagnostic"}
