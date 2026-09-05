"""Typed YAML composition for scorer, calibration, and selection components."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.registry import Registry
from abrex.scorers.base import Calibrator, Scorer, SelectionPolicy
from abrex.scorers.execution import ScorerExecutor
from abrex.scorers.registry import CALIBRATORS, SCORERS, SELECTION_POLICIES


class ScorerConfig(BaseModel):
    """Validated scorer composition and explicit post-processing hooks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scorer: ComponentSpec
    calibration: ComponentSpec | None = None
    selection: ComponentSpec | None = None
    seed: int | None = None
    feature_config_fingerprint: str | None = None


def scorer_config_from_resolved(
    config: ResolvedConfig, *, section: str = "scorer"
) -> ScorerConfig:
    """Read either ``scorer`` or another explicitly named top-level section."""

    raw = (config.model_extra or {}).get(section)
    if not isinstance(raw, dict):
        raise ValueError(f"Resolved configuration does not contain {section!r}")
    if "scorer" in raw:
        return ScorerConfig.model_validate(raw)
    component = {key: raw[key] for key in ("type", "params") if key in raw}
    options = {
        key: raw[key]
        for key in (
            "calibration",
            "selection",
            "seed",
            "feature_config_fingerprint",
        )
        if key in raw
    }
    return ScorerConfig(scorer=ComponentSpec.model_validate(component), **options)


def create_scorer_executor(
    config: ScorerConfig | ComponentSpec,
    *,
    scorer_registry: Registry[Scorer] = SCORERS,
    calibrator_registry: Registry[Calibrator] = CALIBRATORS,
    selection_registry: Registry[SelectionPolicy] = SELECTION_POLICIES,
) -> ScorerExecutor:
    """Construct a scorer executor from injectable registries."""

    if isinstance(config, ComponentSpec):
        selected = ScorerConfig(scorer=config)
    else:
        selected = config
    entry = scorer_registry.get_entry(selected.scorer.type)
    scorer = create_component(selected.scorer, scorer_registry)
    calibration = (
        create_component(selected.calibration, calibrator_registry)
        if selected.calibration is not None
        else None
    )
    selection = (
        create_component(selected.selection, selection_registry)
        if selected.selection is not None
        else None
    )
    return ScorerExecutor(
        scorer,
        scorer_key=entry.key,
        seed=selected.seed,
        feature_config_fingerprint=selected.feature_config_fingerprint,
        calibrator=calibration,
        selection_policy=selection,
    )


__all__ = [
    "ScorerConfig",
    "create_scorer_executor",
    "scorer_config_from_resolved",
]
