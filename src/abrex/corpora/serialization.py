"""Versioned canonical JSONL artifacts, manifests, and fingerprints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from abrex.corpora.base import CorpusBuildResult, SourceResource
from abrex.corpora.validation import (
    CanonicalValidator,
    ValidationIssue,
    ValidationMode,
    ValidationSummary,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)

CANONICAL_SCHEMA_VERSION = "canonical-v1"
MANIFEST_SCHEMA_VERSION = "manifest-v1"


class CanonicalSerializationError(ValueError):
    """Raised when a canonical JSONL artifact is malformed or cannot be read."""


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Immutable identity and audit metadata for one canonical artifact."""

    dataset_id: str
    fingerprint: str
    record_count: int
    annotation_count: int
    adapter_identity: str | None = None
    adapter_version: str | None = None
    normalizer_identities: tuple[str, ...] = ()
    config_fingerprint: str | None = None
    source_identifier: str | None = None
    source_format: str | None = None
    source_fingerprint: str | None = None
    validation: ValidationSummary = ValidationSummary()
    schema_version: str = CANONICAL_SCHEMA_VERSION
    manifest_version: str = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_id, str) or not self.dataset_id.strip():
            raise ValueError("dataset_id must not be empty")
        if not _is_sha256(self.fingerprint):
            raise ValueError("fingerprint must be a SHA-256 hexadecimal digest")
        if self.config_fingerprint is not None and not _is_sha256(
            self.config_fingerprint
        ):
            raise ValueError("config_fingerprint must be a SHA-256 hexadecimal digest")
        if self.source_fingerprint is not None and not _is_sha256(
            self.source_fingerprint
        ):
            raise ValueError("source_fingerprint must be a SHA-256 hexadecimal digest")
        for name in ("record_count", "annotation_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.normalizer_identities, tuple) or any(
            not isinstance(item, str) for item in self.normalizer_identities
        ):
            raise TypeError("normalizer_identities must be a tuple of strings")
        if not isinstance(self.validation, ValidationSummary):
            raise TypeError("validation must be a ValidationSummary")
        if self.schema_version != CANONICAL_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported canonical schema version: {self.schema_version!r}"
            )
        if self.manifest_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"Unsupported manifest version: {self.manifest_version!r}")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-compatible manifest data."""

        return {
            "manifest_version": self.manifest_version,
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "fingerprint": self.fingerprint,
            "record_count": self.record_count,
            "annotation_count": self.annotation_count,
            "adapter": {
                "identity": self.adapter_identity,
                "version": self.adapter_version,
            },
            "normalizers": list(self.normalizer_identities),
            "config_fingerprint": self.config_fingerprint,
            "source": {
                "identifier": self.source_identifier,
                "format": self.source_format,
                "fingerprint": self.source_fingerprint,
            },
            "validation": self.validation.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize the manifest with stable formatting."""

        return (
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


def record_to_dict(record: CorpusRecord) -> dict[str, object]:
    """Convert one canonical record to a versioned JSON-compatible mapping."""

    if not isinstance(record, CorpusRecord):
        raise TypeError("record must be a CorpusRecord")
    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "record_id": record.record_id,
        "document": {
            "document_id": record.document.document_id,
            "text": record.document.text,
        },
        "gold_annotations": [
            _definition_to_dict(annotation) for annotation in record.gold_annotations
        ],
        "provenance": _provenance_to_dict(record.provenance),
    }


def record_from_dict(
    data: Mapping[str, object], *, line_number: int | None = None
) -> CorpusRecord:
    """Parse and validate one canonical record mapping."""

    location = f" at line {line_number}" if line_number is not None else ""
    try:
        if data.get("schema_version") != CANONICAL_SCHEMA_VERSION:
            raise CanonicalSerializationError(
                f"Unsupported canonical schema version{location}: "
                f"{data.get('schema_version')!r}"
            )
        document_data = _mapping(data, "document")
        document = Document(
            _string(document_data, "document_id"), _string(document_data, "text")
        )
        raw_annotations = data.get("gold_annotations", [])
        if not isinstance(raw_annotations, list):
            raise TypeError("gold_annotations must be a JSON array")
        annotations = tuple(
            _definition_from_dict(_mapping_value(item, "annotation"))
            for item in raw_annotations
        )
        record_id = data.get("record_id")
        if record_id is not None and not isinstance(record_id, str):
            raise TypeError("record_id must be a string or null")
        provenance_data = data.get("provenance")
        record = CorpusRecord(
            document=document,
            gold_annotations=annotations,
            record_id=record_id,
            provenance=_provenance_from_dict(provenance_data),
        )
        record.validate()
        return record
    except CanonicalSerializationError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise CanonicalSerializationError(
            f"Invalid canonical record{location}: {error}"
        ) from error


def serialize_record(record: CorpusRecord) -> str:
    """Serialize one record as a newline-terminated canonical JSON object."""

    return _json_line(record_to_dict(record))


