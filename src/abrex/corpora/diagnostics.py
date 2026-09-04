"""Structured diagnostics emitted while building canonical corpus records."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Literal

DiagnosticAction = Literal["observed", "repaired", "dropped"]
DiagnosticSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class AdapterDiagnostic:
    """One observable adapter, normalization, or validation event."""

    severity: DiagnosticSeverity
    code: str
    message: str
    action: DiagnosticAction = "observed"
    record_id: str | None = None
    annotation_id: str | None = None
    location: str | None = None
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError(f"Unsupported diagnostic severity: {self.severity!r}")
        if not self.code.strip():
            raise ValueError("Diagnostic code must not be empty")
        if not self.message.strip():
            raise ValueError("Diagnostic message must not be empty")
        if self.action not in ("observed", "repaired", "dropped"):
            raise ValueError(f"Unsupported diagnostic action: {self.action!r}")
        for name, value in (
            ("record_id", self.record_id),
            ("annotation_id", self.annotation_id),
            ("location", self.location),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"Diagnostic {name} must be a string or None")
        if not isinstance(self.details, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(part, str) for part in item)
            for item in self.details
        ):
            raise TypeError("Diagnostic details must be a tuple of string pairs")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""

        result: dict[str, object] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "action": self.action,
        }
        if self.record_id is not None:
            result["record_id"] = self.record_id
        if self.annotation_id is not None:
            result["annotation_id"] = self.annotation_id
        if self.location is not None:
            result["location"] = self.location
        if self.details:
            result["details"] = dict(self.details)
        return result


@dataclass(frozen=True, slots=True)
class DiagnosticsSummary:
    """Immutable diagnostics and deterministic aggregate counts."""

    diagnostics: tuple[AdapterDiagnostic, ...] = ()

    @property
    def total(self) -> int:
        """Return the number of emitted diagnostics."""

        return len(self.diagnostics)

    def to_dict(self) -> dict[str, object]:
        """Return counts and the underlying events in machine-readable form."""

        severity_counts = Counter(item.severity for item in self.diagnostics)
        action_counts = Counter(item.action for item in self.diagnostics)
        return {
            "total": self.total,
            "by_severity": {
                "info": severity_counts["info"],
                "warning": severity_counts["warning"],
                "error": severity_counts["error"],
            },
            "by_action": {
                "observed": action_counts["observed"],
                "repaired": action_counts["repaired"],
                "dropped": action_counts["dropped"],
            },
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def to_json(self) -> str:
        """Serialize the summary deterministically as JSON."""

        return (
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


class DiagnosticsCollector:
    """Mutable, per-build collector used by adapters and normalizers."""

    def __init__(self) -> None:
        self._diagnostics: list[AdapterDiagnostic] = []

    @property
    def diagnostics(self) -> tuple[AdapterDiagnostic, ...]:
        """Return events in emission order."""

        return tuple(self._diagnostics)

    def add(
        self,
        severity: DiagnosticSeverity,
        code: str,
        message: str,
        *,
        action: DiagnosticAction = "observed",
        record_id: str | None = None,
        annotation_id: str | None = None,
        location: str | None = None,
        details: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """Append one diagnostic event."""

        self._diagnostics.append(
            AdapterDiagnostic(
                severity=severity,
                code=code,
                message=message,
                action=action,
                record_id=record_id,
                annotation_id=annotation_id,
                location=location,
                details=details,
            )
        )

    def extend(self, diagnostics: tuple[AdapterDiagnostic, ...]) -> None:
        """Append already-constructed diagnostic events."""

        self._diagnostics.extend(diagnostics)

    def summary(self) -> DiagnosticsSummary:
        """Freeze the current events into an immutable summary."""

        return DiagnosticsSummary(self.diagnostics)
