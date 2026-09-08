"""Immutable weak-evidence records and transparent silver-label aggregation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates import Candidate
from abrex.domain import Document, TextSpan

EvidencePolarity = Literal["positive", "negative", "abstain"]
SilverStatus = Literal["positive", "negative", "abstain"]


class EvidenceAggregationConfig(BaseModel):
    """Explicit deterministic policy for collapsing weak evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    positive_threshold: float = Field(default=1.0, ge=0)
    negative_threshold: float = Field(default=1.0, ge=0)
    conflict_policy: Literal["abstain", "priority"] = "abstain"
    positive_priority: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One exact, source-family-labelled observation about a candidate."""

    document_id: str
    short_form: TextSpan
    long_form: TextSpan
    source_family: str
    source_id: str
    source_version: str
    polarity: EvidencePolarity
    weight: float = 1.0
    local_context: str = ""
    iteration_lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("document_id", "source_family", "source_id", "source_version"):
            if (
                not isinstance(getattr(self, name), str)
                or not getattr(self, name).strip()
            ):
                raise ValueError(f"{name} must not be empty")
        if self.polarity not in ("positive", "negative", "abstain"):
            raise ValueError("invalid evidence polarity")
        if self.weight < 0:
            raise ValueError("evidence weight must be non-negative")

    def validate_against(self, document: Document) -> None:
        if document.document_id != self.document_id:
            raise ValueError("evidence document ID does not match document")
        self.short_form.validate_against(document.text)
        self.long_form.validate_against(document.text)

    @property
    def evidence_id(self) -> str:
        payload = json.dumps(asdict(self), default=_json_default, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SilverLabel:
    """Generated label with complete aggregation lineage."""

    document_id: str
    short_form: TextSpan
    long_form: TextSpan
    status: SilverStatus
    evidence_ids: tuple[str, ...]
    aggregation_config: EvidenceAggregationConfig
    reason: str
    confidence: float


class EvidenceLedger:
    """Append-only content-addressed evidence collection."""

    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: EvidenceRecord) -> str:
        """Add once by content identity and return its stable ID."""

        identifier = record.evidence_id
        self._records.setdefault(identifier, record)
        return identifier

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records.values())

    def label(
        self,
        document: Document,
        short_form: TextSpan,
        long_form: TextSpan,
        config: EvidenceAggregationConfig,
    ) -> SilverLabel:
        """Aggregate supplied evidence; absence never means negative."""

        selected = tuple(
            (identifier, record)
            for identifier, record in self._records.items()
            if record.document_id == document.document_id
            and record.short_form == short_form
            and record.long_form == long_form
        )
        families: dict[str, tuple[str, EvidenceRecord]] = {}
        for identifier, record in selected:
            previous = families.get(record.source_family)
            if previous is None or record.weight > previous[1].weight:
                families[record.source_family] = (identifier, record)
        positive = sum(
            record.weight
            for _, record in families.values()
            if record.polarity == "positive"
        )
        negative = sum(
            record.weight
            for _, record in families.values()
            if record.polarity == "negative"
        )
        conflict = (
            positive >= config.positive_threshold
            and negative >= config.negative_threshold
        )
        if conflict and config.conflict_policy == "abstain":
            status: SilverStatus = "abstain"
            reason = "contradictory source-family evidence"
        elif conflict:
            status = "positive" if config.positive_priority else "negative"
            reason = "priority policy resolved contradictory source-family evidence"
        elif positive >= config.positive_threshold:
            status, reason = "positive", "positive source-family evidence met threshold"
        elif negative >= config.negative_threshold:
            status, reason = "negative", "negative source-family evidence met threshold"
        else:
            status, reason = "abstain", "insufficient supplied evidence"
        total = positive + negative
        confidence = max(positive, negative) / total if total else 0.0
        return SilverLabel(
            document.document_id,
            short_form,
            long_form,
            status,
            tuple(identifier for identifier, _ in selected),
            config,
            reason,
            confidence,
        )


def evidence_from_candidate(
    document: Document,
    candidate: Candidate,
    *,
    source_family: str,
    source_id: str,
    source_version: str,
    polarity: EvidencePolarity,
    weight: float = 1.0,
    iteration_lineage: tuple[str, ...] = (),
) -> EvidenceRecord:
    """Create evidence while capturing exact local context."""

    candidate.validate_against(document)
    start = min(candidate.short_form.start, candidate.long_form.start)
    end = max(candidate.short_form.end, candidate.long_form.end)
    return EvidenceRecord(
        document.document_id,
        candidate.short_form,
        candidate.long_form,
        source_family,
        source_id,
        source_version,
        polarity,
        weight,
        document.text[start:end],
        iteration_lineage,
    )


def _json_default(value: object) -> object:
    if isinstance(value, TextSpan):
        return {"start": value.start, "end": value.end}
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"unsupported evidence value: {type(value).__name__}")


__all__ = [
    "EvidenceAggregationConfig",
    "EvidenceLedger",
    "EvidencePolarity",
    "EvidenceRecord",
    "SilverLabel",
    "SilverStatus",
    "evidence_from_candidate",
]
