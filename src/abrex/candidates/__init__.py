"""Candidate enumeration contracts, generators, pipelines, and artifacts."""

from abrex.candidates.base import (
    Candidate,
    CandidateArtifact,
    CandidateDiagnostic,
    CandidateGenerationResult,
    CandidateGenerator,
    CandidateGeneratorMetadata,
    CandidatePipeline,
    CandidateRecord,
)
from abrex.candidates.generators import (
    PARENTHETICAL_GENERATOR_VERSION,
    NestedParentheticalCandidateConfig,
    NestedParentheticalCandidateGenerator,
    ParentheticalCandidateConfig,
    ParentheticalCandidateGenerator,
    ReverseOrderCandidateConfig,
    ReverseOrderCandidateGenerator,
    StructuredRelationCandidateConfig,
    StructuredRelationCandidateGenerator,
)
from abrex.candidates.pipeline import (
    CandidatePipelineConfig,
    ConfiguredCandidatePipeline,
    candidate_pipeline_config_from_resolved,
    create_candidate_pipeline,
)
from abrex.candidates.registry import GENERATORS, register_builtin_components
from abrex.candidates.serialization import (
    CANDIDATE_SCHEMA_VERSION,
    CandidateSerializationError,
    fingerprint_candidate_artifact,
    read_candidate_artifact,
    serialize_candidate_artifact,
    write_candidate_artifact,
)

__all__ = [
    "CANDIDATE_SCHEMA_VERSION",
    "GENERATORS",
    "PARENTHETICAL_GENERATOR_VERSION",
    "Candidate",
    "CandidateArtifact",
    "CandidateDiagnostic",
    "CandidateGenerationResult",
    "CandidateGenerator",
    "CandidateGeneratorMetadata",
    "CandidatePipeline",
    "CandidatePipelineConfig",
    "CandidateRecord",
    "CandidateSerializationError",
    "ConfiguredCandidatePipeline",
    "ParentheticalCandidateConfig",
    "ParentheticalCandidateGenerator",
    "NestedParentheticalCandidateConfig",
    "NestedParentheticalCandidateGenerator",
    "ReverseOrderCandidateConfig",
    "ReverseOrderCandidateGenerator",
    "StructuredRelationCandidateConfig",
    "StructuredRelationCandidateGenerator",
    "candidate_pipeline_config_from_resolved",
    "create_candidate_pipeline",
    "fingerprint_candidate_artifact",
    "read_candidate_artifact",
    "register_builtin_components",
    "serialize_candidate_artifact",
    "write_candidate_artifact",
]
