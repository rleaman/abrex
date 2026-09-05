"""Immutable reporting inputs and reporter extension contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from abrex.domain import Document
from abrex.evaluation import EvaluationResult, MatchOutcome


@dataclass(frozen=True, slots=True)
class ReportContext:
    """All immutable inputs needed to render one evaluation report.

    ``metadata`` and ``configuration`` are ordered key/value pairs so callers
    cannot mutate a report after construction.  Missing documents are allowed
    for machine-readable reports; HTML renders missing context explicitly.
    """

    evaluation: EvaluationResult
    documents: tuple[Document, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    configuration: tuple[tuple[str, object], ...] = ()
    dimensions: tuple[StratificationDimension, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation, EvaluationResult):
            raise TypeError("evaluation must be an EvaluationResult")
        if not isinstance(self.documents, tuple) or any(
            not isinstance(document, Document) for document in self.documents
        ):
            raise TypeError("documents must be a tuple of Document values")
        if len({document.document_id for document in self.documents}) != len(
            self.documents
        ):
            raise ValueError("documents must not contain duplicate document IDs")
        for name, values in (
            ("metadata", self.metadata),
            ("configuration", self.configuration),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                for item in values
            ):
                raise TypeError(f"{name} must be a tuple of key/value pairs")
            if len({item[0] for item in values}) != len(values):
                raise ValueError(f"{name} keys must be unique")
        if not isinstance(self.dimensions, tuple) or any(
            not isinstance(dimension, StratificationDimension)
            for dimension in self.dimensions
        ):
            raise TypeError("dimensions must contain StratificationDimension values")

    @property
    def document_map(self) -> Mapping[str, Document]:
        """Return a fresh read-only view of supplied document context."""

        return {document.document_id: document for document in self.documents}


@runtime_checkable
class StratificationDimension(Protocol):
    """Optional, explicit hook for grouping existing match outcomes."""

    @property
    def identity(self) -> str: ...

    def classify(self, document_id: str, outcome: MatchOutcome) -> str | None: ...


@runtime_checkable
class Reporter(Protocol):
    """Render an evaluation context without changing or recomputing it."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def render(self, context: ReportContext) -> str: ...

    def write(self, context: ReportContext, path: Path) -> None: ...


class ReportingError(ValueError):
    """Raised for invalid report inputs or output failures."""


__all__ = ["ReportContext", "Reporter", "ReportingError", "StratificationDimension"]
