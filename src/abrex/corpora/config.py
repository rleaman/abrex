"""Typed configuration and composition for corpus builds."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abrex.config import (
    ComponentSpec,
    ConfigError,
    ResolvedConfig,
    create_component,
    load_config_layer,
)
from abrex.corpora.base import (
    CorpusAdapter,
    CorpusPipeline,
    NormalizationStep,
    SourceResource,
)
from abrex.corpora.registry import CORPUS_ADAPTERS, NORMALIZERS
from abrex.registry import Registry


class SourceResourceConfig(BaseModel):
    """YAML representation of a source-resource descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str = Field(min_length=1)
    location: Path | None = None
    format: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_resource(self) -> SourceResource:
        """Convert validated boundary data into the adapter descriptor."""

        return SourceResource(
            identifier=self.identifier,
            location=self.location,
            format=self.format,
            metadata=tuple(sorted(self.metadata.items())),
        )


class CorpusOutputConfig(BaseModel):
    """Repository-relative names for one canonical corpus artifact pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    directory: Path
    jsonl: str = "canonical.jsonl"
    manifest: str = "manifest.json"

    @field_validator("jsonl", "manifest")
    @classmethod
    def _require_relative_filename(cls, value: str) -> str:
        posix_path = PurePosixPath(value)
        windows_path = PureWindowsPath(value)
        if (
            not value.strip()
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or windows_path.root
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError("artifact names must be non-empty relative paths")
        return value

    @property
    def jsonl_path(self) -> Path:
        """Return the configured canonical JSONL path."""

        return self.directory / self.jsonl

    @property
    def manifest_path(self) -> Path:
        """Return the configured canonical manifest path."""

        return self.directory / self.manifest


class CorpusConfig(BaseModel):
    """Typed YAML configuration for one adapter and normalizer sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: ComponentSpec
    source: SourceResourceConfig = Field(
        default_factory=lambda: SourceResourceConfig(identifier="embedded")
    )
    normalizers: tuple[ComponentSpec, ...] = ()
    strict: bool = False
    output: CorpusOutputConfig | None = None


class CorpusBuildGroupConfig(BaseModel):
    """One named group of corpus configuration paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    configs: tuple[Path, ...] = Field(min_length=1)


class CorpusBuildGroupsConfig(BaseModel):
    """Configuration-driven groups of corpus builds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    groups: dict[str, CorpusBuildGroupConfig]

    def paths_for(self, name: str) -> tuple[Path, ...]:
        """Return paths for a group, with an actionable unknown-group error."""

        try:
            return self.groups[name].configs
        except KeyError as error:
            available = ", ".join(sorted(self.groups)) or "<none>"
            raise ConfigError(
                f"Unknown corpus build group {name!r}; available groups: {available}"
            ) from error


def load_corpus_build_groups(path: Path) -> CorpusBuildGroupsConfig:
    """Load and validate a configuration-driven corpus group manifest."""

    raw = load_config_layer(path)
    try:
        return CorpusBuildGroupsConfig.model_validate(raw)
    except ValueError as error:
        raise ConfigError(
            f"Invalid corpus group configuration {path}: {error}"
        ) from error


def corpus_config_from_resolved(config: ResolvedConfig) -> CorpusConfig:
    """Validate the resolved ``corpus`` section at the application boundary."""

    raw = config.model_extra.get("corpus") if config.model_extra else None
    if raw is None:
        raise ValueError("Resolved configuration does not contain a corpus section")
    return CorpusConfig.model_validate(raw)


def create_corpus_pipeline(
    config: CorpusConfig,
    *,
    adapter_registry: Registry[CorpusAdapter] = CORPUS_ADAPTERS,
    normalizer_registry: Registry[NormalizationStep] = NORMALIZERS,
) -> CorpusPipeline:
    """Instantiate a typed corpus pipeline from isolated registries."""

    # The public Registry type is intentionally accepted through the generic
    # composition helper; local registries are useful in tests and embedding.
    adapter: CorpusAdapter = create_component(config.adapter, adapter_registry)
    normalizers: tuple[NormalizationStep, ...] = tuple(
        create_component(spec, normalizer_registry) for spec in config.normalizers
    )
    return CorpusPipeline(adapter, normalizers, strict=config.strict)


__all__ = [
    "CorpusConfig",
    "CorpusBuildGroupConfig",
    "CorpusBuildGroupsConfig",
    "CorpusOutputConfig",
    "SourceResourceConfig",
    "corpus_config_from_resolved",
    "create_corpus_pipeline",
    "load_corpus_build_groups",
]
