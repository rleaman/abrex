"""Versioned, additive audit supplement contract for T054.

The supplement is deliberately separate from the T052 annotation state.  T052
files remain valid legacy interchange; this module only adds the fields needed
for the human audit and never upgrades or rewrites those files.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.literature.review_models import ReviewError, fingerprint, now

AUDIT_SUPPLEMENT_SCHEMA_VERSION: Literal["t054-audit-supplement-v1"] = (
    "t054-audit-supplement-v1"
)

Support = Literal["supported", "unsupported", "uncertain", "unreviewed"]
RelationKind = Literal[
    "abbreviation_expansion", "other_naming_or_code_relation", "uncertain"
]
EvidenceStructure = Literal["contiguous_shared", "discontinuous", "uncertain"]
ContextRequirement = Literal["text_alone", "document_structure", "image", "uncertain"]
Scope = Literal["body_text", "caption", "table", "uncertain"]
SearchStatus = Literal["not_searched", "searched_none_found", "searched_found"]


class AuditSpan(BaseModel):
    """An exact half-open span in the case's canonical Unicode text."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def interval(self) -> AuditSpan:
        if self.start >= self.end:
            raise ValueError("audit span start must be smaller than end")
        return self


class ReconstructedExpansion(BaseModel):
    """An interpretation without invented source coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(min_length=1)
    label: Literal["reconstructed"] = "reconstructed"


class AuditAlternative(BaseModel):
    """One alternative in an unresolved one-to-many relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    alternative_id: str = Field(min_length=1)
    anchor_spans: tuple[AuditSpan, ...] = ()
    evidence_spans: tuple[AuditSpan, ...] = ()
    reconstructed_expansion: ReconstructedExpansion | None = None


class SourceErrorProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    flagged: bool = False
    note: str = ""
    proposed_text: str | None = None


class AuditRelation(BaseModel):
    """A proposal with exact evidence and no implicit scientific coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    relation_id: str = Field(min_length=1)
    support: Support = "unreviewed"
    relation_kind: RelationKind = "uncertain"
    evidence_structure: EvidenceStructure = "uncertain"
    context_requirement: ContextRequirement = "uncertain"
    scope: Scope = "uncertain"
    anchor_spans: tuple[AuditSpan, ...] = ()
    evidence_spans: tuple[AuditSpan, ...] = ()
    alternatives: tuple[AuditAlternative, ...] = ()
    reconstructed_expansion: ReconstructedExpansion | None = None
    source_error: SourceErrorProposal | None = None
    notes: str = ""


class RelationDecision(BaseModel):
    """A decision on one relation, independent of passage search completion."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    relation_id: str = Field(min_length=1)
    support: Support
    note: str = ""


class AuditSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    relation_decisions: tuple[RelationDecision, ...] = ()
    search_status: SearchStatus = "not_searched"
    search_note: str = ""

    @model_validator(mode="after")
    def unique_relations(self) -> AuditSnapshot:
        ids = [item.relation_id for item in self.relation_decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("relation decisions must have unique relation IDs")
        return self


class AuditRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revision: int = Field(ge=1)
    saved_at: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    source: Literal["browser", "json_import", "bioc_sidecar_import"]
    assisted_exposure: bool
    snapshot: AuditSnapshot


class AuditCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    canonical_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relations: tuple[AuditRelation, ...] = ()
    revision: int = Field(ge=0, default=0)
    current: AuditSnapshot = AuditSnapshot()
    history: tuple[AuditRevision, ...] = ()

    @model_validator(mode="after")
    def validate_case(self) -> AuditCase:
        import hashlib

        if (
            hashlib.sha256(self.canonical_text.encode("utf-8")).hexdigest()
            != self.canonical_text_sha256
        ):
            raise ReviewError(f"canonical text hash mismatch for {self.case_id}")
        relation_ids = {item.relation_id for item in self.relations}
        if len(relation_ids) != len(self.relations):
            raise ValueError("audit relation IDs must be unique")
        for relation in self.relations:
            for span in (*relation.anchor_spans, *relation.evidence_spans):
                validate_audit_span(span, self.canonical_text, self.case_id)
            for alternative in relation.alternatives:
                for span in (*alternative.anchor_spans, *alternative.evidence_spans):
                    validate_audit_span(span, self.canonical_text, self.case_id)
        if tuple(event.revision for event in self.history) != tuple(
            range(1, self.revision + 1)
        ):
            raise ValueError("audit history must contain every ordered revision")
        if self.revision == 0 and self.history:
            raise ValueError("revision zero cannot have history")
        if self.history and self.history[-1].snapshot != self.current:
            raise ValueError("latest audit history snapshot must equal current")
        for decision in self.current.relation_decisions:
            if decision.relation_id not in relation_ids:
                raise ReviewError(f"unknown audit relation ID {decision.relation_id}")
        return self


class AuditSupplement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["t054-audit-supplement-v1"] = (
        AUDIT_SUPPLEMENT_SCHEMA_VERSION
    )
    supplement_id: str = Field(min_length=1)
    t052_packet_id: str = Field(min_length=1)
    t052_packet_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    t052_annotation_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    t053_audit_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: tuple[AuditCase, ...] = ()

    @model_validator(mode="after")
    def identity(self) -> AuditSupplement:
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("audit case IDs must be unique")
        expected = f"t054-{fingerprint(supplement_identity_payload(self))[:20]}"
        if self.supplement_id != expected:
            raise ReviewError("audit supplement identity does not match its content")
        return self


def validate_audit_span(span: AuditSpan, text: str, case_id: str) -> None:
    if span.end > len(text) or text[span.start : span.end] != span.text:
        raise ReviewError(f"audit span text mismatch or range error in {case_id}")


def supplement_identity_payload(value: AuditSupplement) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "t052_packet_id": value.t052_packet_id,
        "t052_packet_content_sha256": value.t052_packet_content_sha256,
        "t052_annotation_state_sha256": value.t052_annotation_state_sha256,
        "t053_audit_packet_sha256": value.t053_audit_packet_sha256,
        "cases": [case.model_dump(mode="json") for case in value.cases],
    }


