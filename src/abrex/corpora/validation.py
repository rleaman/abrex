"""Validation and audit reporting for canonical corpus records.

Validation is deliberately separate from adapter parsing and from evaluation.
It can identify annotations that require a later scoring policy without making
that policy decision itself.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, cast

from abrex.corpora.diagnostics import AdapterDiagnostic, DiagnosticsSummary
from abrex.domain import AbbreviationDefinition, CorpusRecord

ValidationMode = Literal["strict", "permissive"]
ValidationSeverity = Literal["info", "warning", "error"]
ValidationAction = Literal[
    "observed", "repaired", "dropped", "ambiguous", "unscoreable"
]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One structured, location-aware canonical validation event."""

    severity: ValidationSeverity
    code: str
    message: str
    action: ValidationAction = "observed"
    record_id: str | None = None
    annotation_id: str | None = None
    location: str | None = None
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError(f"Unsupported validation severity: {self.severity!r}")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("Validation code must not be empty")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Validation message must not be empty")
        if self.action not in (
            "observed",
            "repaired",
            "dropped",
            "ambiguous",
            "unscoreable",
        ):
            raise ValueError(f"Unsupported validation action: {self.action!r}")
        for name, value in (
            ("record_id", self.record_id),
            ("annotation_id", self.annotation_id),
            ("location", self.location),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"Validation {name} must be a string or None")
        if not isinstance(self.details, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(part, str) for part in item)
            for item in self.details
        ):
            raise TypeError("Validation details must be a tuple of string pairs")

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
class ValidationSummary:
    """Immutable validation events and auditable action counts."""

    issues: tuple[ValidationIssue, ...] = ()
    records_seen: int = 0
    records_kept: int = 0

    def __post_init__(self) -> None:
        if any(not isinstance(issue, ValidationIssue) for issue in self.issues):
            raise TypeError("issues must contain ValidationIssue values")
        for name in ("records_seen", "records_kept"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.records_kept > self.records_seen:
            raise ValueError("records_kept must not exceed records_seen")

    @property
    def total(self) -> int:
        """Return the number of validation issues."""

        return len(self.issues)

    @property
    def records_dropped(self) -> int:
        """Return the number of records not retained by validation."""

        return self.records_seen - self.records_kept

    @property
    def repaired(self) -> int:
        """Return the number of explicitly reported repairs."""

        return self._count_action("repaired")

    @property
    def dropped(self) -> int:
        """Return the number of explicitly reported drops."""

        return self._count_action("dropped")

    @property
    def ambiguous(self) -> int:
        """Return the number of annotations needing ambiguity review."""

        return self._count_action("ambiguous")

    @property
    def unscoreable(self) -> int:
        """Return the number of annotations lacking complete scoreable spans."""

        return self._count_action("unscoreable")

    def _count_action(self, action: ValidationAction) -> int:
        return sum(issue.action == action for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic machine-readable summary data."""

        severity_counts = {
            severity: sum(issue.severity == severity for issue in self.issues)
            for severity in ("info", "warning", "error")
        }
        return {
            "total": self.total,
            "records_seen": self.records_seen,
            "records_kept": self.records_kept,
            "records_dropped": self.records_dropped,
            "by_severity": severity_counts,
            "by_action": {
                action: self._count_action(cast(ValidationAction, action))
                for action in (
                    "observed",
                    "repaired",
                    "dropped",
                    "ambiguous",
                    "unscoreable",
                )
            },
            "diagnostics": [issue.to_dict() for issue in self.issues],
        }

    def to_json(self) -> str:
        """Serialize the summary with stable formatting."""

        return (
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validated records paired with their immutable audit summary."""

    records: tuple[CorpusRecord, ...]
    summary: ValidationSummary


class CanonicalValidationError(ValueError):
    """Raised when strict canonical validation finds an error."""

    def __init__(self, message: str, summary: ValidationSummary) -> None:
        super().__init__(message)
        self.summary = summary


class CanonicalValidator:
    """Validate canonical records without applying evaluation policy."""

    def __init__(self, *, flag_overlaps: bool = True) -> None:
        self.flag_overlaps = flag_overlaps

    def validate(
        self,
        records: Iterable[CorpusRecord],
        *,
        mode: ValidationMode = "permissive",
        diagnostics: DiagnosticsSummary | Iterable[ValidationIssue] = (),
    ) -> ValidationResult:
        """Validate records, retaining valid rows in permissive mode.

        Existing adapter/normalizer diagnostics are carried into the report so
        repairs and drops remain visible in the canonical artifact manifest.
        """

        if mode not in ("strict", "permissive"):
            raise ValueError(f"Unsupported validation mode: {mode!r}")
        issues = _coerce_issues(diagnostics)
        initial_dropped_records = sum(
            issue.action == "dropped" and issue.location == "record" for issue in issues
        )
        source_records = tuple(records)
        valid: list[CorpusRecord] = []
        for record in source_records:
            try:
                if not isinstance(record, CorpusRecord):
                    raise TypeError("records must contain CorpusRecord values")
                record.validate()
                issues.extend(self._annotation_issues(record))
            except (TypeError, ValueError) as error:
                issues.append(
                    ValidationIssue(
                        "error",
                        "RECORD_INVALID",
                        str(error),
                        action="dropped",
                        record_id=(
                            record.id if isinstance(record, CorpusRecord) else None
                        ),
                        location="record",
                    )
                )
                continue
            valid.append(record)

        ordered = tuple(sorted(valid, key=_record_sort_key))
        summary = ValidationSummary(
            tuple(issues), len(source_records) + initial_dropped_records, len(ordered)
        )
        if mode == "strict" and any(issue.severity == "error" for issue in issues):
            raise CanonicalValidationError(
                "Strict canonical validation failed", summary
            )
        return ValidationResult(ordered, summary)

    def _annotation_issues(self, record: CorpusRecord) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        annotations = record.gold_annotations
        for index, annotation in enumerate(annotations):
            annotation_id = (
                annotation.provenance.source_annotation_id
                if annotation.provenance is not None
                else None
            )
            if annotation.short_form is None or annotation.long_form is None:
                issues.append(
                    ValidationIssue(
                        "warning",
                        "INCOMPLETE_ANNOTATION",
                        "Annotation lacks a short-form or long-form span",
                        action="unscoreable",
                        record_id=record.id,
                        annotation_id=annotation_id,
                        location=f"gold_annotations[{index}]",
                    )
                )

        if self.flag_overlaps:
            for left_index, left in enumerate(annotations):
                for right_index in range(left_index + 1, len(annotations)):
                    right = annotations[right_index]
                    if _definitions_overlap(left, right):
                        issues.append(
                            ValidationIssue(
                                "warning",
                                "OVERLAPPING_ANNOTATIONS",
                                (
                                    "Annotation spans overlap; scoring policy must "
                                    "decide handling"
                                ),
                                action="ambiguous",
                                record_id=record.id,
                                location=(
                                    f"gold_annotations[{left_index}],"
                                    f"gold_annotations[{right_index}]"
                                ),
                            )
                        )
        return issues


def _coerce_issues(
    diagnostics: DiagnosticsSummary | Iterable[ValidationIssue],
) -> list[ValidationIssue]:
    if isinstance(diagnostics, DiagnosticsSummary):
        return [
            ValidationIssue(
                item.severity,
                item.code,
                item.message,
                action=item.action,
                record_id=item.record_id,
                annotation_id=item.annotation_id,
                location=item.location,
                details=item.details,
            )
            for item in diagnostics.diagnostics
        ]
    return list(diagnostics)


def _definitions_overlap(
    left: AbbreviationDefinition, right: AbbreviationDefinition
) -> bool:
    left_spans = (left.short_form, left.long_form)
    right_spans = (right.short_form, right.long_form)
    return any(
        left_span is not None
        and right_span is not None
        and left_span.start < right_span.end
        and right_span.start < left_span.end
        for left_span in left_spans
        for right_span in right_spans
    )


def _record_sort_key(record: CorpusRecord) -> tuple[object, ...]:
    return (
        record.id,
        record.document.document_id,
        record.document.text,
        tuple(
            (
                annotation.short_form.start if annotation.short_form else None,
                annotation.short_form.end if annotation.short_form else None,
                annotation.long_form.start if annotation.long_form else None,
                annotation.long_form.end if annotation.long_form else None,
                annotation.provenance.source_annotation_id
                if annotation.provenance is not None
                else None,
            )
            for annotation in record.gold_annotations
        ),
    )


def validation_issue_from_diagnostic(diagnostic: AdapterDiagnostic) -> ValidationIssue:
    """Convert a T003 diagnostic into the T004 validation issue shape."""

    return ValidationIssue(
        diagnostic.severity,
        diagnostic.code,
        diagnostic.message,
        action=diagnostic.action,
        record_id=diagnostic.record_id,
        annotation_id=diagnostic.annotation_id,
        location=diagnostic.location,
        details=diagnostic.details,
    )


__all__ = [
    "CanonicalValidationError",
    "CanonicalValidator",
    "ValidationAction",
    "ValidationIssue",
    "ValidationMode",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationSummary",
    "validation_issue_from_diagnostic",
]