def serialize_records(records: Iterable[CorpusRecord]) -> str:
    """Serialize records in deterministic order without collapsing duplicates."""

    ordered = _ordered_records(tuple(records))
    return "".join(serialize_record(record) for record in ordered)


def write_canonical_jsonl(records: Iterable[CorpusRecord], path: Path) -> str:
    """Write canonical JSONL and return its dataset fingerprint."""

    content = serialize_records(records)
    try:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except OSError as error:
        raise CanonicalSerializationError(
            f"Unable to write canonical JSONL {path}: {error}"
        ) from error
    return _fingerprint_bytes(content.encode("utf-8"))


def read_canonical_jsonl(
    path: Path, *, mode: ValidationMode = "strict"
) -> tuple[CorpusRecord, ...]:
    """Load, validate, and deterministically order a canonical JSONL artifact."""

    try:
        with path.open("r", encoding="utf-8", newline=None) as stream:
            lines = tuple(stream)
    except (OSError, UnicodeError) as error:
        raise CanonicalSerializationError(
            f"Unable to read canonical JSONL {path}: {error}"
        ) from error
    records: list[CorpusRecord] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise CanonicalSerializationError(
                f"Invalid canonical JSONL at line {line_number}: blank line"
            )
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise CanonicalSerializationError(
                f"Invalid JSON at line {line_number}: {error.msg}"
            ) from error
        if not isinstance(data, dict):
            raise CanonicalSerializationError(
                f"Invalid canonical JSONL at line {line_number}: object required"
            )
        records.append(
            record_from_dict(cast(Mapping[str, object], data), line_number=line_number)
        )
    result = CanonicalValidator().validate(records, mode=mode)
    return result.records


def fingerprint_records(records: Iterable[CorpusRecord]) -> str:
    """Return a path-independent SHA-256 fingerprint of canonical records."""

    return _fingerprint_bytes(serialize_records(records).encode("utf-8"))


