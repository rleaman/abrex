"""Candidate-generation contracts and immutable analysis values."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from abrex.domain import AnnotationProvenance, Document, TextSpan

CandidateDiagnosticSeverity = Literal["info", "warning", "error"]
CandidateDiagnosticAction = Literal["observed", "pruned"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A plausible short/long span pair before acceptance or scoring."""

    document_id: str
    short_form: TextSpan
    long_form: TextSpan
    construction: str
    provenance: AnnotationProvenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Candidate document_id must not be empty")
        if not isinstance(self.short_form, TextSpan):
            raise TypeError("Candidate short_form must be a TextSpan")
        if not isinstance(self.long_form, TextSpan):
            raise TypeError("Candidate long_form must be a TextSpan")
        if not isinstance(self.construction, str) or not self.construction.strip():
            raise ValueError("Candidate construction must not be empty")
        if self.provenance is not None and not isinstance(
            self.provenance, AnnotationProvenance
        ):
            raise TypeError("Candidate provenance must be AnnotationProvenance or None")

    def validate_against(self, document: Document) -> None:
        """Validate document identity and both canonical spans."""

        if self.document_id != document.document_id:
            raise ValueError("Candidate document_id does not match document")
        self.short_form.validate_against(document.text)
        self.long_form.validate_against(document.text)


@dataclass(frozen=True, slots=True)
class CandidateDiagnostic:
    """An auditable observation or reason a possible candidate was pruned."""

    severity: CandidateDiagnosticSeverity
    code: str
    message: str
    document_id: str
    action: CandidateDiagnosticAction
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError("Invalid candidate diagnostic severity")
        if self.action not in ("observed", "pruned"):
            raise ValueError("Invalid candidate diagnostic action")
        for name in ("code", "message", "document_id"):
            if (
                not isinstance(getattr(self, name), str)
                or not getattr(self, name).strip()
            ):
                raise ValueError(f"Candidate diagnostic {name} must not be empty")
        if not isinstance(self.details, tuple) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.details
        ):
            raise TypeError("Candidate diagnostic details must be tuple[str, str]")


@dataclass(frozen=True, slots=True)
class CandidateGenerationResult:
    """Candidates and diagnostics produced for one canonical document."""

    document_id: str
    candidates: tuple[Candidate, ...] = ()
    diagnostics: tuple[CandidateDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Candidate result document_id must not be empty")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(item, Candidate) for item in self.candidates
        ):
            raise TypeError("candidates must be a tuple of Candidate values")
        if not isinstance(self.diagnostics, tuple) or any(
            not isinstance(item, CandidateDiagnostic) for item in self.diagnostics
        ):
            raise TypeError("diagnostics must be a tuple of CandidateDiagnostic values")


class CandidateGenerator(Protocol):
    """Interchangeable candidate enumerator over canonical documents."""

    identity: str
    version: str

    def generate(self, document: Document) -> CandidateGenerationResult:
        """Enumerate plausible pairs without accepting or scoring them."""


@dataclass(frozen=True, slots=True)
class CandidateGeneratorMetadata:
    """Stable identity for one or more generators used in an artifact."""

    components: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.components or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(version, str)
            or not version.strip()
            for key, version in self.components
        ):
            raise ValueError("Candidate generator metadata must be non-empty")


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """Serialized unit of candidate analysis for one document."""

    document_id: str
    candidates: tuple[Candidate, ...] = ()
    diagnostics: tuple[CandidateDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        result = CandidateGenerationResult(
            self.document_id, self.candidates, self.diagnostics
        )
        if any(item.document_id != self.document_id for item in result.candidates):
            raise ValueError("Candidate document IDs must match their record")
        if any(item.document_id != self.document_id for item in result.diagnostics):
            raise ValueError(
                "Candidate diagnostic document IDs must match their record"
            )
        object.__setattr__(self, "candidates", result.candidates)
        object.__setattr__(self, "diagnostics", result.diagnostics)


@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    """Immutable candidate-generation output suitable for serialization."""

    generators: CandidateGeneratorMetadata
    records: tuple[CandidateRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.generators, CandidateGeneratorMetadata):
            raise TypeError("generators must be CandidateGeneratorMetadata")
        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple")
        identifiers = [record.document_id for record in self.records]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Candidate artifact contains duplicate document IDs")


class CandidatePipeline(Protocol):
    """Protocol for a configured multi-generator candidate pipeline."""

    def generate(self, document: Document) -> CandidateRecord:
        """Generate and combine candidates for one document."""

    def generate_documents(
        self, documents: Iterable[Document]
    ) -> tuple[CandidateRecord, ...]:
        """Generate deterministic records for an iterable of documents."""


__all__ = [
    "Candidate",
    "CandidateArtifact",
    "CandidateDiagnostic",
    "CandidateDiagnosticAction",
    "CandidateDiagnosticSeverity",
    "CandidateGenerationResult",
    "CandidateGenerator",
    "CandidateGeneratorMetadata",
    "CandidatePipeline",
    "CandidateRecord",
]
