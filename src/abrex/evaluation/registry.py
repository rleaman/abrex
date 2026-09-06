"""Default and injectable evaluation component registries."""

from __future__ import annotations

from abrex.evaluation.base import MatchingPolicy, Metric
from abrex.registry import Registry

MATCHING_POLICIES = Registry[MatchingPolicy]("matching_policies")
METRICS = Registry[Metric]("metrics")


def register_builtin_components() -> None:
    """Register the built-in matching and metric plugins once."""

    from abrex.evaluation.matching import (
        ExactPairConfig,
        ExactPairMatchingPolicy,
        ExactSpanConfig,
        ExactSpanMatchingPolicy,
    )
    from abrex.evaluation.metrics import (
        PairPRFConfig,
        PairPRFMetric,
        SpanPRFConfig,
        SpanPRFMetric,
    )

    if "exact_pair" not in MATCHING_POLICIES:
        MATCHING_POLICIES.register(
            "exact_pair", ExactPairMatchingPolicy, config_model=ExactPairConfig
        )
    if "exact_span" not in MATCHING_POLICIES:
        MATCHING_POLICIES.register(
            "exact_span", ExactSpanMatchingPolicy, config_model=ExactSpanConfig
        )
    if "pair_prf" not in METRICS:
        METRICS.register("pair_prf", PairPRFMetric, config_model=PairPRFConfig)
    if "span_prf" not in METRICS:
        METRICS.register("span_prf", SpanPRFMetric, config_model=SpanPRFConfig)


register_builtin_components()

__all__ = ["MATCHING_POLICIES", "METRICS", "register_builtin_components"]
