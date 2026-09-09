"""Typed, content-addressed T052 review and annotation models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REVIEW_SCHEMA_VERSION: Literal["t052-review-packet-v2"] = "t052-review-packet-v2"
ANNOTATION_SCHEMA_VERSION: Literal["t052-annotations-v2"] = "t052-annotations-v2"
SUBMISSION_SCHEMA_VERSION: Literal["t052-annotation-submission-v2"] = (
    "t052-annotation-submission-v2"
)
PRIMARY_METHODS = ("schwartz_hearst", "ab3p", "plodv2_pairing")

PairStatus = Literal["unreviewed", "correct", "incorrect", "unsure"]
MissedStatus = Literal["unreviewed", "none", "missed", "unsure"]
DecisionOrigin = Literal["assisted", "corrected", "added"]


class ReviewError(ValueError):
    """Raised when review content cannot be accepted without data loss."""


class ReviewSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def interval(self) -> ReviewSpan:
        if self.start >= self.end:
            raise ValueError("review span start must be smaller than end")
        return self


class ReviewSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    suggestion_id: str = Field(min_length=1)
    proposal_kind: Literal["definition", "span"] = "definition"
    short_form: ReviewSpan | None = None
    long_form: ReviewSpan | None = None
    source_pair_ids: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    method_ids: tuple[str, ...] = ()
    provenance: tuple[dict[str, object], ...] = ()

    @model_validator(mode="after")
    def endpoint(self) -> ReviewSuggestion:
        if self.short_form is None and self.long_form is None:
            raise ValueError("a review suggestion needs at least one endpoint")
        if self.proposal_kind == "definition" and (
            self.short_form is None or self.long_form is None
        ):
            raise ValueError("a definition suggestion needs both endpoints")
        return self


class ReviewStructure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: str = Field(min_length=1)
    text: str
    source_path: str | None = None


class ReviewCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str = Field(min_length=1)
    inventory_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    article_group_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    arm: Literal["pmc_cc_by", "pubmed_abstract"]
    source_url: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    section_heading: str = Field(min_length=1)
    category: Literal[
        "disagreement", "agreement", "enriched_zero", "uniform_zero", "diagnostic"
    ]
    inventory_category: str = Field(min_length=1)
    canonical_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    passage_start: int = Field(ge=0)
    passage_end: int = Field(ge=1)
    text: str = Field(min_length=1)
    context_before: str = ""
    context_after: str = ""
    suggestions: tuple[ReviewSuggestion, ...] = ()
    structures: tuple[ReviewStructure, ...] = ()
    source_comparisons: tuple[dict[str, object], ...] = ()
    method_diagnostics: tuple[dict[str, object], ...] = ()
    selection_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passage(self) -> ReviewCase:
        if self.passage_end - self.passage_start != len(self.text):
            raise ValueError("passage bounds must equal its Unicode code-point length")
        if len({item.suggestion_id for item in self.suggestions}) != len(
            self.suggestions
        ):
            raise ValueError("suggestion IDs must be unique")
        for suggestion in self.suggestions:
            validate_span(suggestion.short_form, self.text, "suggestion short form")
            validate_span(suggestion.long_form, self.text, "suggestion long form")
        return self


class ReviewSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    targets: dict[str, int]
    denominators: dict[str, int]
    selected: dict[str, int]
    shortages: dict[str, int]
    arm_counts: dict[str, int]
    per_article_cap: int = Field(ge=1)


class ReviewPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["t052-review-packet-v2"] = REVIEW_SCHEMA_VERSION
    packet_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: str = Field(min_length=1)
    seed: int
    cases: tuple[ReviewCase, ...]
    selection: ReviewSelection


class PairDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision_id: str = Field(min_length=1)
    suggestion_id: str | None = None
    proposal_kind: Literal["definition", "span"] = "definition"
    status: PairStatus = "unreviewed"
    short_form: ReviewSpan | None = None
    long_form: ReviewSpan | None = None
    origin: DecisionOrigin = "assisted"
    notes: str = ""

    @model_validator(mode="after")
    def origin_contract(self) -> PairDecision:
        if self.origin == "added" and self.suggestion_id is not None:
            raise ValueError("added definitions cannot reference a suggestion")
        if self.origin != "added" and self.suggestion_id is None:
            raise ValueError("assisted/corrected decisions require a suggestion")
        if self.short_form is None and self.long_form is None:
            raise ValueError("a pair decision needs at least one endpoint")
        if (
            self.proposal_kind == "definition"
            and self.status == "correct"
            and (self.short_form is None or self.long_form is None)
        ):
            raise ValueError("a correct definition decision needs both endpoints")
        return self


class DecisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pairs: tuple[PairDecision, ...] = ()
    missed_definition: MissedStatus = "unreviewed"
    notes: str = ""


class RevisionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revision: int = Field(ge=1)
    saved_at: str = Field(min_length=1)
    source: Literal["browser", "json_import", "bioc_import"]
    snapshot: DecisionSnapshot


class CaseAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revision: int = Field(ge=1)
    updated_at: str = Field(min_length=1)
    current: DecisionSnapshot
    history: tuple[RevisionEvent, ...]

    @model_validator(mode="after")
    def full_history(self) -> CaseAnnotation:
        if tuple(event.revision for event in self.history) != tuple(
            range(1, self.revision + 1)
        ):
            raise ValueError("annotation history must contain every ordered revision")
        if not self.history or self.history[-1].snapshot != self.current:
            raise ValueError("latest history snapshot must equal current decision")
        return self


class AnnotationState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["t052-annotations-v2"] = ANNOTATION_SCHEMA_VERSION
    packet_id: str = Field(min_length=1)
    packet_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_case_id: str | None = None
    updated_at: str | None = None
    annotations: dict[str, CaseAnnotation] = Field(default_factory=dict)


class CaseSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision: int = Field(ge=0)
    decision: DecisionSnapshot


class AnnotationSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["t052-annotation-submission-v2"] = SUBMISSION_SCHEMA_VERSION
    packet_id: str
    packet_content_sha256: str
    current_case_id: str | None = None
    annotations: dict[str, CaseSubmission] = Field(default_factory=dict)


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def validate_span(span: ReviewSpan | None, text: str, label: str) -> None:
    if span is None:
        return
    if span.end > len(text):
        raise ReviewError(f"{label} [{span.start}, {span.end}) is out of range")
    expected = text[span.start : span.end]
    if expected != span.text:
        raise ReviewError(
            f"{label} text mismatch: expected {expected!r}, received {span.text!r}"
        )


def packet_identity_payload(packet: ReviewPacket) -> dict[str, object]:
    return {
        "schema_version": packet.schema_version,
        "source_manifest_sha256": packet.source_manifest_sha256,
        "source_run_id": packet.source_run_id,
        "seed": packet.seed,
        "cases": [case.model_dump(mode="json") for case in packet.cases],
        "selection": packet.selection.model_dump(mode="json"),
    }


def validate_packet_identity(packet: ReviewPacket) -> None:
    digest = fingerprint(packet_identity_payload(packet))
    if digest != packet.content_sha256 or packet.packet_id != f"t052-{digest[:20]}":
        raise ReviewError("review packet identity does not match its immutable content")
    if len({case.case_id for case in packet.cases}) != len(packet.cases):
        raise ReviewError("review case IDs must be unique")


def validate_snapshot(case: ReviewCase, snapshot: DecisionSnapshot) -> None:
    suggestions = {item.suggestion_id: item for item in case.suggestions}
    decision_ids: set[str] = set()
    referenced: set[str] = set()
    for pair in snapshot.pairs:
        if pair.decision_id in decision_ids:
            raise ReviewError(f"duplicate decision ID {pair.decision_id}")
        decision_ids.add(pair.decision_id)
        validate_span(pair.short_form, case.text, "short form")
        validate_span(pair.long_form, case.text, "long form")
        if pair.suggestion_id:
            suggestion = suggestions.get(pair.suggestion_id)
            if suggestion is None:
                raise ReviewError(f"unknown suggestion ID {pair.suggestion_id}")
            if pair.suggestion_id in referenced:
                raise ReviewError(
                    f"suggestion {pair.suggestion_id} has multiple current decisions"
                )
            referenced.add(pair.suggestion_id)
            if pair.proposal_kind != suggestion.proposal_kind:
                raise ReviewError("decision proposal kind differs from its suggestion")
            if pair.origin == "assisted" and (
                pair.short_form != suggestion.short_form
                or pair.long_form != suggestion.long_form
            ):
                raise ReviewError(
                    "changed suggestion endpoints require corrected provenance"
                )
    # A submission may be partial while a reviewer is working through a case.
    # Unreferenced suggestions remain visible in the packet and are represented
    # as unreviewed by the browser's base snapshot; requiring every suggestion
    # here would make incremental save/resume and partial BioC backups fail.


def empty_annotation_state(packet: ReviewPacket) -> AnnotationState:
    return AnnotationState(
        packet_id=packet.packet_id, packet_content_sha256=packet.content_sha256
    )


def validate_annotation_state(packet: ReviewPacket, state: AnnotationState) -> None:
    if (
        state.packet_id != packet.packet_id
        or state.packet_content_sha256 != packet.content_sha256
    ):
        raise ReviewError("annotation packet/content identity mismatch")
    cases = {case.case_id: case for case in packet.cases}
    if state.current_case_id is not None and state.current_case_id not in cases:
        raise ReviewError(f"unknown resume case ID {state.current_case_id}")
    unknown = sorted(set(state.annotations) - set(cases))
    if unknown:
        raise ReviewError(f"unknown annotation case IDs: {unknown}")
    for case_id, annotation in state.annotations.items():
        for event in annotation.history:
            validate_snapshot(cases[case_id], event.snapshot)


def apply_submission(
    packet: ReviewPacket,
    state: AnnotationState,
    submission: AnnotationSubmission,
    *,
    source: Literal["browser", "json_import", "bioc_import"] = "browser",
) -> AnnotationState:
    if (
        submission.packet_id != packet.packet_id
        or submission.packet_content_sha256 != packet.content_sha256
    ):
        raise ReviewError("annotation submission packet/content identity mismatch")
    cases = {case.case_id: case for case in packet.cases}
    if (
        submission.current_case_id is not None
        and submission.current_case_id not in cases
    ):
        raise ReviewError(f"unknown resume case ID {submission.current_case_id}")
    updated = dict(state.annotations)
    saved_at = now()
    for case_id, item in submission.annotations.items():
        case = cases.get(case_id)
        if case is None:
            raise ReviewError(f"unknown annotation case ID {case_id}")
        validate_snapshot(case, item.decision)
        previous = updated.get(case_id)
        actual = previous.revision if previous else 0
        if item.expected_revision != actual:
            raise ReviewError(
                f"revision conflict for {case_id}: expected {item.expected_revision}, "
                f"current {actual}"
            )
        if previous and previous.current == item.decision:
            continue
        revision = actual + 1
        event = RevisionEvent(
            revision=revision, saved_at=saved_at, source=source, snapshot=item.decision
        )
        updated[case_id] = CaseAnnotation(
            revision=revision,
            updated_at=saved_at,
            current=item.decision,
            history=(previous.history if previous else ()) + (event,),
        )
    result = AnnotationState(
        packet_id=packet.packet_id,
        packet_content_sha256=packet.content_sha256,
        current_case_id=submission.current_case_id,
        updated_at=saved_at,
        annotations=updated,
    )
    validate_annotation_state(packet, result)
    return result
