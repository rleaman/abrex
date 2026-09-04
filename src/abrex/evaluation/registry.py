"""Default and injectable evaluation component registries."""

from __future__ import annotations

from abrex.evaluation.base import MatchingPolicy, Metric
from abrex.registry import Registry

MATCHING_POLICIES = Registry[MatchingPolicy]("matching_policies")
METRICS = Registry[Metric]("metrics")


def register_builtin_components() -> None:
    """Register the initial exact matching and pair metric plugins once."""

    from abrex.evaluation.matching import ExactPairConfig, ExactPairMatchingPolicy
    from abrex.evaluation.metrics import PairPRFConfig, PairPRFMetric

    if "exact_pair" not in MATCHING_POLICIES:
        MATCHING_POLICIES.register(
            "exact_pair", ExactPairMatchingPolicy, config_model=ExactPairConfig
        )
    if "pair_prf" not in METRICS:
        METRICS.register("pair_prf", PairPRFMetric, config_model=PairPRFConfig)


register_builtin_components()

__all__ = ["MATCHING_POLICIES", "METRICS", "register_builtin_components"]