def validate_supplement_identity(value: AuditSupplement) -> None:
    expected = f"t054-{fingerprint(supplement_identity_payload(value))[:20]}"
    if value.supplement_id != expected:
        raise ReviewError("audit supplement identity does not match its content")


def validate_supplement_sources(
    value: AuditSupplement,
    *,
    t052_packet_id: str,
    t052_packet_content_sha256: str,
    t052_annotation_state_sha256: str,
    t053_audit_packet_sha256: str,
) -> None:
    """Reject a supplement prepared for a different immutable input bundle."""
    if (
        value.t052_packet_id != t052_packet_id
        or value.t052_packet_content_sha256 != t052_packet_content_sha256
        or value.t052_annotation_state_sha256 != t052_annotation_state_sha256
        or value.t053_audit_packet_sha256 != t053_audit_packet_sha256
    ):
        raise ReviewError("audit supplement source identity mismatch")


def read_audit_supplement(
    path: Path, *, expected_sources: dict[str, str] | None = None
) -> AuditSupplement:
    try:
        value = AuditSupplement.model_validate_json(path.read_text(encoding="utf-8"))
        validate_supplement_identity(value)
        if expected_sources is not None:
            validate_supplement_sources(value, **expected_sources)
        return value
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, ReviewError):
            raise
        raise ReviewError(f"invalid audit supplement: {error}") from error


def write_audit_supplement(value: AuditSupplement, path: Path) -> None:
    validate_supplement_identity(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value.model_dump_json(indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def apply_audit_revision(
    case: AuditCase,
    snapshot: AuditSnapshot,
    *,
    expected_revision: int,
    reviewer_id: str,
    assisted_exposure: bool,
    source: Literal["browser", "json_import", "bioc_sidecar_import"] = "browser",
) -> AuditCase:
    """Apply one case revision and reject stale concurrent writers."""
    if expected_revision != case.revision:
        raise ReviewError(
            f"audit revision conflict for {case.case_id}: expected "
            f"{expected_revision}, current {case.revision}"
        )
    event = AuditRevision(
        revision=case.revision + 1,
        saved_at=now(),
        reviewer_id=reviewer_id,
        source=source,
        assisted_exposure=assisted_exposure,
        snapshot=snapshot,
    )
    return AuditCase(
        case_id=case.case_id,
        canonical_text=case.canonical_text,
        canonical_text_sha256=case.canonical_text_sha256,
        relations=case.relations,
        revision=event.revision,
        current=snapshot,
        history=case.history + (event,),
    )


def empty_audit_supplement(
    *,
    t052_packet_id: str,
    t052_packet_content_sha256: str,
    t052_annotation_state_sha256: str,
    t053_audit_packet_sha256: str,
    cases: tuple[AuditCase, ...] = (),
) -> AuditSupplement:
    identity: dict[str, object] = {
        "schema_version": AUDIT_SUPPLEMENT_SCHEMA_VERSION,
        "t052_packet_id": t052_packet_id,
        "t052_packet_content_sha256": t052_packet_content_sha256,
        "t052_annotation_state_sha256": t052_annotation_state_sha256,
        "t053_audit_packet_sha256": t053_audit_packet_sha256,
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    return AuditSupplement(
        supplement_id=f"t054-{fingerprint(identity)[:20]}",
        t052_packet_id=t052_packet_id,
        t052_packet_content_sha256=t052_packet_content_sha256,
        t052_annotation_state_sha256=t052_annotation_state_sha256,
        t053_audit_packet_sha256=t053_audit_packet_sha256,
        cases=cases,
    )


__all__ = [
    "AUDIT_SUPPLEMENT_SCHEMA_VERSION",
    "AuditAlternative",
    "AuditCase",
    "AuditRelation",
    "AuditRevision",
    "AuditSnapshot",
    "AuditSpan",
    "AuditSupplement",
    "ContextRequirement",
    "EvidenceStructure",
    "RelationDecision",
    "RelationKind",
    "ReconstructedExpansion",
    "Scope",
    "SourceErrorProposal",
    "Support",
    "apply_audit_revision",
    "empty_audit_supplement",
    "read_audit_supplement",
    "validate_audit_span",
    "validate_supplement_identity",
    "validate_supplement_sources",
    "write_audit_supplement",
]
