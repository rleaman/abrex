"""Tests for candidate contracts, parenthetical generation, and artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from abrex.candidates import (
    CANDIDATE_SCHEMA_VERSION,
    Candidate,
    CandidateArtifact,
    CandidateDiagnostic,
    CandidateGeneratorMetadata,
    CandidatePipelineConfig,
    CandidateRecord,
    ParentheticalCandidateGenerator,
    create_candidate_pipeline,
    fingerprint_candidate_artifact,
    read_candidate_artifact,
    serialize_candidate_artifact,
    write_candidate_artifact,
)
from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import Document, TextSpan


def test_parenthetical_generator_enumerates_windows_and_prunes() -> None:
    document = Document("d1", "alpha beta (AB) and (x) and (not an acronym!)")
    result = ParentheticalCandidateGenerator().generate(document)
    assert len(result.candidates) == 2
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "short_form_too_short",
        "short_form_invalid",
    }
    assert result.candidates[0].construction == "parenthetical_after_long_form"


def test_generator_configuration_and_missing_context_diagnostic() -> None:
    generator = ParentheticalCandidateGenerator(
        maximum_long_form_words=1, maximum_short_form_length=2
    )
    result = generator.generate(Document("d1", "(AB)"))
    assert result.candidates == ()
    assert result.diagnostics[0].code == "missing_long_form_context"
    with pytest.raises(ValueError, match="Invalid params|extra"):
        ParentheticalCandidateGenerator(unknown=True)


def test_pipeline_registry_composition_and_explicit_deduplication() -> None:
    config = CandidatePipelineConfig(
        generators=(ComponentSpec(type="parenthetical"),), deduplicate=True
    )
    pipeline = create_candidate_pipeline(config)
    artifact = pipeline.generate_artifact((Document("d1", "alpha beta (AB)"),))
    assert artifact.generators == CandidateGeneratorMetadata((("parenthetical", "1"),))
    assert len(artifact.records[0].candidates) == 2
    assert pipeline.generate_documents(()) == ()


def test_candidate_validation_and_artifact_round_trip(tmp_path: Path) -> None:
    candidate = Candidate("d1", TextSpan(12, 14), TextSpan(0, 10), "construction")
    record = CandidateRecord("d1", (candidate,))
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("test", "1"),)), (record,)
    )
    assert CANDIDATE_SCHEMA_VERSION in serialize_candidate_artifact(artifact)
    assert fingerprint_candidate_artifact(artifact)
    path = tmp_path / "candidates.jsonl"
    assert write_candidate_artifact(path, artifact)
    metadata, records = read_candidate_artifact(
        path, documents={"d1": Document("d1", "0123456789abAB")}
    )
    assert CandidateArtifact(metadata, records) == artifact
    with pytest.raises(ValueError, match="document IDs"):
        CandidateRecord("d1", (Candidate("d2", TextSpan(0, 1), TextSpan(1, 2), "x"),))


def test_artifact_rejects_malformed_schema_and_duplicate_records(
    tmp_path: Path,
) -> None:
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("test", "1"),)), (CandidateRecord("d1"),)
    )
    path = tmp_path / "bad.jsonl"
    path.write_text(
        artifact_to_json(artifact).replace(CANDIDATE_SCHEMA_VERSION, "bad"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid candidate artifact"):
        read_candidate_artifact(path)
    duplicate = artifact_to_json(artifact) + artifact_to_json(artifact)
    path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        read_candidate_artifact(path)
    path.write_text(artifact_to_json(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="No canonical"):
        read_candidate_artifact(path, documents={})


def test_diagnostic_and_configured_section_validation() -> None:
    diagnostic = CandidateDiagnostic("info", "code", "message", "d1", "pruned")
    assert diagnostic.details == ()
    config = ResolvedConfig.model_validate(
        {"candidates": {"generators": [{"type": "parenthetical"}]}}
    )
    from abrex.candidates import candidate_pipeline_config_from_resolved

    assert candidate_pipeline_config_from_resolved(config).deduplicate is False


def artifact_to_json(artifact: CandidateArtifact) -> str:
    return serialize_candidate_artifact(artifact)
