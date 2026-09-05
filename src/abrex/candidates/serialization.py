"""Deterministic JSONL candidate artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from abrex.candidates.base import (
    Candidate,
    CandidateArtifact,
    CandidateDiagnostic,
    CandidateDiagnosticAction,
    CandidateDiagnosticSeverity,
    CandidateGeneratorMetadata,
    CandidateRecord,
)
from abrex.domain import AnnotationProvenance, Document, TextSpan

CANDIDATE_SCHEMA_VERSION = "candidates-v1"


class CandidateSerializationError(ValueError):
    """Raised for malformed or unreadable candidate artifacts."""


def serialize_candidate_artifact(
    artifact: CandidateArtifact,
) -> str:
    """Serialize candidate records as stable JSONL."""

    lines = []
    for record in sorted(artifact.records, key=lambda item: item.document_id):
        lines.append(
            _json_line(
                {
                    "schema_version": CANDIDATE_SCHEMA_VERSION,
                    "generators": [
                        {"key": key, "version": version}
                        for key, version in artifact.generators.components
                    ],
                    "document_id": record.document_id,
                    "candidates": [
                        _candidate_to_dict(item) for item in record.candidates
                    ],
                    "diagnostics": [
                        _diagnostic_to_dict(item) for item in record.diagnostics
                    ],
                }
            )
        )
    return "".join(lines)


def write_candidate_artifact(path: Path, artifact: CandidateArtifact) -> str:
    """Write an artifact and return its SHA-256 fingerprint."""

    serialized = serialize_candidate_artifact(artifact)
    try:
        path.write_text(serialized, encoding="utf-8")
    except OSError as error:
        raise CandidateSerializationError(f"Unable to write {path}: {error}") from error
    return _fingerprint(serialized.encode("utf-8"))


def read_candidate_artifact(
    path: Path, *, documents: Mapping[str, Document] | None = None
) -> tuple[CandidateGeneratorMetadata, tuple[CandidateRecord, ...]]:
    """Read, validate, and return a candidate artifact."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise CandidateSerializationError(f"Unable to read {path}: {error}") from error
    if not lines:
        raise CandidateSerializationError("Candidate artifact must contain a record")
    metadata: CandidateGeneratorMetadata | None = None
    records: list[CandidateRecord] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise TypeError("object required")
            if raw.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
                raise ValueError("unsupported candidate schema version")
            current_metadata = _metadata_from_dict(raw.get("generators"))
            if metadata is None:
                metadata = current_metadata
            elif current_metadata != metadata:
                raise TypeError("inconsistent generator metadata")
            record = _record_from_dict(raw)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise CandidateSerializationError(
                f"Invalid candidate artifact at line {line_number}: {error}"
            ) from error
        if record.document_id in seen:
            raise CandidateSerializationError("Duplicate candidate document ID")
        seen.add(record.document_id)
        document = documents.get(record.document_id) if documents is not None else None
        if documents is not None and document is None:
            raise CandidateSerializationError(
                f"No canonical document for {record.document_id!r}"
            )
        if document is not None:
            for candidate in record.candidates:
                candidate.validate_against(document)
        records.append(record)
    assert metadata is not None
    return metadata, tuple(records)


def fingerprint_candidate_artifact(
    artifact: CandidateArtifact,
) -> str:
    """Return the path-independent artifact fingerprint."""

    return _fingerprint(serialize_candidate_artifact(artifact).encode("utf-8"))


def _candidate_to_dict(candidate: Candidate) -> dict[str, object]:
    return {
        "document_id": candidate.document_id,
        "short_form": _span_to_dict(candidate.short_form),
        "long_form": _span_to_dict(candidate.long_form),
        "construction": candidate.construction,
        "provenance": _provenance_to_dict(candidate.provenance),
    }


def _candidate_from_dict(data: Mapping[str, object]) -> Candidate:
    return Candidate(
        cast(str, data["document_id"]),
        _span_from_dict(data["short_form"]),
        _span_from_dict(data["long_form"]),
        cast(str, data["construction"]),
        _provenance_from_dict(data.get("provenance")),
    )


def _record_from_dict(data: Mapping[str, object]) -> CandidateRecord:
    candidates = data.get("candidates")
    diagnostics = data.get("diagnostics", [])
    if not isinstance(candidates, list) or not isinstance(diagnostics, list):
        raise TypeError("candidates and diagnostics must be arrays")
    return CandidateRecord(
        cast(str, data["document_id"]),
        tuple(
            _candidate_from_dict(cast(Mapping[str, object], item))
            for item in candidates
        ),
        tuple(
            _diagnostic_from_dict(cast(Mapping[str, object], item))
            for item in diagnostics
        ),
    )


def _metadata_from_dict(data: object) -> CandidateGeneratorMetadata:
    if not isinstance(data, list) or not data:
        raise TypeError("generators must be a non-empty array")
    components = []
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("generator metadata must be objects")
        components.append((cast(str, item["key"]), cast(str, item["version"])))
    return CandidateGeneratorMetadata(tuple(components))


def _diagnostic_to_dict(diagnostic: CandidateDiagnostic) -> dict[str, object]:
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "document_id": diagnostic.document_id,
        "action": diagnostic.action,
        "details": dict(diagnostic.details),
    }


def _diagnostic_from_dict(data: Mapping[str, object]) -> CandidateDiagnostic:
    details = data.get("details", {})
    if not isinstance(details, dict):
        raise TypeError("diagnostic details must be an object")
    return CandidateDiagnostic(
        cast(CandidateDiagnosticSeverity, data["severity"]),
        cast(str, data["code"]),
        cast(str, data["message"]),
        cast(str, data["document_id"]),
        cast(CandidateDiagnosticAction, data["action"]),
        tuple(
            sorted((cast(str, key), cast(str, value)) for key, value in details.items())
        ),
    )


def _span_to_dict(span: TextSpan) -> dict[str, int]:
    return {"start": span.start, "end": span.end}


def _span_from_dict(data: object) -> TextSpan:
    if not isinstance(data, dict):
        raise TypeError("span must be an object")
    return TextSpan(cast(int, data["start"]), cast(int, data["end"]))


def _provenance_to_dict(provenance: AnnotationProvenance | None) -> object:
    if provenance is None:
        return None
    return {
        "adapter_identity": provenance.adapter_identity,
        "adapter_version": provenance.adapter_version,
        "transformation_notes": list(provenance.transformation_notes),
    }


def _provenance_from_dict(data: object) -> AnnotationProvenance | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError("provenance must be an object")
    notes = data.get("transformation_notes", [])
    if not isinstance(notes, list) or any(not isinstance(item, str) for item in notes):
        raise TypeError("transformation_notes must be an array of strings")
    return AnnotationProvenance(
        adapter_identity=cast(str | None, data.get("adapter_identity")),
        adapter_version=cast(str | None, data.get("adapter_version")),
        transformation_notes=tuple(notes),
    )


def _json_line(data: Mapping[str, object]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "CANDIDATE_SCHEMA_VERSION",
    "CandidateSerializationError",
    "fingerprint_candidate_artifact",
    "read_candidate_artifact",
    "serialize_candidate_artifact",
    "write_candidate_artifact",
]
