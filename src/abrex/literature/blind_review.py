"""Prediction-free packet, readiness, and immutable lock contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.literature.review_models import (
    AnnotationState,
    ReviewCase,
    ReviewPacket,
    ReviewSelection,
    ReviewStructure,
    fingerprint,
    now,
)
from abrex.literature.review_readiness import (
    CaseReadiness,
    ReadinessIssue,
    ReviewReadiness,
)

BLIND_PACKET_SCHEMA: Literal["abrex-blind-review-packet-v1"] = (
    "abrex-blind-review-packet-v1"
)
BLIND_LOCK_SCHEMA: Literal["abrex-blind-annotation-lock-v1"] = (
    "abrex-blind-annotation-lock-v1"
)


class BlindReviewCase(BaseModel):
    """Source-only annotation case with no detector-derived fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    article_group_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    arm: Literal["pmc_cc_by", "pubmed_abstract"]
    source_url: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    section_heading: str = Field(min_length=1)
    canonical_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    passage_start: int = Field(ge=0)
    passage_end: int = Field(ge=1)
    text: str = Field(min_length=1)
    context_before: str = ""
    context_after: str = ""
    structures: tuple[ReviewStructure, ...] = ()

    @model_validator(mode="after")
    def passage(self) -> BlindReviewCase:
        if self.passage_end - self.passage_start != len(self.text):
            raise ValueError("passage bounds must equal its Unicode code-point length")
        return self


class BlindReviewPacket(BaseModel):
    """Immutable source-only packet served by the blind reviewer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["abrex-blind-review-packet-v1"] = BLIND_PACKET_SCHEMA
    packet_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol_id: str = Field(min_length=1)
    seed: int
    cases: tuple[BlindReviewCase, ...]

    @model_validator(mode="after")
    def identity(self) -> BlindReviewPacket:
        payload = self.model_dump(mode="json", exclude={"packet_id", "content_sha256"})
        digest = fingerprint(payload)
        if self.content_sha256 != digest or self.packet_id != f"blind-{digest[:20]}":
            raise ValueError("blind packet identity does not match immutable content")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("blind review case IDs must be unique")
        return self

    def annotation_packet(self) -> ReviewPacket:
        """Return the established state-validation view with neutral metadata."""

        cases = tuple(
            ReviewCase(
                case_id=case.case_id,
                inventory_id=f"blind-{case.case_id}",
                article_id=case.article_id,
                article_group_id=case.article_group_id,
                title=case.title,
                arm=case.arm,
                source_url=case.source_url,
                source_kind=case.source_kind,
                section_id=case.section_id,
                section_heading=case.section_heading,
                category="uniform_zero",
                inventory_category="prediction_blind",
                canonical_text_sha256=case.canonical_text_sha256,
                passage_start=case.passage_start,
                passage_end=case.passage_end,
                text=case.text,
                context_before=case.context_before,
                context_after=case.context_after,
                suggestions=(),
                structures=case.structures,
                source_comparisons=(),
                method_diagnostics=(),
                selection_reason="frozen prediction-blind sample",
            )
            for case in self.cases
        )
        counts = {"prediction_blind": len(cases)}
        return ReviewPacket(
            packet_id=self.packet_id,
            content_sha256=self.content_sha256,
            source_manifest_sha256=self.content_sha256,
            source_run_id=self.protocol_id,
            seed=self.seed,
            cases=cases,
            selection=ReviewSelection(
                targets=counts,
                denominators=counts,
                selected=counts,
                shortages={"prediction_blind": 0},
                arm_counts={
                    arm: sum(case.arm == arm for case in cases)
                    for arm in ("pmc_cc_by", "pubmed_abstract")
                },
                per_article_cap=max(
                    (
                        sum(
                            item.article_group_id == case.article_group_id
                            for item in cases
                        )
                        for case in cases
                    ),
                    default=1,
                ),
            ),
        )


class BlindAnnotationLock(BaseModel):
    """Immutable binding between a completed blind packet and annotation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["abrex-blind-annotation-lock-v1"] = BLIND_LOCK_SCHEMA
    packet_id: str
    packet_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locked_at: str = Field(min_length=1)
    exposure_status: Literal["prediction_blind"] = "prediction_blind"
    predictions_exposed: Literal[False] = False


