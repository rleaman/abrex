"""Immutable, format-neutral value objects for abbreviation annotations.

The domain uses Unicode Python string character offsets and half-open
intervals, ``[start, end)``.  Source coordinates are kept in
:class:`SourceTextSpan` because source annotations may be incomplete or use a
coordinate space that is different from the canonical document.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from abrex.domain.errors import (
    InvalidAnnotationError,
    InvalidSpanError,
    SpanValidationError,
)


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_optional_text(value: str | None, field_name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return value


@dataclass(frozen=True, slots=True)
class TextSpan:
    """A canonical half-open character interval.

    ``start == end`` is intentionally valid.  Whether a zero-length span is
    meaningful for a corpus is a corpus/evaluation policy, not a property of
    interval arithmetic.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise TypeError("Span start must be an integer")
        if isinstance(self.end, bool) or not isinstance(self.end, int):
            raise TypeError("Span end must be an integer")
        if self.start < 0 or self.end < 0:
            raise InvalidSpanError("Span coordinates must be non-negative")
        if self.start > self.end:
            raise InvalidSpanError(
                f"Span start must not exceed end: {self.start}>{self.end}"
            )

    @property
    def length(self) -> int:
        """Return the number of characters covered by the span."""

        return self.end - self.start

    @property
    def is_zero_length(self) -> bool:
        """Return whether the span covers no characters."""

        return self.start == self.end

    def validate_against(self, text: str) -> None:
        """Raise if this span falls outside ``text``.

        The method does not normalize text or coordinates.  Callers that use
        a different coordinate space must preserve that fact in provenance.
        """

        if not isinstance(text, str):
            raise TypeError("Text must be a string")
        if self.end > len(text):
            raise SpanValidationError(
                f"Span [{self.start}, {self.end}) exceeds text length {len(text)}"
            )


@dataclass(frozen=True, slots=True)
class Document:
    """Canonical document text identified by an explicit stable identifier."""

    document_id: str
    text: str

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")

    @property
    def id(self) -> str:
        """Return the stable document identifier.

        ``document_id`` remains the canonical field name; this alias keeps
        call sites that use the general domain notion of an ID readable.
        """

        return self.document_id

    def validate_span(self, span: TextSpan, expected_text: str | None = None) -> None:
        """Validate a span's bounds and, optionally, its captured text."""

        if not isinstance(span, TextSpan):
            raise TypeError("span must be a TextSpan")
        span.validate_against(self.text)
        if expected_text is not None:
            _require_optional_text(expected_text, "expected_text")
            actual_text = self.text[span.start : span.end]
            if actual_text != expected_text:
                raise SpanValidationError(
                    f"Text mismatch for span [{span.start}, {span.end}): "
                    f"expected {expected_text!r}, got {actual_text!r}"
                )

    def text_for(self, span: TextSpan) -> str:
        """Return the canonical text covered by ``span`` after validation."""

        self.validate_span(span)
        return self.text[span.start : span.end]

    def validate_definition(self, definition: AbbreviationDefinition) -> None:
        """Validate an annotation against this document's ID, text, and bounds."""

        definition.validate_against(self)


@dataclass(frozen=True, slots=True)
class SourceTextSpan:
    """Source-space text and optional coordinates retained in provenance.

    A source may provide text without coordinates, coordinates without text,
    or both.  Coordinates are therefore optional, but one coordinate cannot
    be supplied without the other.  No canonical coordinate is inferred from
    source text.
    """

    start: int | None = None
    end: int | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        if (self.start is None) != (self.end is None):
            raise ValueError("Source start and end must both be present or absent")
        if self.start is not None and (
            isinstance(self.start, bool) or not isinstance(self.start, int)
        ):
            raise TypeError("Source start must be an integer or None")
        if self.end is not None and (
            isinstance(self.end, bool) or not isinstance(self.end, int)
        ):
            raise TypeError("Source end must be an integer or None")
        if self.start is not None and self.start < 0:
            raise InvalidSpanError("Source span coordinates must be non-negative")
        if self.end is not None and self.end < 0:
            raise InvalidSpanError("Source span coordinates must be non-negative")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise InvalidSpanError(
                f"Source span start must not exceed end: {self.start}>{self.end}"
            )
        _require_optional_text(self.text, "text")

    @property
    def has_coordinates(self) -> bool:
        """Return whether source coordinates were actually supplied."""

        return self.start is not None


@dataclass(frozen=True, slots=True)
class AnnotationProvenance:
    """Traceability information for one canonical annotation.

    ``original_short_form`` and ``original_long_form`` preserve source facts
    independently of canonical spans.  ``transformation_notes`` is an
    ordered, immutable record of adapter/normalization actions; it carries no
    implicit policy about whether those actions are scientifically valid.
    """

    source_corpus: str | None = None
    source_record_id: str | None = None
    source_annotation_id: str | None = None
    original_short_form: SourceTextSpan | None = None
    original_long_form: SourceTextSpan | None = None
    adapter_identity: str | None = None
    adapter_version: str | None = None
    transformation_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "source_corpus",
            "source_record_id",
            "source_annotation_id",
            "adapter_identity",
            "adapter_version",
        ):
            _require_optional_text(getattr(self, field_name), field_name)
        if not isinstance(self.transformation_notes, tuple):
            raise TypeError("transformation_notes must be a tuple of strings")
        if any(not isinstance(note, str) for note in self.transformation_notes):
            raise TypeError("transformation_notes must be a tuple of strings")


