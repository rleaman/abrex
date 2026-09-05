"""Configurable candidate-generation application service."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates.base import (
    Candidate,
    CandidateArtifact,
    CandidateDiagnostic,
    CandidateGenerator,
    CandidateGeneratorMetadata,
    CandidateRecord,
)
from abrex.candidates.registry import GENERATORS
from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.domain import Document
from abrex.registry import Registry


class CandidatePipelineConfig(BaseModel):
    """Typed YAML composition for candidate generators and deduplication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generators: tuple[ComponentSpec, ...] = Field(min_length=1)
    deduplicate: bool = False


@dataclass(frozen=True, slots=True)
class ConfiguredCandidatePipeline:
    """Combine registered generators without accepting or scoring candidates."""

    generators: tuple[CandidateGenerator, ...]
    deduplicate: bool = False

    def __post_init__(self) -> None:
        if not self.generators:
            raise ValueError("Candidate pipeline requires at least one generator")

    @property
    def metadata(self) -> CandidateGeneratorMetadata:
        """Return stable generator identities for artifact metadata."""

        return CandidateGeneratorMetadata(
            tuple(
                (generator.identity, generator.version) for generator in self.generators
            )
        )

    def generate(self, document: Document) -> CandidateRecord:
        """Generate candidates for one document and audit deduplication."""

        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for generator in self.generators:
            result = generator.generate(document)
            if result.document_id != document.document_id:
                raise ValueError(
                    f"Generator {generator.identity!r} returned the wrong document ID"
                )
            candidates.extend(result.candidates)
            diagnostics.extend(result.diagnostics)
        if self.deduplicate:
            unique: list[Candidate] = []
            seen: set[tuple[object, ...]] = set()
            for candidate in candidates:
                key = (
                    candidate.document_id,
                    candidate.short_form,
                    candidate.long_form,
                    candidate.construction,
                )
                if key in seen:
                    diagnostics.append(
                        CandidateDiagnostic(
                            "info",
                            "duplicate_candidate_pruned",
                            "Duplicate candidate removed by configured pipeline policy",
                            document.document_id,
                            "pruned",
                        )
                    )
                else:
                    seen.add(key)
                    unique.append(candidate)
            candidates = unique
        return CandidateRecord(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )

    def generate_documents(
        self, documents: Iterable[Document]
    ) -> tuple[CandidateRecord, ...]:
        """Generate records in input order for deterministic embedding."""

        return tuple(self.generate(document) for document in documents)

    def generate_artifact(self, documents: Iterable[Document]) -> CandidateArtifact:
        """Generate an immutable artifact with generator identity metadata."""

        return CandidateArtifact(self.metadata, self.generate_documents(documents))


def create_candidate_pipeline(
    config: CandidatePipelineConfig,
    *,
    registry: Registry[CandidateGenerator] = GENERATORS,
) -> ConfiguredCandidatePipeline:
    """Instantiate a typed candidate pipeline from an injectable registry."""

    return ConfiguredCandidatePipeline(
        tuple(create_component(spec, registry) for spec in config.generators),
        config.deduplicate,
    )


def candidate_pipeline_config_from_resolved(
    config: ResolvedConfig,
) -> CandidatePipelineConfig:
    """Read the top-level ``candidates`` YAML section."""

    raw = config.model_extra.get("candidates") if config.model_extra else None
    if not isinstance(raw, dict):
        raise ValueError("Resolved configuration does not contain a candidates section")
    return CandidatePipelineConfig.model_validate(raw)


__all__ = [
    "CandidatePipelineConfig",
    "ConfiguredCandidatePipeline",
    "candidate_pipeline_config_from_resolved",
    "create_candidate_pipeline",
]
