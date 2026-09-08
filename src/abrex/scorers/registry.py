"""Injectable registries for scorer lifecycle components."""

from __future__ import annotations

from abrex.registry import Registry
from abrex.scorers.base import Calibrator, Scorer, SelectionPolicy

SCORERS = Registry[Scorer]("scorers")
CALIBRATORS = Registry[Calibrator]("scorer_calibrators")
SELECTION_POLICIES = Registry[SelectionPolicy]("scorer_selection_policies")


def register_builtin_components() -> None:
    """Register only neutral plumbing components supplied by ABREX."""

    from abrex.scorers.logistic import (
        LogisticRegressionConfig,
        LogisticRegressionScorer,
    )
    from abrex.scorers.strategies import FixedThreshold, IdentityCalibrator

    if "identity" not in CALIBRATORS:
        CALIBRATORS.register("identity", IdentityCalibrator)
    if "fixed" not in SELECTION_POLICIES:
        SELECTION_POLICIES.register("fixed", FixedThreshold)
    if "logistic_regression" not in SCORERS:
        SCORERS.register(
            "logistic_regression",
            LogisticRegressionScorer,
            config_model=LogisticRegressionConfig,
        )


register_builtin_components()

__all__ = [
    "CALIBRATORS",
    "SCORERS",
    "SELECTION_POLICIES",
    "register_builtin_components",
]
