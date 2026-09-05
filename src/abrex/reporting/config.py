"""Typed YAML composition for reporting components."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.registry import Registry
from abrex.reporting.base import Reporter
from abrex.reporting.registry import REPORTERS


class ReportingConfig(BaseModel):
    """Ordered reporter specifications selected by YAML registry keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    reporters: tuple[ComponentSpec, ...] = Field(default_factory=tuple)


def reporting_config_from_resolved(config: ResolvedConfig) -> ReportingConfig:
    """Validate the top-level or nested ``reporting`` section."""

    if not isinstance(config, ResolvedConfig):
        raise TypeError("config must be a ResolvedConfig")
    extras = config.model_extra or {}
    raw = extras.get("reporting", extras)
    if not isinstance(raw, dict):
        raise ValueError("Resolved configuration reporting section must be a mapping")
    values = raw.get("reporters", ())
    if not isinstance(values, list | tuple):
        raise TypeError("Reporting reporters must be a list")
    return ReportingConfig(
        reporters=tuple(ComponentSpec.model_validate(value) for value in values)
    )


def create_reporters(
    config: ReportingConfig | ResolvedConfig,
    *,
    reporter_registry: Registry[Reporter] = REPORTERS,
) -> tuple[Reporter, ...]:
    """Instantiate configured reporters using an injectable registry."""

    selected = (
        reporting_config_from_resolved(config)
        if isinstance(config, ResolvedConfig)
        else config
    )
    if not isinstance(selected, ReportingConfig):
        raise TypeError("config must be a ReportingConfig or ResolvedConfig")
    return tuple(
        create_component(spec, reporter_registry) for spec in selected.reporters
    )


__all__ = ["ReportingConfig", "create_reporters", "reporting_config_from_resolved"]
