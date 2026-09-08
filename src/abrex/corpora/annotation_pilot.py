"""Auditable contemporary annotation-pilot interchange and conversion."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.config import load_config_layer
from abrex.corpora.serialization import record_to_dict
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    SourceTextSpan,
    TextSpan,
)

ANNOTATION_SCHEMA_VERSION = "contemporary-annotation-v1"
ANNOTATION_PROVENANCE_METADATA_VERSION = "annotation-provenance-metadata-v1"
_ANNOTATION_METADATA_NOTE_PREFIX = "annotation_metadata="
LabelOrigin = Literal["independent", "assisted", "adjudicated"]
LabelStatus = Literal["accepted", "unresolved", "rejected"]
PilotRole = Literal["development", "evaluation", "unlabeled_pilot"]


class AnnotationPilotError(ValueError):
    """Raised when an annotation packet cannot be safely imported."""


class AnnotationSpan(BaseModel):
    """A half-open Unicode span with captured source text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> AnnotationSpan:
        if self.start > self.end:
            raise ValueError("annotation span start must not exceed end")
        return self


class AdjudicationEvent(BaseModel):
    """One immutable revision/adjudication-history event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    action: Literal["created", "revised", "adjudicated"]
    note: str = Field(min_length=1)
    from_status: LabelStatus | None = None
    to_status: LabelStatus | None = None


class AnnotationLabel(BaseModel):
    """One relation label with origin, status, and revision lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str = Field(min_length=1)
    short_form: AnnotationSpan | None = None
    long_form: AnnotationSpan | None = None
    origin: LabelOrigin
    status: LabelStatus
    annotator_id: str | None = None
    suggestion_source: str | None = None
    phenomenon_tags: tuple[str, ...] = ()
    revision: int = Field(default=0, ge=0)
    history: tuple[AdjudicationEvent, ...] = ()
    note: str | None = None

    @model_validator(mode="after")
    def validate_origin(self) -> AnnotationLabel:
        if self.origin == "independent" and self.suggestion_source is not None:
            raise ValueError("independent labels cannot name a suggestion source")
        if self.origin == "assisted" and not self.suggestion_source:
            raise ValueError("assisted labels require a suggestion source")
        if not self.annotator_id and self.origin != "assisted":
            raise ValueError("independent/adjudicated labels require annotator_id")
        if any(not tag.strip() for tag in self.phenomenon_tags):
            raise ValueError("phenomenon_tags must not contain empty values")
        return self


class AnnotationCase(BaseModel):
    """One T029-sampled article case and its annotation labels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    article_group_id: str = Field(min_length=1)
    role: PilotRole
    text: str
    guideline_version: str = Field(min_length=1)
    labels: tuple[AnnotationLabel, ...] = ()
    resolver_identity: str | None = None
    source_path: str | None = None

    @model_validator(mode="after")
    def validate_blindness(self) -> AnnotationCase:
        if self.role == "evaluation":
            independent = [
                label for label in self.labels if label.origin == "independent"
            ]
            if independent and self.resolver_identity is not None:
                raise ValueError(
                    "independent evaluation labels must not expose resolver identity"
                )
        if any(label.relation_id.strip() == "" for label in self.labels):
            raise ValueError("relation IDs must be non-empty")
        return self


class AnnotationProvenanceMetadata(BaseModel):
    """Lossless T030 metadata embedded in canonical annotation provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["annotation-provenance-metadata-v1"] = (
        "annotation-provenance-metadata-v1"
    )
    relation_id: str = Field(min_length=1)
    origin: LabelOrigin
    status: LabelStatus
    annotator_id: str | None = None
    suggestion_source: str | None = None
    phenomenon_tags: tuple[str, ...] = ()
    revision: int = Field(ge=0)
    history: tuple[AdjudicationEvent, ...] = ()
    note: str | None = None
    article_group_id: str = Field(min_length=1)
    guideline_version: str = Field(min_length=1)
    resolver_identity: str | None = None
    source_path: str | None = None


