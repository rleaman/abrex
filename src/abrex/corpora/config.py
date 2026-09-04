"""Typed configuration and composition for corpus builds."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import ComponentSpec, ResolvedConfig, create_component
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


class CorpusConfig(BaseModel):
    """Typed YAML configuration for one adapter and normalizer sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: ComponentSpec
    source: SourceResourceConfig = Field(
        default_factory=lambda: SourceResourceConfig(identifier="embedded")
    )
    normalizers: tuple[ComponentSpec, ...] = ()
    strict: bool = False


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
    "SourceResourceConfig",
    "corpus_config_from_resolved",
    "create_corpus_pipeline",
]
