"""Contracts and immutable values for candidate feature extraction."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from abrex.candidates import Candidate, CandidateArtifact
from abrex.domain import Document

FEATURE_SCHEMA_VERSION = "features-v1"


@dataclass(frozen=True, slots=True)
class FeatureColumn:
    """Metadata for one numeric feature column."""

    name: str
    extractor: str
    extractor_version: str
    description: str

    def __post_init__(self) -> None:
        for field_name in ("name", "extractor", "extractor_version", "description"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Feature column {field_name} must not be empty")
        if (
            not isinstance(self.name, str)
            or not isinstance(self.extractor, str)
            or not isinstance(self.extractor_version, str)
            or not isinstance(self.description, str)
            or self.name != self.name.lower()
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_"
                for character in self.name
            )
        ):
            raise ValueError(
                "Feature column names must use lowercase letters, digits, and "
                "underscores"
            )


@dataclass(frozen=True, slots=True)
class FeatureExtractorMetadata:
    """Stable identity and schema contribution of one extractor."""

    key: str
    version: str
    feature_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or not isinstance(self.version, str)
            or not self.key.strip()
            or not self.version.strip()
        ):
            raise ValueError("Feature extractor metadata identity must not be empty")
        if not self.feature_names or any(
            not name.strip() for name in self.feature_names
        ):
            raise ValueError("Feature extractor metadata requires feature names")


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    """Ordered schema metadata for a feature matrix."""

    columns: tuple[FeatureColumn, ...]
    extractors: tuple[FeatureExtractorMetadata, ...]
    version: str = FEATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.version != FEATURE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported feature schema version: {self.version!r}")
        if not self.columns or not self.extractors:
            raise ValueError("Feature schema requires columns and extractors")
        if len({column.name for column in self.columns}) != len(self.columns):
            raise ValueError("Feature column names must be unique")
        names = tuple(column.name for column in self.columns)
        metadata_names = tuple(
            name for extractor in self.extractors for name in extractor.feature_names
        )
        if names != metadata_names:
            raise ValueError("Feature columns and extractor metadata disagree")

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Return feature names in their deterministic matrix order."""

        return tuple(column.name for column in self.columns)

    @property
    def column_names(self) -> tuple[str, ...]:
        """Alias for callers treating the schema as a tabular schema."""

        return self.feature_names

    def as_dict(self) -> dict[str, object]:
        """Return JSON-compatible schema metadata for analysis tooling."""

        return {
            "schema_version": self.version,
            "extractors": [
                {
                    "key": extractor.key,
                    "version": extractor.version,
                    "feature_names": list(extractor.feature_names),
                }
                for extractor in self.extractors
            ],
            "columns": [
                {
                    "name": column.name,
                    "extractor": column.extractor,
                    "extractor_version": column.extractor_version,
                    "dtype": "float",
                    "description": column.description,
                }
                for column in self.columns
            ],
        }


@dataclass(frozen=True, slots=True)
class FeatureRow:
    """One candidate's feature vector and stable artifact-local row key."""

    document_id: str
    candidate_index: int
    candidate: Candidate
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Feature row document_id must not be empty")
        if isinstance(self.candidate_index, bool) or not isinstance(
            self.candidate_index, int
        ):
            raise TypeError("Feature row candidate_index must be an integer")
        if self.candidate_index < 0:
            raise ValueError("Feature row candidate_index must be non-negative")
        if self.candidate.document_id != self.document_id:
            raise ValueError("Feature row candidate and document IDs must match")
        if not isinstance(self.values, tuple) or any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            for value in self.values
        ):
            raise TypeError("Feature row values must be finite numeric values")
        object.__setattr__(self, "values", tuple(float(value) for value in self.values))


@dataclass(frozen=True, slots=True)
class FeatureMatrix:
    """Immutable tabular representation of extracted candidate features."""

    schema: FeatureSchema
    rows: tuple[FeatureRow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or any(
            not isinstance(row, FeatureRow) for row in self.rows
        ):
            raise TypeError("Feature matrix rows must be a tuple of FeatureRow values")
        width = len(self.schema.columns)
        if any(len(row.values) != width for row in self.rows):
            raise ValueError("Every feature row must match the schema width")

    @property
    def matrix(self) -> tuple[tuple[float, ...], ...]:
        """Return numeric rows in schema order."""

        return tuple(row.values for row in self.rows)

    @property
    def shape(self) -> tuple[int, int]:
        """Return ``(row_count, column_count)`` without a NumPy dependency."""

        return len(self.rows), len(self.schema.columns)

    @property
    def row_keys(self) -> tuple[tuple[str, int], ...]:
        """Return document/candidate-index keys aligned with :attr:`matrix`."""

        return tuple((row.document_id, row.candidate_index) for row in self.rows)


class FeatureExtractor(Protocol):
    """Interchangeable, gold-independent extractor for one candidate."""

    identity: str
    version: str
    feature_names: tuple[str, ...]
    feature_descriptions: tuple[str, ...]

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        """Return finite named feature values for ``candidate``."""


class FeatureSet(Protocol):
    """Protocol for a configured collection of feature extractors."""

    @property
    def schema(self) -> FeatureSchema:
        """Return deterministic feature schema metadata."""

    def extract(self, document: Document, candidate: Candidate) -> tuple[float, ...]:
        """Extract one vector in schema order."""

    def extract_artifact(
        self,
        artifact: CandidateArtifact,
        documents: Mapping[str, Document],
    ) -> FeatureMatrix:
        """Transform a candidate artifact and canonical documents into a matrix."""


def validate_feature_names(names: Iterable[str]) -> tuple[str, ...]:
    """Validate and freeze an extractor's explicitly ordered feature names."""

    result = tuple(names)
    if not result or any(
        not isinstance(name, str) or not name.strip() for name in result
    ):
        raise ValueError("Feature extractors require non-empty feature names")
    if len(set(result)) != len(result):
        raise ValueError("Feature names within an extractor must be unique")
    return result


__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "FeatureColumn",
    "FeatureExtractor",
    "FeatureExtractorMetadata",
    "FeatureMatrix",
    "FeatureRow",
    "FeatureSchema",
    "FeatureSet",
    "validate_feature_names",
]