class AnnotationPilotConfig(BaseModel):
    """Typed paths and policy for one local annotation-pilot conversion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_path: Path
    canonical_output: Path
    report_output: Path
    guideline_version: str = Field(min_length=1)
    review_packet_output: Path | None = None
    review_packet_size: int = Field(default=8, ge=1)
    seed: int = Field(default=0, ge=0)


def _validate_span(
    span: AnnotationSpan | None, text: str, name: str
) -> TextSpan | None:
    if span is None:
        return None
    canonical = TextSpan(span.start, span.end)
    if span.text is not None and text[span.start : span.end] != span.text:
        raise AnnotationPilotError(
            f"{name} text mismatch for [{span.start}, {span.end})"
        )
    canonical.validate_against(text)
    return canonical


def case_to_corpus_record(case: AnnotationCase) -> CorpusRecord:
    """Convert a case without changing text, offsets, or relation provenance."""

    document = Document(case.document_id, case.text)
    definitions: list[AbbreviationDefinition] = []
    for label in case.labels:
        if label.status == "rejected":
            continue
        short = _validate_span(label.short_form, case.text, "short_form")
        long = _validate_span(label.long_form, case.text, "long_form")
        source_short = (
            SourceTextSpan(short.start, short.end, _text_for(case, short))
            if short is not None
            else None
        )
        source_long = (
            SourceTextSpan(long.start, long.end, _text_for(case, long))
            if long is not None
            else None
        )
        provenance = AnnotationProvenance(
            source_corpus="contemporary-annotation-pilot",
            source_record_id=case.case_id,
            source_annotation_id=label.relation_id,
            original_short_form=source_short,
            original_long_form=source_long,
            adapter_identity="annotation-pilot",
            adapter_version=ANNOTATION_SCHEMA_VERSION,
            transformation_notes=(
                f"origin={label.origin}",
                f"status={label.status}",
                f"revision={label.revision}",
                f"article_group_id={case.article_group_id}",
                _annotation_metadata_note(case, label),
            ),
        )
        definitions.append(
            AbbreviationDefinition(
                document_id=case.document_id,
                short_form=short,
                long_form=long,
                short_form_text=_text_for(case, short) if short is not None else None,
                long_form_text=_text_for(case, long) if long is not None else None,
                provenance=provenance,
            )
        )
    return CorpusRecord(
        document=document,
        gold_annotations=tuple(definitions),
        record_id=case.case_id,
        provenance=AnnotationProvenance(
            source_corpus="contemporary-annotation-pilot",
            source_record_id=case.case_id,
            adapter_identity="annotation-pilot",
            adapter_version=ANNOTATION_SCHEMA_VERSION,
            transformation_notes=(
                f"role={case.role}",
                f"article_group_id={case.article_group_id}",
                f"guideline_version={case.guideline_version}",
            ),
        ),
    )


def _annotation_metadata_note(case: AnnotationCase, label: AnnotationLabel) -> str:
    metadata = AnnotationProvenanceMetadata(
        relation_id=label.relation_id,
        origin=label.origin,
        status=label.status,
        annotator_id=label.annotator_id,
        suggestion_source=label.suggestion_source,
        phenomenon_tags=label.phenomenon_tags,
        revision=label.revision,
        history=label.history,
        note=label.note,
        article_group_id=case.article_group_id,
        guideline_version=case.guideline_version,
        resolver_identity=case.resolver_identity,
        source_path=case.source_path,
    )
    payload = json.dumps(
        metadata.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _ANNOTATION_METADATA_NOTE_PREFIX + payload


def annotation_metadata_from_provenance(
    provenance: AnnotationProvenance,
) -> AnnotationProvenanceMetadata | None:
    """Decode lossless T030 metadata from canonical provenance, when present."""

    encoded = [
        note.removeprefix(_ANNOTATION_METADATA_NOTE_PREFIX)
        for note in provenance.transformation_notes
        if note.startswith(_ANNOTATION_METADATA_NOTE_PREFIX)
    ]
    if not encoded:
        return None
    if len(encoded) != 1:
        raise AnnotationPilotError("canonical provenance has duplicate T030 metadata")
    try:
        return AnnotationProvenanceMetadata.model_validate_json(encoded[0])
    except ValueError as error:
        raise AnnotationPilotError(
            f"invalid canonical T030 provenance metadata: {error}"
        ) from error


def _text_for(case: AnnotationCase, span: TextSpan) -> str:
    span.validate_against(case.text)
    return case.text[span.start : span.end]


def read_annotation_pilot(path: Path) -> tuple[AnnotationCase, ...]:
    """Read a versioned JSON packet without network or resolver access."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AnnotationPilotError(
            f"Unable to read annotation pilot {path}: {error}"
        ) from error
    if (
        not isinstance(raw, Mapping)
        or raw.get("schema_version") != ANNOTATION_SCHEMA_VERSION
    ):
        raise AnnotationPilotError("unsupported annotation pilot schema")
    cases = raw.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, str | bytes):
        raise AnnotationPilotError("annotation pilot cases must be an array")
    try:
        result = tuple(AnnotationCase.model_validate(case) for case in cases)
    except (TypeError, ValueError) as error:
        raise AnnotationPilotError(f"invalid annotation case: {error}") from error
    if len({case.case_id for case in result}) != len(result):
        raise AnnotationPilotError("annotation case IDs must be unique")
    return result


