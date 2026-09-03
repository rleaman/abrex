"""Typed configuration loading and component composition."""

from abrex.config.composition import create_component
from abrex.config.loader import (
    ConfigError,
    dump_resolved_config,
    load_config_layer,
    load_resolved_config,
    merge_config_layers,
    serialize_resolved_config,
)
from abrex.config.models import ComponentSpec, ResolvedConfig

__all__ = [
    "ComponentSpec",
    "ConfigError",
    "ResolvedConfig",
    "create_component",
    "dump_resolved_config",
    "load_config_layer",
    "load_resolved_config",
    "merge_config_layers",
    "serialize_resolved_config",
]