def fingerprint_file(path: Path) -> str:
    """Return a SHA-256 fingerprint of source bytes for manifest provenance."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise CanonicalSerializationError(
            f"Unable to fingerprint source {path}: {error}"
        ) from error
    return digest.hexdigest()


def build_dataset_manifest(
    records: Iterable[CorpusRecord],
    *,
    dataset_id: str,
    validation: ValidationSummary | None = None,
    build_result: CorpusBuildResult | None = None,
    config_fingerprint: str | None = None,
) -> DatasetManifest:
    """Create a manifest from records and optional corpus-build metadata."""

    ordered = _ordered_records(tuple(records))
    source = build_result.source if build_result is not None else None
    return DatasetManifest(
        dataset_id=dataset_id,
        fingerprint=fingerprint_records(ordered),
        record_count=len(ordered),
        annotation_count=sum(len(record.gold_annotations) for record in ordered),
        adapter_identity=(
            build_result.adapter_identity if build_result is not None else None
        ),
        adapter_version=(
            build_result.adapter_version if build_result is not None else None
        ),
        normalizer_identities=(
            build_result.normalizer_identities if build_result is not None else ()
        ),
        config_fingerprint=config_fingerprint,
        source_identifier=source.identifier if source is not None else None,
        source_format=source.format if source is not None else None,
        source_fingerprint=_source_fingerprint(source),
        validation=validation if validation is not None else ValidationSummary(),
    )


def write_canonical_dataset(
    build_result: CorpusBuildResult,
    path: Path,
    *,
    dataset_id: str | None = None,
    manifest_path: Path | None = None,
    mode: ValidationMode = "permissive",
    config_fingerprint: str | None = None,
) -> DatasetManifest:
    """Validate a build result, write JSONL, and write its manifest."""

    validation = CanonicalValidator().validate(
        build_result.records, mode=mode, diagnostics=build_result.diagnostics
    )
    write_canonical_jsonl(validation.records, path)
    manifest = build_dataset_manifest(
        validation.records,
        dataset_id=dataset_id or build_result.source.identifier,
        validation=validation.summary,
        build_result=build_result,
        config_fingerprint=config_fingerprint,
    )
    output_manifest = manifest_path or path.with_suffix(".manifest.json")
    try:
        with output_manifest.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(manifest.to_json())
    except OSError as error:
        raise CanonicalSerializationError(
            f"Unable to write dataset manifest {output_manifest}: {error}"
        ) from error
    return manifest


def read_dataset_manifest(path: Path) -> DatasetManifest:
    """Load a manifest and validate its structural identity fields."""

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CanonicalSerializationError(
            f"Unable to read dataset manifest {path}: {error}"
        ) from error
    if not isinstance(data, dict):
        raise CanonicalSerializationError("Dataset manifest must be a JSON object")
    try:
        adapter = _mapping(data, "adapter")
        source = _mapping(data, "source")
        validation_data = _mapping(data, "validation")
        validation = _validation_summary_from_dict(validation_data)
        normalizers = data.get("normalizers", [])
        if not isinstance(normalizers, list) or any(
            not isinstance(item, str) for item in normalizers
        ):
            raise TypeError("normalizers must be an array of strings")
        return DatasetManifest(
            dataset_id=_string(data, "dataset_id"),
            fingerprint=_string(data, "fingerprint"),
            record_count=_int(data, "record_count"),
            annotation_count=_int(data, "annotation_count"),
            adapter_identity=_optional_string(adapter, "identity"),
            adapter_version=_optional_string(adapter, "version"),
            normalizer_identities=tuple(normalizers),
            config_fingerprint=_optional_string(data, "config_fingerprint"),
            source_identifier=_optional_string(source, "identifier"),
            source_format=_optional_string(source, "format"),
            source_fingerprint=_optional_string(source, "fingerprint"),
            validation=validation,
            schema_version=_string(data, "schema_version"),
            manifest_version=_string(data, "manifest_version"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CanonicalSerializationError(
            f"Invalid dataset manifest: {error}"
        ) from error


def read_canonical_dataset(
    jsonl_path: Path,
    manifest_path: Path | None = None,
    *,
    mode: ValidationMode = "strict",
) -> tuple[tuple[CorpusRecord, ...], DatasetManifest]:
    """Load an artifact pair and detect data or manifest corruption."""

    records = read_canonical_jsonl(jsonl_path, mode=mode)
    manifest = read_dataset_manifest(
        manifest_path or jsonl_path.with_suffix(".manifest.json")
    )
    if fingerprint_records(records) != manifest.fingerprint:
        raise CanonicalSerializationError(
            "Canonical dataset fingerprint does not match its manifest"
        )
    if len(records) != manifest.record_count:
        raise CanonicalSerializationError(
            "Canonical dataset record count does not match its manifest"
        )
    annotation_count = sum(len(record.gold_annotations) for record in records)
    if annotation_count != manifest.annotation_count:
        raise CanonicalSerializationError(
            "Canonical dataset annotation count does not match its manifest"
        )
    return records, manifest


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
    mapping = _mapping_value(data, "prediction")
    return PredictionMetadata(
        confidence=_optional_float(mapping, "confidence"),
        score=_optional_float(mapping, "score"),
        component=_optional_string(mapping, "component"),
        component_version=_optional_string(mapping, "component_version"),
    )


def _validation_summary_from_dict(data: Mapping[str, object]) -> ValidationSummary:
    raw = data.get("diagnostics", [])
    if not isinstance(raw, list):
        raise TypeError("validation diagnostics must be an array")
    # Reconstructing complete issues is intentionally strict; summaries are
    # artifacts, not an opportunity to discard audit information.

    issues = tuple(_validation_issue_from_dict(item) for item in raw)
    return ValidationSummary(
        issues=issues,
        records_seen=_int(data, "records_seen"),
        records_kept=_int(data, "records_kept"),
    )


def _validation_issue_from_dict(data: object) -> ValidationIssue:
    mapping = _mapping_value(data, "validation issue")
    raw_details = mapping.get("details", {})
    if not isinstance(raw_details, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in raw_details.items()
    ):
        raise TypeError("validation issue details must be a JSON object of strings")
    return ValidationIssue(
        severity=cast(Any, _string(mapping, "severity")),
        code=_string(mapping, "code"),
        message=_string(mapping, "message"),
        action=cast(Any, _string(mapping, "action")),
        record_id=_optional_string(mapping, "record_id"),
        annotation_id=_optional_string(mapping, "annotation_id"),
        location=_optional_string(mapping, "location"),
        details=tuple(sorted(raw_details.items())),
    )


def _ordered_records(records: tuple[CorpusRecord, ...]) -> tuple[CorpusRecord, ...]:
    return tuple(sorted(records, key=_record_sort_key))


def _record_sort_key(record: CorpusRecord) -> tuple[object, ...]:
    annotation_keys = tuple(
        json.dumps(_definition_to_dict(annotation), ensure_ascii=False, sort_keys=True)
        for annotation in record.gold_annotations
    )
    return (
        record.id,
        record.document.document_id,
        record.document.text,
        annotation_keys,
    )


def _json_line(data: Mapping[str, object]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_fingerprint(source: SourceResource | None) -> str | None:
    if source is None or source.location is None or not source.location.is_file():
        return None
    return fingerprint_file(source.location)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _mapping_value(data.get(key), key)


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
    "CANONICAL_SCHEMA_VERSION",
    "CanonicalSerializationError",
    "DatasetManifest",
    "MANIFEST_SCHEMA_VERSION",
    "build_dataset_manifest",
    "fingerprint_file",
    "fingerprint_records",
    "read_canonical_dataset",
    "read_canonical_jsonl",
    "read_dataset_manifest",
    "record_from_dict",
    "record_to_dict",
    "serialize_record",
    "serialize_records",
    "write_canonical_dataset",
    "write_canonical_jsonl",
]