def write_annotation_pilot(cases: Sequence[AnnotationCase], path: Path) -> str:
    """Write a deterministic annotation packet and return its fingerprint."""

    payload = {
        "schema_version": ANNOTATION_SCHEMA_VERSION,
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8", newline="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def select_review_packet(
    cases: Sequence[AnnotationCase], *, seed: int, max_cases: int
) -> tuple[AnnotationCase, ...]:
    """Select difficult/unresolved cases with a stable hash tie-breaker."""

    if max_cases < 1:
        raise ValueError("max_cases must be positive")
    difficult = {
        "ambiguous",
        "table",
        "caption",
        "rare-form",
        "overlap",
        "nested",
        "partial",
    }
    ranked = sorted(
        cases,
        key=lambda case: (
            not (
                any(label.status == "unresolved" for label in case.labels)
                or any(
                    tag in difficult
                    for label in case.labels
                    for tag in label.phenomenon_tags
                )
            ),
            hashlib.sha256(f"{seed}:{case.case_id}".encode()).hexdigest(),
        ),
    )
    return tuple(ranked[:max_cases])


def annotation_report(cases: Sequence[AnnotationCase]) -> dict[str, object]:
    """Summarize origin/status/phenomenon without calling labels human gold."""

    origins = Counter(label.origin for case in cases for label in case.labels)
    statuses = Counter(label.status for case in cases for label in case.labels)
    phenomena = Counter(
        tag for case in cases for label in case.labels for tag in label.phenomenon_tags
    )
    return {
        "schema_version": ANNOTATION_SCHEMA_VERSION,
        "case_count": len(cases),
        "evaluation_case_count": sum(case.role == "evaluation" for case in cases),
        "empty_definition_case_count": sum(not case.labels for case in cases),
        "origin_counts": dict(sorted(origins.items())),
        "status_counts": dict(sorted(statuses.items())),
        "phenomenon_counts": dict(sorted(phenomena.items())),
        "independent_label_count": origins["independent"],
        "assisted_label_count": origins["assisted"],
        "adjudicated_label_count": origins["adjudicated"],
        "unresolved_label_count": statuses["unresolved"],
        "evidence_status": "provisional_silver_pending_independent_review",
        "claims_allowed": False,
    }


def write_canonical_annotation_artifact(
    cases: Sequence[AnnotationCase], path: Path
) -> str:
    """Write imported cases as canonical JSONL, retaining incomplete labels."""

    serialized = "".join(
        json.dumps(
            record_to_dict(case_to_corpus_record(case)),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for case in cases
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8", newline="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_annotation_config(path: Path) -> AnnotationPilotConfig:
    """Load the ``annotation_pilot`` YAML section."""

    try:
        raw = load_config_layer(path)
        section = raw.get("annotation_pilot")
        if not isinstance(section, Mapping):
            raise AnnotationPilotError(
                "configuration must contain an 'annotation_pilot' mapping"
            )
        return AnnotationPilotConfig.model_validate(section)
    except AnnotationPilotError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise AnnotationPilotError(
            f"invalid annotation configuration: {error}"
        ) from error


def run_annotation_pilot(config: AnnotationPilotConfig) -> dict[str, object]:
    """Import a packet, emit canonical records/report, and optionally review cases."""

    cases = read_annotation_pilot(config.input_path)
    if any(case.guideline_version != config.guideline_version for case in cases):
        raise AnnotationPilotError(
            "case guideline version differs from configured version"
        )
    canonical_fingerprint = write_canonical_annotation_artifact(
        cases, config.canonical_output
    )
    report = annotation_report(cases)
    report["input_fingerprint"] = hashlib.sha256(
        config.input_path.read_bytes()
    ).hexdigest()
    report["canonical_fingerprint"] = canonical_fingerprint
    if config.review_packet_output is not None:
        review = select_review_packet(
            cases, seed=config.seed, max_cases=config.review_packet_size
        )
        report["review_packet_fingerprint"] = write_annotation_pilot(
            review, config.review_packet_output
        )
        report["review_packet_case_count"] = len(review)
    config.report_output.parent.mkdir(parents=True, exist_ok=True)
    config.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


__all__ = [
    "ANNOTATION_PROVENANCE_METADATA_VERSION",
    "ANNOTATION_SCHEMA_VERSION",
    "AdjudicationEvent",
    "AnnotationCase",
    "AnnotationLabel",
    "AnnotationPilotConfig",
    "AnnotationPilotError",
    "AnnotationProvenanceMetadata",
    "AnnotationSpan",
    "annotation_metadata_from_provenance",
    "annotation_report",
    "case_to_corpus_record",
    "load_annotation_config",
    "read_annotation_pilot",
    "run_annotation_pilot",
    "select_review_packet",
    "write_annotation_pilot",
    "write_canonical_annotation_artifact",
]
