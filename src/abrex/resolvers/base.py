"""Domain-facing resolver contracts and immutable execution values."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from abrex.domain import AbbreviationDefinition, Document, PredictionMetadata

PredictionValidationMode = Literal["strict", "permissive"]
ExecutionErrorPolicy = Literal["raise", "collect"]
DiagnosticSeverity = Literal["info", "warning", "error"]
DiagnosticAction = Literal["observed", "dropped"]


class ResolverError(ValueError):
    """Base class for resolver construction and execution failures."""


class ResolverExecutionError(ResolverError):
    """A resolver failed for a specific document or execution phase."""

    def __init__(
        self,
        message: str,
        *,
        resolver_key: str,
        document_id: str | None,
        phase: Literal["input", "resolve", "materialize"],
        cause: BaseException | None = None,
    ) -> None:
        self.resolver_key = resolver_key
        self.document_id = document_id
        self.phase = phase
        self.cause_type = type(cause).__name__ if cause is not None else None
        self.cause = cause
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ResolverMetadata:
    """Stable identity of the selected resolver implementation."""

    key: str
    implementation_version: str

    def __post_init__(self) -> None:
        for name in ("key", "implementation_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Resolver {name} must not be empty")

    @property
    def version(self) -> str:
        """Return the implementation version using the short public name."""

        return self.implementation_version

    @property
    def stable_key(self) -> str:
        """Return the registry key using an explicit metadata-oriented name."""

        return self.key


@dataclass(frozen=True, slots=True)
class PredictionDiagnostic:
    """One observable validation or execution event for a prediction run."""

    severity: DiagnosticSeverity
    code: str
    message: str
    document_id: str
    action: DiagnosticAction = "observed"
    prediction_index: int | None = None
    phase: str | None = None
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError(f"Unsupported diagnostic severity: {self.severity!r}")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("Prediction diagnostic code must not be empty")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Prediction diagnostic message must not be empty")
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Prediction diagnostic document_id must not be empty")
        if self.action not in ("observed", "dropped"):
            raise ValueError(f"Unsupported diagnostic action: {self.action!r}")
        if self.prediction_index is not None and (
            isinstance(self.prediction_index, bool)
            or not isinstance(self.prediction_index, int)
            or self.prediction_index < 0
        ):
            raise ValueError("prediction_index must be a non-negative integer or None")
        if self.phase is not None and not isinstance(self.phase, str):
            raise TypeError("phase must be a string or None")
        if not isinstance(self.details, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(part, str) for part in item)
            for item in self.details
        ):
            raise TypeError("details must be a tuple of string pairs")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible diagnostic mapping."""

        result: dict[str, object] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "document_id": self.document_id,
            "action": self.action,
        }
        if self.prediction_index is not None:
            result["prediction_index"] = self.prediction_index
        if self.phase is not None:
            result["phase"] = self.phase
        if self.details:
            result["details"] = dict(self.details)
        return result


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    """Predictions and diagnostics associated with one canonical document."""

    document_id: str
    predictions: tuple[AbbreviationDefinition, ...] = ()
    diagnostics: tuple[PredictionDiagnostic, ...] = ()
    record_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Prediction document_id must not be empty")
        if not isinstance(self.predictions, tuple) or any(
            not isinstance(item, AbbreviationDefinition) for item in self.predictions
        ):
            raise TypeError("predictions must be a tuple of AbbreviationDefinition")
        if not isinstance(self.diagnostics, tuple) or any(
            not isinstance(item, PredictionDiagnostic) for item in self.diagnostics
        ):
            raise TypeError("diagnostics must be a tuple of PredictionDiagnostic")
        if self.record_id is not None and (
            not isinstance(self.record_id, str) or not self.record_id.strip()
        ):
            raise ValueError("record_id must be a non-empty string or None")


@dataclass(frozen=True, slots=True)
class PredictionValidationResult:
    """Validated predictions plus every invalid-output diagnostic."""

    predictions: tuple[AbbreviationDefinition, ...]
    diagnostics: tuple[PredictionDiagnostic, ...]
    predictions_seen: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.predictions_seen, bool)
            or not isinstance(self.predictions_seen, int)
            or self.predictions_seen < 0
        ):
            raise ValueError("predictions_seen must be a non-negative integer")
        if self.predictions_seen < len(self.predictions):
            raise ValueError("predictions_seen must include retained predictions")


@dataclass(frozen=True, slots=True)
class ResolverRunResult:
    """Batch resolver output with immutable records and execution failures."""

    resolver: ResolverMetadata
    records: tuple[PredictionRecord, ...]
    execution_errors: tuple[ResolverExecutionError, ...] = ()

    @property
    def diagnostics(self) -> tuple[PredictionDiagnostic, ...]:
        """Return diagnostics in document execution order."""

        return tuple(
            diagnostic for record in self.records for diagnostic in record.diagnostics
        )


@runtime_checkable
class Resolver(Protocol):
    """Interchangeable resolver contract over canonical document text.

    Implementations must read ``document.text`` as supplied. Text
    normalization and coordinate remapping are outside this interface.
    """

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Return zero or more predictions in canonical document coordinates."""


class PredictionValidationError(ResolverError):
    """Raised when strict prediction validation finds an invalid output."""

    def __init__(
        self,
        message: str,
        *,
        document_id: str,
        result: PredictionValidationResult,
    ) -> None:
        self.document_id = document_id
        self.result = result
        super().__init__(message)


def attach_resolver_metadata(
    prediction: AbbreviationDefinition, metadata: ResolverMetadata
) -> AbbreviationDefinition:
    """Return a prediction carrying the selected resolver's metadata.

    Existing confidence and arbitrary score values are preserved. The
    execution service owns component identity, so stale component labels from
    a resolver are replaced with the selected registry key and version.
    """

    from dataclasses import replace

    current = prediction.prediction
    prediction_metadata = PredictionMetadata(
        confidence=current.confidence if current is not None else None,
        score=current.score if current is not None else None,
        component=metadata.key,
        component_version=metadata.implementation_version,
    )
    return replace(prediction, prediction=prediction_metadata)


__all__ = [
    "DiagnosticAction",
    "DiagnosticSeverity",
    "ExecutionErrorPolicy",
    "PredictionDiagnostic",
    "PredictionRecord",
    "PredictionValidationError",
    "PredictionValidationMode",
    "PredictionValidationResult",
    "Resolver",
    "ResolverError",
    "ResolverExecutionError",
    "ResolverMetadata",
    "ResolverRunResult",
    "attach_resolver_metadata",
]
