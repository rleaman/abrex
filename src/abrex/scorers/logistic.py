"""Small dependency-free logistic-regression research baseline."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from abrex.features import FeatureMatrix
from abrex.scorers.artifacts import fingerprint_feature_schema
from abrex.scorers.base import ScoringDataset


class LogisticRegressionConfig(BaseModel):
    """Validated CPU-oriented optimization settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    learning_rate: float = Field(default=0.1, gt=0, le=10)
    max_iter: int = Field(default=500, ge=1, le=100_000)
    l2: float = Field(default=0.001, ge=0, le=100)
    class_weight: str = "none"

    def model_post_init(self, __context: object) -> None:
        if self.class_weight not in {"none", "balanced"}:
            raise ValueError("class_weight must be none or balanced")


class LogisticRegressionScorer:
    """Deterministic batch-gradient logistic regression over feature rows."""

    identity = "logistic_regression"
    version = "1"

    def __init__(self, **params: object) -> None:
        self.config = LogisticRegressionConfig.model_validate(params)
        self.weights: tuple[float, ...] | None = None
        self.bias = 0.0
        self.feature_schema_fingerprint: str | None = None

    def fit(
        self,
        train: ScoringDataset,
        *,
        dev: ScoringDataset | None = None,
        seed: int | None = None,
    ) -> None:
        del dev, seed
        if not train.features.rows:
            raise ValueError("logistic regression requires training rows")
        width = len(train.features.schema.columns)
        weights = [0.0] * width
        bias = 0.0
        positives = sum(label >= 0.5 for label in train.labels)
        negatives = len(train.labels) - positives
        positive_weight = negative_weight = 1.0
        if self.config.class_weight == "balanced":
            positive_weight = len(train.labels) / (2 * positives) if positives else 0.0
            negative_weight = len(train.labels) / (2 * negatives) if negatives else 0.0
        for _ in range(self.config.max_iter):
            gradients = [0.0] * width
            bias_gradient = 0.0
            for row, label in zip(train.features.rows, train.labels, strict=True):
                probability = _sigmoid(
                    bias
                    + sum(
                        weight * value
                        for weight, value in zip(weights, row.values, strict=True)
                    )
                )
                weight = positive_weight if label >= 0.5 else negative_weight
                error = (probability - label) * weight
                for index, value in enumerate(row.values):
                    gradients[index] += error * value
                bias_gradient += error
            scale = 1.0 / len(train.labels)
            for index in range(width):
                gradients[index] = (
                    gradients[index] * scale + self.config.l2 * weights[index]
                )
                weights[index] -= self.config.learning_rate * gradients[index]
            bias -= self.config.learning_rate * bias_gradient * scale
        self.weights = tuple(weights)
        self.bias = bias
        self.feature_schema_fingerprint = fingerprint_feature_schema(
            train.features.schema
        )

    def predict(self, features: FeatureMatrix) -> tuple[float, ...]:
        """Return probabilities and reject feature-schema changes."""

        if self.weights is None or self.feature_schema_fingerprint is None:
            raise ValueError("logistic regression has not been fitted")
        # Keep the public protocol typed while allowing artifact-loading tools
        # to pass the validated FeatureMatrix implementation.
        if (
            fingerprint_feature_schema(features.schema)
            != self.feature_schema_fingerprint
        ):
            raise ValueError("logistic regression feature schema does not match")
        return tuple(
            _sigmoid(
                self.bias
                + sum(
                    weight * value
                    for weight, value in zip(self.weights, row.values, strict=True)
                )
            )
            for row in features.rows
        )

    def save(self, path: Path) -> None:
        if self.weights is None or self.feature_schema_fingerprint is None:
            raise ValueError("cannot save an unfitted logistic regression")
        path.write_text(
            json.dumps(
                {
                    "weights": self.weights,
                    "bias": self.bias,
                    "feature_schema_fingerprint": self.feature_schema_fingerprint,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def load(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        weights = data.get("weights")
        fingerprint = data.get("feature_schema_fingerprint")
        if not isinstance(weights, list) or not all(
            isinstance(value, int | float) for value in weights
        ):
            raise ValueError("invalid logistic regression weights")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError("missing logistic regression feature schema fingerprint")
        self.weights = tuple(float(value) for value in weights)
        self.bias = float(data["bias"])
        self.feature_schema_fingerprint = fingerprint


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


__all__ = ["LogisticRegressionConfig", "LogisticRegressionScorer"]
