"""Focused contract tests for the additive T054 audit supplement."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from abrex.literature.audit_supplement import (
    AuditCase,
    AuditRelation,
    AuditRevision,
    AuditSpan,
    ReconstructedExpansion,
    RelationDecision,
    apply_audit_revision,
    empty_audit_supplement,
    read_audit_supplement,
    validate_supplement_sources,
    write_audit_supplement,
)
from abrex.literature.review_models import ReviewError


def _case() -> AuditCase:
    text = "Tumor necrosis factor (TNF) 🧬"
    digest = hashlib.sha256(text.encode()).hexdigest()
    relation = AuditRelation(
        relation_id="r-1",
        support="unreviewed",
        relation_kind="abbreviation_expansion",
        evidence_structure="contiguous_shared",
        context_requirement="text_alone",
        scope="body_text",
        anchor_spans=(AuditSpan(start=23, end=26, text="TNF"),),
        evidence_spans=(AuditSpan(start=0, end=21, text="Tumor necrosis factor"),),
        reconstructed_expansion=ReconstructedExpansion(text="Tumor necrosis factor"),
    )
    return AuditCase(
        case_id="case-1",
        canonical_text=text,
        canonical_text_sha256=digest,
        relations=(relation,),
    )


def test_round_trip_preserves_unicode_exact_evidence_and_identity(
    tmp_path: Path,
) -> None:
    supplement = empty_audit_supplement(
        t052_packet_id="t052-packet",
        t052_packet_content_sha256="a" * 64,
        t052_annotation_state_sha256="b" * 64,
        t053_audit_packet_sha256="c" * 64,
        cases=(_case(),),
    )
    path = tmp_path / "supplement.json"
    write_audit_supplement(supplement, path)
    assert read_audit_supplement(path) == supplement
    assert read_audit_supplement(path).cases[0].canonical_text.endswith("🧬")


def test_rejects_stale_identity_and_bad_unicode_span(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="span"):
        AuditCase(
            case_id="case-1",
            canonical_text="é",
            canonical_text_sha256=hashlib.sha256("é".encode()).hexdigest(),
            relations=(
                AuditRelation(
                    relation_id="r",
                    anchor_spans=(AuditSpan(start=0, end=1, text="e"),),
                ),
            ),
        )
    with pytest.raises(ReviewError, match="invalid audit supplement"):
        path = tmp_path / "stale-supplement.json"
        path.write_text(
            '{"schema_version":"t054-audit-supplement-v1"}', encoding="utf-8"
        )
        try:
            read_audit_supplement(path)
        finally:
            path.unlink(missing_ok=True)


def test_revision_history_and_search_are_separate() -> None:
    case = _case()
    decision = RelationDecision(relation_id="r-1", support="supported")
    snapshot = case.current.model_copy(
        update={
            "relation_decisions": (decision,),
            "search_status": "searched_none_found",
        }
    )
    revision = AuditRevision(
        revision=1,
        saved_at="2026-09-11T00:00:00Z",
        reviewer_id="reviewer",
        source="json_import",
        assisted_exposure=True,
        snapshot=snapshot,
    )
    updated = case.model_copy(
        update={"revision": 1, "current": snapshot, "history": (revision,)}
    )
    assert updated.current.relation_decisions[0].support == "supported"
    assert updated.current.search_status == "searched_none_found"


def test_stale_revision_and_source_identity_are_rejected() -> None:
    case = _case()
    snapshot = case.current.model_copy(
        update={
            "relation_decisions": (
                RelationDecision(relation_id="r-1", support="uncertain"),
            )
        }
    )
    updated = apply_audit_revision(
        case,
        snapshot,
        expected_revision=0,
        reviewer_id="reviewer",
        assisted_exposure=False,
    )
    with pytest.raises(ReviewError, match="revision conflict"):
        apply_audit_revision(
            updated,
            snapshot,
            expected_revision=0,
            reviewer_id="other",
            assisted_exposure=False,
        )
    supplement = empty_audit_supplement(
        t052_packet_id="packet",
        t052_packet_content_sha256="a" * 64,
        t052_annotation_state_sha256="b" * 64,
        t053_audit_packet_sha256="c" * 64,
    )
    with pytest.raises(ReviewError, match="source identity"):
        validate_supplement_sources(
            supplement,
            t052_packet_id="other",
            t052_packet_content_sha256="a" * 64,
            t052_annotation_state_sha256="b" * 64,
            t053_audit_packet_sha256="c" * 64,
        )


def test_interrupted_atomic_save_leaves_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplement = empty_audit_supplement(
        t052_packet_id="packet",
        t052_packet_content_sha256="a" * 64,
        t052_annotation_state_sha256="b" * 64,
        t053_audit_packet_sha256="c" * 64,
    )
    path = tmp_path / "supplement.json"
    write_audit_supplement(supplement, path)
    original = path.read_bytes()

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("simulated interrupted save")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        write_audit_supplement(supplement, path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))
