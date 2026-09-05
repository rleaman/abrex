"""Explicit, model-independent score transformation strategies."""

from __future__ import annotations

import math
from collections.abc import Sequence


class IdentityCalibrator:
    """Leave scores unchanged; useful when calibration is intentionally absent."""

    identity = "identity"
    version = "1"

    def calibrate(self, scores: Sequence[float]) -> tuple[float, ...]:
        values = tuple(float(score) for score in scores)
        if any(not math.isfinite(score) for score in values):
            raise ValueError("Calibrator received a non-finite score")
        return values


class FixedThreshold:
    """Accept scores greater than or equal to a configured threshold."""

    identity = "fixed"
    version = "1"

    def __init__(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError("threshold value must be a real number")
        if not math.isfinite(value):
            raise ValueError("threshold value must be finite")
        self.value = float(value)

    def select(self, scores: Sequence[float]) -> tuple[bool, ...]:
        values = tuple(float(score) for score in scores)
        if any(not math.isfinite(score) for score in values):
            raise ValueError("Selection policy received a non-finite score")
        return tuple(score >= self.value for score in values)


__all__ = ["FixedThreshold", "IdentityCalibrator"]
