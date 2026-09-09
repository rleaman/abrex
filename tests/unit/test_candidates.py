"""Tests for candidate contracts, parenthetical generation, and artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from abrex.candidates import (
    CANDIDATE_SCHEMA_VERSION,
    Candidate,
    CandidateArtifact,
    CandidateDiagnostic,
    CandidateGenerationResult,
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
from abrex.domain import AnnotationProvenance, Document, TextSpan


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


def test_candidate_contracts_reject_untraceable_or_inconsistent_values() -> None:
    span = TextSpan(0, 1)
    provenance = AnnotationProvenance(adapter_identity="fixture")
    candidate = Candidate("doc", span, span, "fixture", provenance)
    candidate.validate_against(Document("doc", "x"))
    with pytest.raises(ValueError, match="document_id"):
        Candidate("", span, span, "fixture")
    with pytest.raises(TypeError, match="short_form"):
        Candidate("doc", "bad", span, "fixture")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="long_form"):
        Candidate("doc", span, "bad", "fixture")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="construction"):
        Candidate("doc", span, span, " ")
    with pytest.raises(TypeError, match="provenance"):
        Candidate("doc", span, span, "fixture", object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not match"):
        candidate.validate_against(Document("other", "x"))

    diagnostic = CandidateDiagnostic("info", "seen", "message", "doc", "observed")
    with pytest.raises(ValueError, match="severity"):
        CandidateDiagnostic("fatal", "x", "x", "doc", "observed")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="action"):
        CandidateDiagnostic("info", "x", "x", "doc", "lost")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="code"):
        CandidateDiagnostic("info", " ", "x", "doc", "observed")
    with pytest.raises(TypeError, match="details"):
        CandidateDiagnostic(
            "info",
            "x",
            "x",
            "doc",
            "observed",
            (("key", 1),),  # type: ignore[arg-type]
        )

    result = CandidateGenerationResult("doc", (candidate,), (diagnostic,))
    assert result.document_id == "doc"
    with pytest.raises(ValueError, match="document_id"):
        CandidateGenerationResult("")
    with pytest.raises(TypeError, match="candidates"):
        CandidateGenerationResult("doc", [candidate])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="diagnostics"):
        CandidateGenerationResult("doc", (), [diagnostic])  # type: ignore[arg-type]


def test_candidate_artifact_contracts_reject_ambiguous_identity() -> None:
    span = TextSpan(0, 1)
    with pytest.raises(ValueError, match="metadata"):
        CandidateGeneratorMetadata(())
    with pytest.raises(ValueError, match="metadata"):
        CandidateGeneratorMetadata((("", "1"),))
    diagnostic = CandidateDiagnostic("info", "x", "x", "other", "observed")
    with pytest.raises(ValueError, match="diagnostic document IDs"):
        CandidateRecord("doc", diagnostics=(diagnostic,))
    metadata = CandidateGeneratorMetadata((("fixture", "1"),))
    record = CandidateRecord("doc")
    with pytest.raises(TypeError, match="generators"):
        CandidateArtifact(object(), (record,))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="records"):
        CandidateArtifact(metadata, [record])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="duplicate"):
        CandidateArtifact(metadata, (record, record))
    with pytest.raises(ValueError, match="exceeds text length"):
        Candidate("doc", TextSpan(1, 2), span, "x").validate_against(
            Document("doc", "x")
        )


def test_candidate_reader_rejects_cross_record_metadata_and_bad_shapes(
    tmp_path: Path,
) -> None:
    valid = artifact_to_json(
        CandidateArtifact(
            CandidateGeneratorMetadata((("first", "1"),)),
            (CandidateRecord("one"),),
        )
    )
    second = artifact_to_json(
        CandidateArtifact(
            CandidateGeneratorMetadata((("second", "1"),)),
            (CandidateRecord("two"),),
        )
    )
    path = tmp_path / "candidates.jsonl"
    path.write_text(valid + second, encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent generator metadata"):
        read_candidate_artifact(path)

    for payload, message in (
        ("", "must contain a record"),
        ("[]\n", "object required"),
        (
            valid.replace('"candidates":[]', '"candidates":{}'),
            "must be arrays",
        ),
        (
            valid.replace('"diagnostics":[]', '"diagnostics":{}'),
            "must be arrays",
        ),
        (
            valid.replace(
                '"generators":[{"key":"first","version":"1"}]', '"generators":[1]'
            ),
            "metadata must be objects",
        ),
    ):
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            read_candidate_artifact(path)


def test_candidate_writer_wraps_filesystem_failure(tmp_path: Path) -> None:
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("fixture", "1"),)), (CandidateRecord("doc"),)
    )
    with pytest.raises(ValueError, match="Unable to write"):
        write_candidate_artifact(tmp_path / "missing" / "artifact.jsonl", artifact)


def artifact_to_json(artifact: CandidateArtifact) -> str:
    return serialize_candidate_artifact(artifact)
