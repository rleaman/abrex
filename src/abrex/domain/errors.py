"""Exceptions raised by the canonical abbreviation domain model."""

from __future__ import annotations


class DomainError(ValueError):
    """Base class for invalid canonical domain values."""


class InvalidSpanError(DomainError):
    """Raised when span coordinates violate the interval contract."""


class SpanValidationError(DomainError):
    """Raised when a span is not valid for a particular document or text."""


class InvalidAnnotationError(DomainError):
    """Raised when an abbreviation annotation violates domain invariants."""
