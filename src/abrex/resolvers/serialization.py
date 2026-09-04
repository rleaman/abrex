"""Versioned prediction artifacts, separate from canonical gold artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)
from abrex.resolvers.base import (
    PredictionDiagnostic,
    PredictionRecord,
    ResolverMetadata,
    ResolverRunResult,
)

PREDICTION_SCHEMA_VERSION = "predictions-v1"


class PredictionSerializationError(ValueError):
    """Raised when a prediction artifact cannot be written or parsed."""


@dataclass(frozen=True, slots=True)
class PredictionArtifact:
    """Immutable prediction records and the resolver that produced them."""

    resolver: ResolverMetadata
    records: tuple[PredictionRecord, ...]
    schema_version: str = PREDICTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.resolver, ResolverMetadata):
            raise TypeError("resolver must be ResolverMetadata")
        if not isinstance(self.records, tuple) or any(
            not isinstance(record, PredictionRecord) for record in self.records
        ):
            raise TypeError("records must be a tuple of PredictionRecord values")
        if self.schema_version != PREDICTION_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported prediction schema version: {self.schema_version!r}"
            )

    @classmethod
    def from_run(cls, result: ResolverRunResult) -> PredictionArtifact:
        """Create an artifact value from an executor result."""

        records = tuple(
            sorted(
                (
                    replace(
                        record,
                        predictions=_ordered_predictions(record.predictions),
                    )
                    for record in result.records
                ),
                key=_record_sort_key,
            )
        )
        return cls(result.resolver, records)

    def to_json(self) -> str:
        """Return deterministic newline-delimited prediction records."""

        return serialize_prediction_artifact(self)


def prediction_record_to_dict(
    record: PredictionRecord, resolver: ResolverMetadata
) -> dict[str, object]:
    """Convert one prediction record to its versioned artifact mapping."""

    if not isinstance(record, PredictionRecord):
        raise TypeError("record must be a PredictionRecord")
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "resolver": {
            "key": resolver.key,
            "version": resolver.implementation_version,
        },
        "record_id": record.record_id,
        "document_id": record.document_id,
        "predictions": [
            _definition_to_dict(prediction)
            for prediction in _ordered_predictions(record.predictions)
        ],
        "diagnostics": [diagnostic.to_dict() for diagnostic in record.diagnostics],
    }


def prediction_record_from_dict(
    data: Mapping[str, object], *, line_number: int | None = None
) -> tuple[ResolverMetadata, PredictionRecord]:
    """Parse one prediction record and its resolver metadata."""

    location = f" at line {line_number}" if line_number is not None else ""
    try:
        if data.get("schema_version") != PREDICTION_SCHEMA_VERSION:
            raise PredictionSerializationError(
                f"Unsupported prediction schema version{location}: "
                f"{data.get('schema_version')!r}"
            )
        resolver_data = _mapping_value(data.get("resolver"), "resolver")
        resolver = ResolverMetadata(
            _string(resolver_data, "key"), _string(resolver_data, "version")
        )
        document_id = _string(data, "document_id")
        raw_predictions = data.get("predictions", [])
        if not isinstance(raw_predictions, list):
            raise TypeError("predictions must be a JSON array")
        predictions = tuple(
            _definition_from_dict(_mapping_value(item, "prediction"))
            for item in raw_predictions
        )
        raw_diagnostics = data.get("diagnostics", [])
        if not isinstance(raw_diagnostics, list):
            raise TypeError("diagnostics must be a JSON array")
        diagnostics = tuple(
            _diagnostic_from_dict(_mapping_value(item, "diagnostic"))
            for item in raw_diagnostics
        )
        record_id = data.get("record_id")
        if record_id is not None and not isinstance(record_id, str):
            raise TypeError("record_id must be a string or null")
        record = PredictionRecord(
            document_id,
            predictions=predictions,
            diagnostics=diagnostics,
            record_id=record_id,
        )
        for prediction in predictions:
            if prediction.document_id != document_id:
                raise ValueError("prediction document ID does not match record")
        return resolver, record
    except PredictionSerializationError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise PredictionSerializationError(
            f"Invalid prediction record{location}: {error}"
        ) from error


def serialize_prediction_artifact(artifact: PredictionArtifact) -> str:
    """Serialize prediction records deterministically without gold fields."""

    if not isinstance(artifact, PredictionArtifact):
        raise TypeError("artifact must be a PredictionArtifact")
    ordered = sorted(artifact.records, key=_record_sort_key)
    return "".join(
        _json_line(prediction_record_to_dict(record, artifact.resolver))
        for record in ordered
    )


def prediction_artifact_from_run(result: ResolverRunResult) -> PredictionArtifact:
    """Convert executor output into the serializable prediction artifact."""

    return PredictionArtifact.from_run(result)


def write_prediction_artifact(
    artifact_or_result: PredictionArtifact | ResolverRunResult, path: Path
) -> str:
    """Write a prediction JSONL artifact and return its SHA-256 fingerprint."""

    artifact = (
        artifact_or_result
        if isinstance(artifact_or_result, PredictionArtifact)
        else PredictionArtifact.from_run(artifact_or_result)
    )
    content = serialize_prediction_artifact(artifact)
    try:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except OSError as error:
        raise PredictionSerializationError(
            f"Unable to write prediction artifact {path}: {error}"
        ) from error
    return _fingerprint(content.encode("utf-8"))


def read_prediction_artifact(
    path: Path, *, documents: Mapping[str, Document] | None = None
) -> PredictionArtifact:
    """Read a prediction artifact and optionally validate spans against documents."""

    try:
        with path.open("r", encoding="utf-8", newline=None) as stream:
            lines = tuple(stream)
    except (OSError, UnicodeError) as error:
        raise PredictionSerializationError(
            f"Unable to read prediction artifact {path}: {error}"
        ) from error
    if not lines:
        raise PredictionSerializationError("Prediction artifact must contain a record")
    parsed: list[PredictionRecord] = []
    resolver: ResolverMetadata | None = None
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise PredictionSerializationError(
                f"Invalid prediction JSONL at line {line_number}: blank line"
            )
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise PredictionSerializationError(
                f"Invalid JSON at line {line_number}: {error.msg}"
            ) from error
        if not isinstance(data, dict):
            raise PredictionSerializationError(
                f"Invalid prediction JSONL at line {line_number}: object required"
            )
        line_resolver, record = prediction_record_from_dict(
            cast(Mapping[str, object], data), line_number=line_number
        )
        if resolver is None:
            resolver = line_resolver
        elif resolver != line_resolver:
            raise PredictionSerializationError(
                f"Inconsistent resolver metadata at line {line_number}"
            )
        if documents is not None:
            document = documents.get(record.document_id)
            if document is None:
                raise PredictionSerializationError(
                    f"No canonical document supplied for {record.document_id!r}"
                )
            for prediction in record.predictions:
                try:
                    prediction.validate_against(document)
                except (TypeError, ValueError) as error:
                    raise PredictionSerializationError(
                        f"Invalid prediction for {record.document_id!r}: {error}"
                    ) from error
        parsed.append(record)
    assert resolver is not None
    return PredictionArtifact(resolver, tuple(parsed))


def fingerprint_prediction_artifact(artifact: PredictionArtifact) -> str:
    """Return a path-independent fingerprint of serialized predictions."""

    return _fingerprint(serialize_prediction_artifact(artifact).encode("utf-8"))


def serialize_predictions(artifact: PredictionArtifact) -> str:
    """Compatibility-oriented short alias for artifact serialization."""

    return serialize_prediction_artifact(artifact)


def write_predictions(
    artifact_or_result: PredictionArtifact | ResolverRunResult, path: Path
) -> str:
    """Short alias for :func:`write_prediction_artifact`."""

    return write_prediction_artifact(artifact_or_result, path)


def read_predictions(
    path: Path, *, documents: Mapping[str, Document] | None = None
) -> PredictionArtifact:
    """Short alias for :func:`read_prediction_artifact`."""

    return read_prediction_artifact(path, documents=documents)


def _definition_to_dict(annotation: AbbreviationDefinition) -> dict[str, object]:
    return {
        "document_id": annotation.document_id,
        "short_form": _span_to_dict(annotation.short_form),
        "long_form": _span_to_dict(annotation.long_form),
        "short_form_text": annotation.short_form_text,
        "long_form_text": annotation.long_form_text,
        "provenance": _provenance_to_dict(annotation.provenance),
        "prediction": _prediction_to_dict(annotation.prediction),
    }


def _definition_from_dict(data: Mapping[str, object]) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        document_id=_string(data, "document_id"),
        short_form=_span_from_dict(data.get("short_form")),
        long_form=_span_from_dict(data.get("long_form")),
        short_form_text=_optional_string(data, "short_form_text"),
        long_form_text=_optional_string(data, "long_form_text"),
        provenance=_provenance_from_dict(data.get("provenance")),
        prediction=_prediction_from_dict(data.get("prediction")),
    )


def _diagnostic_from_dict(data: Mapping[str, object]) -> PredictionDiagnostic:
    raw_details = data.get("details", {})
    if not isinstance(raw_details, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in raw_details.items()
    ):
        raise TypeError("diagnostic details must be a JSON object of strings")
    index = data.get("prediction_index")
    if index is not None and (isinstance(index, bool) or not isinstance(index, int)):
        raise TypeError("prediction_index must be an integer or null")
    phase = data.get("phase")
    if phase is not None and not isinstance(phase, str):
        raise TypeError("phase must be a string or null")
    return PredictionDiagnostic(
        severity=cast(Any, _string(data, "severity")),
        code=_string(data, "code"),
        message=_string(data, "message"),
        document_id=_string(data, "document_id"),
        action=cast(Any, _string(data, "action")),
        prediction_index=index,
        phase=phase,
        details=tuple(sorted(raw_details.items())),
    )


def _span_to_dict(span: TextSpan | None) -> dict[str, int] | None:
    return None if span is None else {"start": span.start, "end": span.end}


def _span_from_dict(data: object) -> TextSpan | None:
    if data is None:
        return None
    mapping = _mapping_value(data, "span")
    return TextSpan(_int(mapping, "start"), _int(mapping, "end"))


def _source_span_to_dict(span: SourceTextSpan | None) -> dict[str, object] | None:
    if span is None:
        return None
    return {"start": span.start, "end": span.end, "text": span.text}


def _source_span_from_dict(data: object) -> SourceTextSpan | None:
    if data is None:
        return None
    mapping = _mapping_value(data, "source span")
    return SourceTextSpan(
        start=_optional_int(mapping, "start"),
        end=_optional_int(mapping, "end"),
        text=_optional_string(mapping, "text"),
    )


def _provenance_to_dict(
    provenance: AnnotationProvenance | None,
) -> dict[str, object] | None:
    if provenance is None:
        return None
    return {
        "source_corpus": provenance.source_corpus,
        "source_record_id": provenance.source_record_id,
        "source_annotation_id": provenance.source_annotation_id,
        "original_short_form": _source_span_to_dict(provenance.original_short_form),
        "original_long_form": _source_span_to_dict(provenance.original_long_form),
        "adapter_identity": provenance.adapter_identity,
        "adapter_version": provenance.adapter_version,
        "transformation_notes": list(provenance.transformation_notes),
    }


def _provenance_from_dict(data: object) -> AnnotationProvenance | None:
    if data is None:
        return None
    mapping = _mapping_value(data, "provenance")
    notes = mapping.get("transformation_notes", [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise TypeError("transformation_notes must be an array of strings")
    return AnnotationProvenance(
        source_corpus=_optional_string(mapping, "source_corpus"),
        source_record_id=_optional_string(mapping, "source_record_id"),
        source_annotation_id=_optional_string(mapping, "source_annotation_id"),
        original_short_form=_source_span_from_dict(mapping.get("original_short_form")),
        original_long_form=_source_span_from_dict(mapping.get("original_long_form")),
        adapter_identity=_optional_string(mapping, "adapter_identity"),
        adapter_version=_optional_string(mapping, "adapter_version"),
        transformation_notes=tuple(notes),
    )


def _prediction_to_dict(
    prediction: PredictionMetadata | None,
) -> dict[str, object] | None:
    if prediction is None:
        return None
    return {
        "confidence": prediction.confidence,
        "score": prediction.score,
        "component": prediction.component,
        "component_version": prediction.component_version,
    }


def _prediction_from_dict(data: object) -> PredictionMetadata | None:
    if data is None:
        return None
    mapping = _mapping_value(data, "prediction metadata")
    return PredictionMetadata(
        confidence=_optional_float(mapping, "confidence"),
        score=_optional_float(mapping, "score"),
        component=_optional_string(mapping, "component"),
        component_version=_optional_string(mapping, "component_version"),
    )


def _ordered_predictions(
    predictions: Iterable[AbbreviationDefinition],
) -> tuple[AbbreviationDefinition, ...]:
    return tuple(
        sorted(
            predictions,
            key=lambda item: json.dumps(_definition_to_dict(item), sort_keys=True),
        )
    )


def _record_sort_key(record: PredictionRecord) -> tuple[str, str, str]:
    return (
        record.record_id or "",
        record.document_id,
        json.dumps(
            [
                _definition_to_dict(item)
                for item in _ordered_predictions(record.predictions)
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


def _json_line(data: Mapping[str, object]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mapping_value(data: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(data, dict):
        raise TypeError(f"{field_name} must be a JSON object")
    return cast(Mapping[str, object], data)


def _string(data: Mapping[str, object], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _optional_string(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{key} must be a string or null")
    return value


def _int(data: Mapping[str, object], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return value


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(f"{key} must be an integer or null")
    return value


def _optional_float(data: Mapping[str, object], key: str) -> float | None:
    value = data.get(key)
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int | float)
    ):
        raise TypeError(f"{key} must be a number or null")
    return value


__all__ = [
    "PREDICTION_SCHEMA_VERSION",
    "PredictionArtifact",
    "PredictionSerializationError",
    "fingerprint_prediction_artifact",
    "prediction_artifact_from_run",
    "prediction_record_from_dict",
    "prediction_record_to_dict",
    "read_prediction_artifact",
    "read_predictions",
    "serialize_prediction_artifact",
    "serialize_predictions",
    "write_prediction_artifact",
    "write_predictions",
]
