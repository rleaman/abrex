"""YAML loading, deterministic merging, environment expansion, and output."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from abrex.config.models import ResolvedConfig

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ValueError):
    """Raised for malformed, ambiguous, or unresolvable configuration."""


class _EnvironmentReference:
    def __init__(self, name: str) -> None:
        self.name = name


class _SafeConfigLoader(yaml.SafeLoader):
    pass


def _environment_constructor(
    loader: _SafeConfigLoader, node: yaml.nodes.Node
) -> _EnvironmentReference:
    value = loader.construct_scalar(cast(yaml.nodes.ScalarNode, node))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ConfigError(f"Invalid !env variable name: {value!r}")
    return _EnvironmentReference(value)


_SafeConfigLoader.add_constructor("!env", _environment_constructor)


def _format_path(path: str) -> str:
    return path or "<root>"


def _interpolate(value: Any, environment: Mapping[str, str], path: str) -> Any:
    if isinstance(value, _EnvironmentReference):
        if value.name not in environment:
            raise ConfigError(
                f"Missing environment variable {value.name!r} at {_format_path(path)}"
            )
        return environment[value.name]
    if isinstance(value, Mapping):
        return {
            key: _interpolate(item, environment, f"{path}.{key}" if path else str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _interpolate(item, environment, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        matches = tuple(_ENV_PATTERN.finditer(value))
        if not matches:
            return value
        missing = next(
            (match.group(1) for match in matches if match.group(1) not in environment),
            None,
        )
        if missing is not None:
            raise ConfigError(
                f"Missing environment variable {missing!r} at {_format_path(path)}"
            )
        return _ENV_PATTERN.sub(lambda match: environment[match.group(1)], value)
    return value


def load_config_layer(path: Path) -> dict[str, Any]:
    """Load one YAML mapping and report file/line context on failure."""

    try:
        with path.open("r", encoding="utf-8") as stream:
            loaded = yaml.load(stream, Loader=_SafeConfigLoader)
    except OSError as error:
        raise ConfigError(f"Unable to read configuration {path}: {error}") from error
    except yaml.YAMLError as error:
        problem = getattr(error, "problem", str(error))
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"Malformed YAML in {path}{location}: {problem}") from error

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration root in {path} must be a YAML mapping")
    return loaded


def _merge_mapping(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(left)
    for key, value in right.items():
        previous = result.get(key)
        if isinstance(previous, Mapping) and isinstance(value, Mapping):
            result[key] = _merge_mapping(previous, value)
        else:
            result[key] = value
    return result


def merge_config_layers(layers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Merge layers in order; mappings recurse and every other value replaces."""

    merged: dict[str, Any] = {}
    for layer in layers:
        if not isinstance(layer, Mapping):
            raise ConfigError("Each configuration layer must be a mapping")
        merged = _merge_mapping(merged, layer)
    return merged


def load_resolved_config(
    paths: Sequence[Path], *, environment: Mapping[str, str] | None = None
) -> ResolvedConfig:
    """Load, merge, interpolate, and validate explicit YAML layers."""

    if not paths:
        raise ConfigError("At least one configuration path is required")
    merged = merge_config_layers(tuple(load_config_layer(path) for path in paths))
    expanded = _interpolate(
        merged, environment if environment is not None else os.environ, ""
    )
    try:
        return ResolvedConfig.model_validate(expanded)
    except ValidationError as error:
        raise ConfigError(f"Invalid resolved configuration: {error}") from error


def serialize_resolved_config(config: ResolvedConfig, *, format: str = "yaml") -> str:
    """Serialize a resolved config deterministically as YAML or JSON."""

    data = config.model_dump(mode="json", exclude_none=True)
    if format == "yaml":
        return yaml.safe_dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    raise ConfigError(f"Unsupported config serialization format: {format!r}")


def dump_resolved_config(
    config: ResolvedConfig, path: Path, *, format: str = "yaml"
) -> None:
    """Write a resolved config with explicit UTF-8 encoding."""

    try:
        path.write_text(
            serialize_resolved_config(config, format=format), encoding="utf-8"
        )
    except OSError as error:
        raise ConfigError(
            f"Unable to write resolved configuration {path}: {error}"
        ) from error
