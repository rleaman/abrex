"""Application service for deterministic scorer fit and prediction lifecycle."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass

from abrex.features import FeatureMatrix
from abrex.scorers.base import (
    Calibrator,
    ScoredCandidate,
    Scorer,
    ScoringDataset,
    SelectionPolicy,
)


@dataclass(slots=True)
class ScorerExecutor:
    """Validate scorer outputs and keep selection/calibration explicit."""

    scorer: Scorer
    scorer_key: str | None = None
    seed: int | None = None
    feature_config_fingerprint: str | None = None
    calibrator: Calibrator | None = None
    selection_policy: SelectionPolicy | None = None

    def __post_init__(self) -> None:
        for name in ("identity", "version"):
            value = getattr(self.scorer, name, None)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Scorer {name} must not be empty")
        if self.scorer_key is None:
            self.scorer_key = self.scorer.identity
        if not self.scorer_key.strip():
            raise ValueError("scorer_key must not be empty")

    @property
    def identity(self) -> str:
        """Return the stable registry identity."""

        assert self.scorer_key is not None
        return self.scorer_key

    @property
    def version(self) -> str:
        """Return the scorer implementation version."""

        return self.scorer.version

    def fit(
        self,
        train: ScoringDataset,
        *,
        dev: ScoringDataset | None = None,
        seed: int | None = None,
    ) -> None:
        """Fit with a stable child seed derived from the experiment seed."""

        selected_seed = self.seed if seed is None else seed
        self.scorer.fit(
            train, dev=dev, seed=derive_child_seed(selected_seed, self.identity)
        )

    def predict(self, features: FeatureMatrix) -> tuple[float, ...]:
        """Validate one finite score per feature row."""

        scores = tuple(self.scorer.predict(features))
        if len(scores) != len(features.rows):
            raise ValueError("Scorer must return one score per feature row")
        if any(
            isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(score)
            for score in scores
        ):
            raise ValueError("Scorer scores must be finite real numbers")
        return tuple(float(score) for score in scores)

    def calibrated_predict(self, features: FeatureMatrix) -> tuple[float, ...]:
        """Return raw scores after the configured calibration hook."""

        scores = self.predict(features)
        if self.calibrator is None:
            return scores
        calibrated = tuple(self.calibrator.calibrate(scores))
        if len(calibrated) != len(scores) or any(
            not isinstance(score, int | float)
            or isinstance(score, bool)
            or not math.isfinite(score)
            for score in calibrated
        ):
            raise ValueError("Calibrator must return one finite score per row")
        return tuple(float(score) for score in calibrated)

    def score(self, features: FeatureMatrix) -> tuple[ScoredCandidate, ...]:
        """Pair calibrated scores with candidate rows without selecting them."""

        return tuple(
            ScoredCandidate(row.document_id, row.candidate_index, row.candidate, score)
            for row, score in zip(
                features.rows, self.calibrated_predict(features), strict=True
            )
        )

    def select(self, scores: Sequence[float]) -> tuple[bool, ...]:
        """Apply the configured selection policy; no policy means no decision."""

        if self.selection_policy is None:
            raise ValueError("No selection policy is configured")
        decisions = tuple(self.selection_policy.select(scores))
        if len(decisions) != len(scores) or any(
            not isinstance(decision, bool) for decision in decisions
        ):
            raise ValueError("Selection policy must return one boolean per score")
        return decisions


def derive_child_seed(seed: int | None, component: str) -> int | None:
    """Derive a stable, component-specific seed without global random state."""

    if seed is None:
        return None
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer or None")
    digest = hashlib.sha256(f"{seed}:{component}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


__all__ = ["ScorerExecutor", "derive_child_seed"]