@dataclass(frozen=True, slots=True)
class PredictionMetadata:
    """Metadata attached only to a resolver prediction.

    Confidence, when provided, is an optional unit-interval value.  Arbitrary
    resolver scores belong in ``score`` and are deliberately not interpreted
    by this domain model.
    """

    confidence: float | None = None
    score: float | None = None
    component: str | None = None
    component_version: str | None = None
    model_artifact_fingerprint: str | None = None
    feature_config_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                self.confidence, int | float
            ):
                raise TypeError("confidence must be a real number or None")
            if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
                raise ValueError("confidence must be finite and between 0 and 1")
        if self.score is not None:
            if isinstance(self.score, bool) or not isinstance(self.score, int | float):
                raise TypeError("score must be a real number or None")
            if not math.isfinite(self.score):
                raise ValueError("score must be finite")
        for field_name in (
            "component",
            "component_version",
            "model_artifact_fingerprint",
            "feature_config_fingerprint",
        ):
            _require_optional_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class AbbreviationDefinition:
    """A short-form/long-form pair in canonical document coordinates.

    Either form may be incomplete: its span and/or captured text may be
    absent when the source did not provide that information.  Missing values
    remain ``None`` and are never inferred by this object.  A definition with
    prediction metadata is a prediction; gold/source semantics are kept in
    the other fields and are not mixed with resolver metadata.
    """

    document_id: str
    short_form: TextSpan | None = None
    long_form: TextSpan | None = None
    short_form_text: str | None = None
    long_form_text: str | None = None
    provenance: AnnotationProvenance | None = None
    prediction: PredictionMetadata | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        if self.short_form is not None and not isinstance(self.short_form, TextSpan):
            raise TypeError("short_form must be a TextSpan or None")
        if self.long_form is not None and not isinstance(self.long_form, TextSpan):
            raise TypeError("long_form must be a TextSpan or None")
        if self.provenance is not None and not isinstance(
            self.provenance, AnnotationProvenance
        ):
            raise TypeError("provenance must be an AnnotationProvenance or None")
        if self.prediction is not None and not isinstance(
            self.prediction, PredictionMetadata
        ):
            raise TypeError("prediction must be a PredictionMetadata or None")
        _require_optional_text(self.short_form_text, "short_form_text")
        _require_optional_text(self.long_form_text, "long_form_text")

    @property
    def confidence(self) -> float | None:
        """Return prediction confidence without storing it in gold semantics."""

        return self.prediction.confidence if self.prediction is not None else None

    @property
    def is_prediction(self) -> bool:
        """Return whether resolver-specific metadata is attached."""

        return self.prediction is not None

    def validate_against(self, document: Document) -> None:
        """Validate document identity, span bounds, and any captured text."""

        if not isinstance(document, Document):
            raise TypeError("document must be a Document")
        if self.document_id != document.document_id:
            raise InvalidAnnotationError(
                f"Definition document ID {self.document_id!r} does not match "
                f"document ID {document.document_id!r}"
            )
        if self.short_form is not None:
            document.validate_span(self.short_form, self.short_form_text)
        if self.long_form is not None:
            document.validate_span(self.long_form, self.long_form_text)


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    """Canonical evaluation record containing one document and gold annotations."""

    document: Document
    gold_annotations: tuple[AbbreviationDefinition, ...] = ()
    record_id: str | None = None
    provenance: AnnotationProvenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document, Document):
            raise TypeError("document must be a Document")
        raw_annotations: object = self.gold_annotations
        if not isinstance(raw_annotations, Sequence) or isinstance(
            raw_annotations, str | bytes
        ):
            raise TypeError("gold_annotations must be a sequence of definitions")
        annotations = tuple(raw_annotations)
        if any(not isinstance(item, AbbreviationDefinition) for item in annotations):
            raise TypeError(
                "gold_annotations must contain AbbreviationDefinition values"
            )
        for annotation in annotations:
            if annotation.document_id != self.document.document_id:
                raise InvalidAnnotationError(
                    f"Gold annotation document ID {annotation.document_id!r} does not "
                    f"match document ID {self.document.document_id!r}"
                )
        object.__setattr__(self, "gold_annotations", annotations)
        if self.record_id is not None:
            _require_non_empty(self.record_id, "record_id")
        if self.provenance is not None and not isinstance(
            self.provenance, AnnotationProvenance
        ):
            raise TypeError("provenance must be an AnnotationProvenance or None")

    @property
    def id(self) -> str:
        """Return the record identifier, falling back to the document ID."""

        return (
            self.record_id if self.record_id is not None else self.document.document_id
        )

    def validate(self) -> None:
        """Validate all contained annotations against the canonical document."""

        for annotation in self.gold_annotations:
            annotation.validate_against(self.document)
