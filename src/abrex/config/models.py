"""Pydantic models used at the configuration boundary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ComponentSpec(BaseModel):
    """A registry key and its implementation-specific parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class ProjectConfig(BaseModel):
    """Reproducibility settings common to experiment configurations."""

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str | None = None
    seed: int | None = None


class RuntimeConfig(BaseModel):
    """Process-level behavior settings."""

    model_config = ConfigDict(extra="allow", frozen=True)

    strict: bool | None = None
    log_level: str | None = None


class OutputConfig(BaseModel):
    """Artifact-output settings retained by the resolved configuration."""

    model_config = ConfigDict(extra="allow", frozen=True)

    root: str | None = None
    save_predictions: bool | None = None
    save_match_records: bool | None = None
    save_resolved_config: bool | None = None


class ResolvedConfig(BaseModel):
    """Validated, fully merged configuration.

    Extra top-level sections are retained because future tasks own their
    component-specific schemas. Sections passed to a registry are validated
    as :class:`ComponentSpec` by the composition layer.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    project: ProjectConfig | None = None
    runtime: RuntimeConfig | None = None
    output: OutputConfig | None = None

    def component(self, name: str) -> ComponentSpec:
        """Validate and return a named single-component section."""

        value = self.model_extra.get(name) if self.model_extra else None
        return ComponentSpec.model_validate(value)
