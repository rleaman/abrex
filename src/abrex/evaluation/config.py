"""Typed YAML composition for evaluation policies and metrics."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.evaluation.base import MatchingPolicy, Metric
from abrex.evaluation.evaluator import Evaluator
from abrex.evaluation.registry import MATCHING_POLICIES, METRICS
from abrex.registry import Registry


class EvaluationConfig(BaseModel):
    """Validated matching policy and ordered metric plugin specifications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    matching: ComponentSpec
    metrics: tuple[ComponentSpec, ...] = Field(
        default_factory=lambda: (ComponentSpec(type="pair_prf"),)
    )


def evaluation_config_from_resolved(config: ResolvedConfig) -> EvaluationConfig:
    """Read the top-level or nested ``evaluation`` YAML section."""

    if not isinstance(config, ResolvedConfig):
        raise TypeError("config must be a ResolvedConfig")
    extras = config.model_extra or {}
    raw = extras.get("evaluation", extras)
    if not isinstance(raw, dict):
        raise ValueError("Resolved configuration evaluation section must be a mapping")
    if "matching" not in raw:
        raise ValueError("Resolved configuration does not contain matching")
    matching = ComponentSpec.model_validate(raw["matching"])
    raw_metrics = raw.get("metrics", (ComponentSpec(type="pair_prf"),))
    if not isinstance(raw_metrics, list | tuple):
        raise TypeError("Evaluation metrics must be a list")
    return EvaluationConfig(
        matching=matching,
        metrics=tuple(ComponentSpec.model_validate(item) for item in raw_metrics),
    )


def create_evaluator(
    config: EvaluationConfig | ResolvedConfig,
    *,
    matching_registry: Registry[MatchingPolicy] = MATCHING_POLICIES,
    metric_registry: Registry[Metric] = METRICS,
) -> Evaluator:
    """Instantiate a YAML-selected evaluator using injectable registries."""

    selected = (
        evaluation_config_from_resolved(config)
        if isinstance(config, ResolvedConfig)
        else config
    )
    if not isinstance(selected, EvaluationConfig):
        raise TypeError("config must be an EvaluationConfig or ResolvedConfig")
    policy = create_component(selected.matching, matching_registry)
    metrics = tuple(
        create_component(spec, metric_registry) for spec in selected.metrics
    )
    policy_entry = matching_registry.get_entry(selected.matching.type)
    return Evaluator(
        policy,
        metrics,
        matching_policy_key=policy_entry.key,
    )


__all__ = [
    "EvaluationConfig",
    "create_evaluator",
    "evaluation_config_from_resolved",
]
