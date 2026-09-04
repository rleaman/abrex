"""Canonical scientific domain objects for abbreviation resolution."""

from abrex.domain.errors import (
    DomainError,
    InvalidAnnotationError,
    InvalidSpanError,
    SpanValidationError,
)
from abrex.domain.models import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)

__all__ = [
    "AbbreviationDefinition",
    "AnnotationProvenance",
    "CorpusRecord",
    "Document",
    "DomainError",
    "InvalidAnnotationError",
    "InvalidSpanError",
    "PredictionMetadata",
    "SourceTextSpan",
    "SpanValidationError",
    "TextSpan",
]
