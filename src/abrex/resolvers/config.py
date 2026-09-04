"""Typed YAML composition for resolver selection and execution policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.registry import Registry
from abrex.resolvers.base import (
    ExecutionErrorPolicy,
    PredictionValidationMode,
    Resolver,
)
from abrex.resolvers.execution import ResolverExecutor
from abrex.resolvers.registry import RESOLVERS


class ResolverConfig(BaseModel):
    """Validated resolver component and explicit execution policies."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resolver: ComponentSpec
    validation_mode: PredictionValidationMode = "strict"
    error_policy: ExecutionErrorPolicy = "raise"


def resolver_config_from_resolved(config: ResolvedConfig) -> ResolverConfig:
    """Read and validate the resolved top-level ``resolver`` section.

    The normal YAML shape is ``resolver: {type: ..., params: ...}``. A nested
    ``resolver`` key is also accepted so execution options can be kept beside
    the component specification without weakening ``ComponentSpec``.
    """

    raw = config.model_extra.get("resolver") if config.model_extra else None
    if not isinstance(raw, dict):
        raise ValueError("Resolved configuration does not contain a resolver section")
    if "resolver" in raw:
        return ResolverConfig.model_validate(raw)
    component_keys = {"type", "params"}
    component = {key: raw[key] for key in component_keys if key in raw}
    options = {
        key: raw[key] for key in ("validation_mode", "error_policy") if key in raw
    }
    return ResolverConfig(resolver=ComponentSpec.model_validate(component), **options)


def create_resolver_executor(
    config: ResolverConfig | ComponentSpec,
    *,
    registry: Registry[Resolver] = RESOLVERS,
    validation_mode: PredictionValidationMode | None = None,
    error_policy: ExecutionErrorPolicy | None = None,
) -> ResolverExecutor:
    """Instantiate a configured resolver and preserve its canonical key."""

    if isinstance(config, ComponentSpec):
        component = config
        selected_mode: PredictionValidationMode = "strict"
        selected_policy: ExecutionErrorPolicy = "raise"
    else:
        component = config.resolver
        selected_mode = config.validation_mode
        selected_policy = config.error_policy
    entry = registry.get_entry(component.type)
    resolver = create_component(component, registry)
    return ResolverExecutor(
        resolver,
        resolver_key=entry.key,
        validation_mode=validation_mode or selected_mode,
        error_policy=error_policy or selected_policy,
    )


__all__ = [
    "ResolverConfig",
    "create_resolver_executor",
    "resolver_config_from_resolved",
]