def create_blind_packet(
    cases: tuple[BlindReviewCase, ...], *, protocol_id: str, seed: int
) -> BlindReviewPacket:
    """Content-address source-only cases without adding derived annotations."""

    payload = {
        "schema_version": BLIND_PACKET_SCHEMA,
        "protocol_id": protocol_id,
        "seed": seed,
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    digest = fingerprint(payload)
    return BlindReviewPacket(
        packet_id=f"blind-{digest[:20]}",
        content_sha256=digest,
        protocol_id=protocol_id,
        seed=seed,
        cases=cases,
    )


def read_blind_packet(path: Path) -> BlindReviewPacket:
    """Read and validate a source-only packet."""

    try:
        return BlindReviewPacket.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"invalid blind review packet: {error}") from error


def write_blind_packet(packet: BlindReviewPacket, path: Path) -> None:
    """Write a deterministic source-only packet."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        packet.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def blind_review_readiness(
    packet: ReviewPacket,
    state: AnnotationState,
    required_case_ids: tuple[str, ...],
) -> ReviewReadiness:
    """Require a whole-passage search while preserving explicit uncertainty."""

    by_id = {case.case_id: case for case in packet.cases}
    results: list[CaseReadiness] = []
    for case_id in required_case_ids:
        case = by_id[case_id]
        annotation = state.annotations.get(case_id)
        snapshot = annotation.current if annotation else None
        issues: list[ReadinessIssue] = []
        if snapshot is None or snapshot.missed_definition != "none":
            issues.append(
                ReadinessIssue(
                    case_id=case_id,
                    kind="passage_search",
                    message="Confirm that the entire passage was searched.",
                )
            )
        for pair in snapshot.pairs if snapshot else ():
            if pair.short_form is None or pair.long_form is None:
                issues.append(
                    ReadinessIssue(
                        case_id=case_id,
                        decision_id=pair.decision_id,
                        kind="support",
                        message="A recorded relation needs both exact endpoints.",
                    )
                )
            if pair.evidence_structure == "discontinuous" and not pair.evidence_spans:
                issues.append(
                    ReadinessIssue(
                        case_id=case_id,
                        decision_id=pair.decision_id,
                        kind="evidence_fragments",
                        message="A discontinuous relation needs evidence fragments.",
                    )
                )
        results.append(
            CaseReadiness(
                case_id=case_id,
                title=case.title,
                complete=not issues,
                issues=tuple(issues),
            )
        )
    complete = sum(item.complete for item in results)
    return ReviewReadiness(
        complete=complete == len(results),
        required_cases=len(results),
        complete_cases=complete,
        remaining_cases=len(results) - complete,
        remaining_items=sum(len(item.issues) for item in results),
        cases=tuple(results),
    )


def create_annotation_lock(
    packet: ReviewPacket, state: AnnotationState
) -> BlindAnnotationLock:
    """Bind a complete state to its packet without exposing later predictions."""

    return BlindAnnotationLock(
        packet_id=packet.packet_id,
        packet_content_sha256=packet.content_sha256,
        annotation_state_sha256=fingerprint(state.model_dump(mode="json")),
        locked_at=now(),
    )


def write_annotation_lock(lock: BlindAnnotationLock, path: Path) -> None:
    """Atomically persist an annotation lock."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(lock.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


__all__ = [
    "BLIND_LOCK_SCHEMA",
    "BLIND_PACKET_SCHEMA",
    "BlindAnnotationLock",
    "BlindReviewCase",
    "BlindReviewPacket",
    "blind_review_readiness",
    "create_annotation_lock",
    "create_blind_packet",
    "read_blind_packet",
    "write_annotation_lock",
    "write_blind_packet",
]
