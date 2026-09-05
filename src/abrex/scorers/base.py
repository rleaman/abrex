"""Contracts and immutable values for supervised candidate scoring.

This module intentionally does not define labels, a loss, or a model family.
Those are scientific choices owned by a scorer implementation and its
experiment configuration.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from abrex.candidates import Candidate
from abrex.features import FeatureMatrix

SCORER_ARTIFACT_SCHEMA_VERSION = "scorer-artifact-v1"
SPLIT_MANIFEST_SCHEMA_VERSION = "scorer-splits-v1"


@dataclass(frozen=True, slots=True)
class ScoringDataset:
    """A feature matrix and caller-supplied labels for one explicit split."""

    split: str
    features: FeatureMatrix
    labels: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.split, str) or not self.split.strip():
            raise ValueError("Scoring dataset split must not be empty")
        if not isinstance(self.features, FeatureMatrix):
            raise TypeError("Scoring dataset features must be a FeatureMatrix")
        if not isinstance(self.labels, tuple):
            raise TypeError("Scoring dataset labels must be a tuple")
        if len(self.labels) != len(self.features.rows):
            raise ValueError("Scoring dataset labels must match feature rows")
        if any(
            isinstance(label, bool)
            or not isinstance(label, int | float)
            or not math.isfinite(label)
            for label in self.labels
        ):
            raise ValueError("Scoring dataset labels must be finite real numbers")
        object.__setattr__(self, "labels", tuple(float(label) for label in self.labels))


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """One candidate paired with a raw scorer output."""

    document_id: str
    candidate_index: int
    candidate: Candidate
    score: float

    def __post_init__(self) -> None:
        if self.candidate.document_id != self.document_id:
            raise ValueError("Scored candidate and candidate document IDs must match")
        if (
            isinstance(self.candidate_index, bool)
            or not isinstance(self.candidate_index, int)
            or self.candidate_index < 0
        ):
            raise ValueError("candidate_index must be a non-negative integer")
        if isinstance(self.score, bool) or not isinstance(self.score, int | float):
            raise TypeError("score must be a real number")
        if not math.isfinite(self.score):
            raise ValueError("score must be finite")
        object.__setattr__(self, "score", float(self.score))


@runtime_checkable
class Scorer(Protocol):
    """Interchangeable fit/predict contract for candidate feature matrices."""

    identity: str
    version: str

    def fit(
        self,
        train: ScoringDataset,
        *,
        dev: ScoringDataset | None = None,
        seed: int | None = None,
    ) -> None:
        """Fit the scorer using the explicitly supplied training data."""

    def predict(self, features: FeatureMatrix) -> Sequence[float]:
        """Return one finite score for every feature row."""


@runtime_checkable
class PersistableScorer(Scorer, Protocol):
    """Optional persistence contract for reproducible model artifacts."""

    def save(self, path: Path) -> None:
        """Write model state to ``path``."""

    def load(self, path: Path) -> None:
        """Load model state from ``path``."""


class Calibrator(Protocol):
    """Transform raw scores before an explicit selection policy is applied."""

    identity: str
    version: str

    def calibrate(self, scores: Sequence[float]) -> tuple[float, ...]:
        """Return one finite calibrated score per raw score."""


class SelectionPolicy(Protocol):
    """Decide which scored candidates become resolver predictions."""

    identity: str
    version: str

    def select(self, scores: Sequence[float]) -> tuple[bool, ...]:
        """Return one acceptance decision per score."""


@dataclass(frozen=True, slots=True)
class ScorerArtifact:
    """Manifest metadata for a persisted model artifact."""

    scorer_key: str
    scorer_version: str
    model_fingerprint: str
    feature_schema_fingerprint: str
    feature_config_fingerprint: str | None = None
    seed: int | None = None
    calibration: tuple[str, str] | None = None
    selection: tuple[str, str] | None = None
    schema_version: str = SCORER_ARTIFACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("scorer_key", "scorer_version", "model_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        for name in ("feature_schema_fingerprint", "feature_config_fingerprint"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be non-empty when supplied")
        if self.schema_version != SCORER_ARTIFACT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported scorer artifact schema: {self.schema_version}"
            )
        for name in ("calibration", "selection"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, tuple)
                or len(value) != 2
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                raise TypeError(f"{name} metadata must be a pair of strings")

    def as_dict(self) -> dict[str, object]:
        """Return deterministic JSON-compatible manifest metadata."""

        return {
            "schema_version": self.schema_version,
            "scorer": {"key": self.scorer_key, "version": self.scorer_version},
            "model_fingerprint": self.model_fingerprint,
            "feature_schema_fingerprint": self.feature_schema_fingerprint,
            "feature_config_fingerprint": self.feature_config_fingerprint,
            "seed": self.seed,
            "calibration": _component_dict(self.calibration),
            "selection": _component_dict(self.selection),
        }


def _component_dict(value: tuple[str, str] | None) -> object:
    if value is None:
        return None
    return {"key": value[0], "version": value[1]}


__all__ = [
    "Calibrator",
    "PersistableScorer",
    "SCORER_ARTIFACT_SCHEMA_VERSION",
    "SPLIT_MANIFEST_SCHEMA_VERSION",
    "ScoredCandidate",
    "Scorer",
    "ScorerArtifact",
    "ScoringDataset",
    "SelectionPolicy",
]
