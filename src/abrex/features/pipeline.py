"""YAML composition and deterministic batch extraction for features."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates import Candidate, CandidateArtifact, CandidateRecord
from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.domain import Document
from abrex.features.base import (
    FeatureColumn,
    FeatureExtractor,
    FeatureExtractorMetadata,
    FeatureMatrix,
    FeatureRow,
    FeatureSchema,
    validate_feature_names,
)
from abrex.features.registry import EXTRACTORS
from abrex.registry import Registry


class FeatureSetConfig(BaseModel):
    """Typed YAML composition for an ordered feature extractor set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extractors: tuple[ComponentSpec, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ConfiguredFeatureSet:
    """Compose extractors and produce inspectable numeric feature matrices."""

    extractors: tuple[FeatureExtractor, ...]

    def __post_init__(self) -> None:
        if not self.extractors:
            raise ValueError("Feature set requires at least one extractor")
        names: list[str] = []
        for extractor in self.extractors:
            if (
                not isinstance(extractor.identity, str)
                or not extractor.identity.strip()
            ):
                raise ValueError("Feature extractor identity must not be empty")
            if not isinstance(extractor.version, str) or not extractor.version.strip():
                raise ValueError("Feature extractor version must not be empty")
            extractor_names = validate_feature_names(extractor.feature_names)
            descriptions = tuple(extractor.feature_descriptions)
            if len(descriptions) != len(extractor_names) or any(
                not isinstance(description, str) or not description.strip()
                for description in descriptions
            ):
                raise ValueError(
                    f"Extractor {extractor.identity!r} must describe every feature"
                )
            names.extend(extractor_names)
        if len(set(names)) != len(names):
            raise ValueError("Feature names must be unique across the feature set")

    @property
    def schema(self) -> FeatureSchema:
        """Return extractor metadata and columns in configured order."""

        metadata = tuple(
            FeatureExtractorMetadata(
                extractor.identity, extractor.version, extractor.feature_names
            )
            for extractor in self.extractors
        )
        columns = tuple(
            FeatureColumn(name, extractor.identity, extractor.version, description)
            for extractor in self.extractors
            for name, description in zip(
                extractor.feature_names, extractor.feature_descriptions, strict=True
            )
        )
        return FeatureSchema(columns, metadata)

    def extract(self, document: Document, candidate: Candidate) -> tuple[float, ...]:
        """Extract and validate one candidate vector in schema order."""

        values: list[float] = []
        for extractor in self.extractors:
            candidate_values = extractor.extract(document, candidate)
            expected = tuple(extractor.feature_names)
            if set(candidate_values) != set(expected):
                raise ValueError(
                    f"Extractor {extractor.identity!r} returned an invalid "
                    "feature schema"
                )
            for name in expected:
                value = candidate_values[name]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise TypeError(f"Feature {name!r} must be numeric")
                if not math.isfinite(value):
                    raise ValueError(f"Feature {name!r} must be finite")
                values.append(float(value))
        return tuple(values)

    def extract_candidates(
        self, document: Document, candidates: Iterable[Candidate]
    ) -> tuple[FeatureRow, ...]:
        """Extract rows in the supplied candidate order."""

        rows = []
        for candidate_index, candidate in enumerate(candidates):
            rows.append(
                FeatureRow(
                    document.document_id,
                    candidate_index,
                    candidate,
                    self.extract(document, candidate),
                )
            )
        return tuple(rows)

    def extract_record(
        self, document: Document, record: CandidateRecord
    ) -> tuple[FeatureRow, ...]:
        """Extract one candidate record after checking its document identity."""

        if record.document_id != document.document_id:
            raise ValueError("Candidate record document ID does not match document")
        return self.extract_candidates(document, record.candidates)

    def extract_artifact(
        self,
        artifact: CandidateArtifact,
        documents: Mapping[str, Document],
    ) -> FeatureMatrix:
        """Transform an artifact into deterministic rows sorted by document ID."""

        rows: list[FeatureRow] = []
        for record in sorted(artifact.records, key=lambda item: item.document_id):
            document = documents.get(record.document_id)
            if document is None:
                raise ValueError(f"No canonical document for {record.document_id!r}")
            rows.extend(self.extract_record(document, record))
        return FeatureMatrix(self.schema, tuple(rows))

    def transform(
        self,
        artifact: CandidateArtifact,
        documents: Mapping[str, Document],
    ) -> FeatureMatrix:
        """Alias for :meth:`extract_artifact` for tabular-transform callers."""

        return self.extract_artifact(artifact, documents)


def create_feature_set(
    config: FeatureSetConfig,
    *,
    registry: Registry[FeatureExtractor] = EXTRACTORS,
) -> ConfiguredFeatureSet:
    """Instantiate a typed feature set from an injectable registry."""

    return ConfiguredFeatureSet(
        tuple(create_component(spec, registry) for spec in config.extractors)
    )


def feature_set_config_from_resolved(config: ResolvedConfig) -> FeatureSetConfig:
    """Read and validate the top-level ``features`` YAML section."""

    raw = config.model_extra.get("features") if config.model_extra else None
    if not isinstance(raw, dict):
        raise ValueError("Resolved configuration does not contain a features section")
    return FeatureSetConfig.model_validate(raw)


__all__ = [
    "ConfiguredFeatureSet",
    "FeatureSetConfig",
    "create_feature_set",
    "feature_set_config_from_resolved",
]
