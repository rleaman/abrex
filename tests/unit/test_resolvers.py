"""Unit and contract tests for resolver execution and prediction artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import pytest

from abrex.cli import main
from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)
from abrex.resolvers import (
    PREDICTION_SCHEMA_VERSION,
    PredictionArtifact,
    PredictionDiagnostic,
    PredictionRecord,
    PredictionSerializationError,
    PredictionValidationError,
    PredictionValidationResult,
    Resolver,
    ResolverConfig,
    ResolverExecutionError,
    ResolverExecutor,
    ResolverMetadata,
    create_resolver_executor,
    fingerprint_prediction_artifact,
    prediction_artifact_from_run,
    read_prediction_artifact,
    resolver_config_from_resolved,
    serialize_prediction_artifact,
    serialize_predictions,
    validate_predictions,
    write_prediction_artifact,
    write_predictions,
)
from abrex.resolvers.serialization import (
    prediction_record_from_dict,
    prediction_record_to_dict,
    read_predictions,
)


class FailingResolver:
    identity = "failing"
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        raise RuntimeError(f"failed {document.document_id}")


class InvalidSpanResolver:
    identity = "invalid_span"
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return (
            AbbreviationDefinition(
                document.document_id,
                short_form=TextSpan(0, 2),
                long_form=TextSpan(0, len(document.text) + 1),
            ),
        )


class InvalidTypeResolver:
    identity = "invalid_type"
    version = "test"

    def resolve(self, document: Document) -> Iterable[object]:
        return (object(),)


class DuplicateResolver:
    identity = "duplicate"
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        prediction = AbbreviationDefinition(
            document.document_id, TextSpan(0, 3), TextSpan(4, 9)
        )
        return prediction, prediction


class MaterializeResolver:
    identity = "materialize"
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return cast(Iterable[AbbreviationDefinition], BrokenIterator())


class BrokenIterator:
    def __iter__(self) -> BrokenIterator:
        return self

    def __next__(self) -> AbbreviationDefinition:
        raise RuntimeError("broken iterator")


class NoIdentityResolver:
    identity = ""
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return ()


class NoVersionResolver:
    identity = "no_version"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return ()


class EmptyVersionResolver:
    identity = "empty_version"
    version = ""

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return ()


class BrokenDocuments:
    def __iter__(self) -> BrokenDocuments:
        return self

    def __next__(self) -> Document:
        raise RuntimeError("broken documents")


def test_resolver_protocol_is_structural() -> None:
    assert isinstance(FailingResolver(), Resolver)


def test_toy_resolver_runs_canonical_text_and_attaches_metadata() -> None:
    config = ResolverConfig.model_validate(
        {"resolver": {"type": "toy", "params": {"confidence": 0.8}}}
    )
    document = Document("doc-1", "Tumor necrosis factor (TNF) is important.")
    result = create_resolver_executor(config).resolve_document(document)

    assert result.document_id == "doc-1"
    assert len(result.predictions) == 1
    prediction = result.predictions[0]
    assert prediction.short_form_text == "TNF"
    assert prediction.long_form_text == "Tumor necrosis factor"
    assert prediction.confidence == 0.8
    assert prediction.prediction is not None
    assert prediction.prediction.component == "toy"
    assert prediction.prediction.component_version == "1"
    assert document.text == "Tumor necrosis factor (TNF) is important."


def test_yaml_resolver_selection_is_typed_and_registry_injectable() -> None:
    resolved = ResolvedConfig.model_validate(
        {
            "resolver": {
                "type": "toy",
                "params": {},
                "validation_mode": "permissive",
                "error_policy": "collect",
            }
        }
    )
    config = resolver_config_from_resolved(resolved)
    executor = create_resolver_executor(config)
    assert config.validation_mode == "permissive"
    assert config.error_policy == "collect"
    assert executor.metadata == ResolverMetadata("toy", "1")
    assert executor.error_policy == "collect"


def test_resolver_config_supports_nested_shape_and_missing_section_is_explicit() -> (
    None
):
    nested = ResolvedConfig.model_validate(
        {"resolver": {"resolver": {"type": "toy", "params": {}}}}
    )
    assert resolver_config_from_resolved(nested).resolver.type == "toy"
    with pytest.raises(ValueError, match="does not contain"):
        resolver_config_from_resolved(ResolvedConfig.model_validate({}))
    direct = create_resolver_executor(ComponentSpec(type="toy"))
    assert direct.metadata.key == "toy"


def test_invalid_predictions_are_reported_or_rejected_explicitly() -> None:
    document = Document("doc-1", "ABC means alpha")
    permissive = ResolverExecutor(InvalidSpanResolver(), validation_mode="permissive")
    result = permissive.resolve_document(document)
    assert result.predictions == ()
    assert result.diagnostics[0].code == "INVALID_PREDICTION"
    assert result.diagnostics[0].action == "dropped"

    strict = ResolverExecutor(InvalidSpanResolver())
    with pytest.raises(PredictionValidationError) as raised:
        strict.resolve_document(document)
    assert raised.value.document_id == "doc-1"
    assert raised.value.result.predictions_seen == 1
    assert raised.value.result.diagnostics[0].phase == "validation"


def test_validation_boundary_rejects_bad_document_and_mode() -> None:
    metadata = ResolverMetadata("toy", "1")
    with pytest.raises(TypeError, match="document"):
        validate_predictions(cast(Any, object()), (), resolver=metadata)
    with pytest.raises(ValueError, match="validation mode"):
        validate_predictions(
            Document("doc-1", "text"), (), resolver=metadata, mode=cast(Any, "bad")
        )


def test_invalid_prediction_types_are_diagnosed() -> None:
    result = ResolverExecutor(
        InvalidTypeResolver(),  # type: ignore[arg-type]
        validation_mode="permissive",
    ).resolve_document(Document("doc-1", "text"))
    assert result.diagnostics[0].code == "INVALID_PREDICTION_TYPE"
    assert result.diagnostics[0].details == (("actual_type", "object"),)


def test_execution_failures_are_structured_and_batch_policy_is_explicit() -> None:
    document = Document("doc-1", "text")
    executor = ResolverExecutor(FailingResolver())
    with pytest.raises(ResolverExecutionError) as raised:
        executor.resolve_document(document)
    assert raised.value.resolver_key == "failing"
    assert raised.value.document_id == "doc-1"
    assert raised.value.phase == "resolve"
    assert raised.value.cause_type == "RuntimeError"

    collected = executor.resolve_documents((document,), error_policy="collect")
    assert len(collected.execution_errors) == 1
    assert collected.records[0].diagnostics[0].code == "RESOLVER_EXECUTION_FAILED"
    assert collected.diagnostics == collected.records[0].diagnostics
    with pytest.raises(ResolverExecutionError, match="failed"):
        executor.resolve_documents((document,))


def test_executor_rejects_bad_configuration_and_batch_inputs() -> None:
    document = Document("doc-1", "text")
    with pytest.raises(TypeError, match="callable"):
        ResolverExecutor(cast(Any, object()))
    with pytest.raises(ValueError, match="validation mode"):
        ResolverExecutor(FailingResolver(), validation_mode=cast(Any, "bad"))
    with pytest.raises(ValueError, match="error policy"):
        ResolverExecutor(FailingResolver(), error_policy=cast(Any, "bad"))
    executor = ResolverExecutor(FailingResolver())
    with pytest.raises(TypeError, match="Document"):
        executor.resolve_document(cast(Any, "not a document"))
    with pytest.raises(ResolverExecutionError, match="iterable"):
        executor.resolve_documents(cast(Any, 1))
    with pytest.raises(ResolverExecutionError, match="contain Document"):
        executor.resolve_documents((object(),))
    collected = executor.resolve_documents((object(),), error_policy="collect")
    assert collected.execution_errors[0].phase == "input"
    with pytest.raises(ResolverExecutionError, match="materialized"):
        ResolverExecutor(MaterializeResolver()).resolve_document(
            Document("doc-1", "text")
        )
    with pytest.raises(ValueError, match="error policy"):
        executor.resolve_documents((document,), error_policy=cast(Any, "bad"))
    with pytest.raises(ResolverExecutionError, match="could not be consumed"):
        executor.resolve_documents(BrokenDocuments())
    with pytest.raises(PredictionValidationError):
        ResolverExecutor(InvalidSpanResolver()).resolve_documents((document,))
    with pytest.raises(ValueError, match="resolver identity"):
        ResolverExecutor(NoIdentityResolver())
    assert (
        ResolverExecutor(
            cast(Resolver, NoVersionResolver()), resolver_key="no_version"
        ).metadata.version
        == "unknown"
    )
    assert (
        ResolverExecutor(
            cast(Resolver, EmptyVersionResolver()), resolver_key="empty_version"
        ).metadata.version
        == "unknown"
    )


def test_resolver_metadata_and_diagnostic_values_validate_their_invariants() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ResolverMetadata("", "1")
    metadata = ResolverMetadata("toy", "1")
    assert metadata.version == "1"
    assert metadata.stable_key == "toy"
    defaults = PredictionDiagnostic("info", "OBSERVED", "ok", "doc-1")
    assert defaults.to_dict()["action"] == "observed"
    complete = PredictionDiagnostic(
        "warning",
        "WARN",
        "warning",
        "doc-1",
        prediction_index=0,
        phase="validation",
        details=(("key", "value"),),
    )
    assert complete.to_dict()["details"] == {"key": "value"}
    for kwargs, match in (
        ({"severity": cast(Any, "bad")}, "severity"),
        ({"code": ""}, "code"),
        ({"message": ""}, "message"),
        ({"document_id": ""}, "document_id"),
        ({"action": cast(Any, "bad")}, "action"),
        ({"prediction_index": -1}, "prediction_index"),
        ({"phase": cast(Any, 1)}, "phase"),
        ({"details": cast(Any, (("key", 1),))}, "details"),
    ):
        values: dict[str, Any] = {
            "severity": "info",
            "code": "CODE",
            "message": "message",
            "document_id": "doc-1",
        }
        values.update(kwargs)
        with pytest.raises((TypeError, ValueError), match=match):
            PredictionDiagnostic(**values)

    valid_prediction = AbbreviationDefinition("doc-1")
    valid_record = PredictionRecord("doc-1", predictions=(valid_prediction,))
    with pytest.raises(ValueError, match="document_id"):
        PredictionRecord("")
    with pytest.raises(TypeError, match="AbbreviationDefinition"):
        PredictionRecord("doc-1", predictions=cast(Any, (object(),)))
    with pytest.raises(TypeError, match="PredictionDiagnostic"):
        PredictionRecord("doc-1", diagnostics=cast(Any, (object(),)))
    with pytest.raises(ValueError, match="record_id"):
        PredictionRecord("doc-1", record_id=" ")
    assert valid_record
    with pytest.raises(ValueError, match="non-negative"):
        PredictionValidationResult((), (), -1)
    with pytest.raises(ValueError, match="include"):
        PredictionValidationResult((valid_prediction,), (), 0)


def test_duplicates_are_retained_and_batch_output_has_resolver_metadata() -> None:
    document = Document("doc-1", "ABC means alpha")
    result = ResolverExecutor(DuplicateResolver()).resolve_batch((document,))
    assert len(result.records[0].predictions) == 2
    assert result.resolver == ResolverMetadata("duplicate", "test")


def test_prediction_artifact_is_distinct_deterministic_and_round_trips(
    tmp_path: Path,
) -> None:
    documents = (
        Document("doc-b", "ABC means alpha"),
        Document("doc-a", "ABC means alpha"),
    )
    result = ResolverExecutor(DuplicateResolver()).resolve_documents(documents)
    artifact = PredictionArtifact.from_run(result)
    serialized = serialize_prediction_artifact(artifact)
    assert serialized == serialize_prediction_artifact(
        PredictionArtifact.from_run(
            ResolverExecutor(DuplicateResolver()).resolve_documents(
                tuple(reversed(documents))
            )
        )
    )
    assert PREDICTION_SCHEMA_VERSION in serialized
    assert "gold_annotations" not in serialized
    assert fingerprint_prediction_artifact(artifact)

    path = tmp_path / "predictions.jsonl"
    assert write_prediction_artifact(artifact, path)
    loaded = read_prediction_artifact(
        path, documents={doc.id: doc for doc in documents}
    )
    assert loaded == artifact


def test_prediction_artifact_rejects_empty_and_invalid_input(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(PredictionSerializationError, match="contain a record"):
        read_prediction_artifact(path)


def test_prediction_serialization_handles_metadata_diagnostics_and_bad_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provenance = AnnotationProvenance(
        source_corpus="toy",
        source_record_id="record-1",
        source_annotation_id="annotation-1",
        original_short_form=SourceTextSpan(0, 3, "ABC"),
        original_long_form=SourceTextSpan(text="alpha beta"),
        adapter_identity="adapter",
        adapter_version="1",
        transformation_notes=("kept",),
    )
    prediction = AbbreviationDefinition(
        "doc-1",
        TextSpan(0, 3),
        TextSpan(8, 18),
        "ABC",
        "alpha beta",
        provenance,
        PredictionMetadata(0.5, 2.0, "toy", "1"),
    )
    diagnostic = PredictionDiagnostic(
        "warning", "WARN", "review", "doc-1", prediction_index=0, phase="validation"
    )
    record = PredictionRecord("doc-1", (prediction,), (diagnostic,), "record-1")
    artifact = PredictionArtifact(ResolverMetadata("toy", "1"), (record,))
    assert artifact.to_json() == serialize_prediction_artifact(artifact)
    assert (
        prediction_record_from_dict(json.loads(artifact.to_json()), line_number=1)[1]
        == record
    )
    assert prediction_artifact_from_run(
        ResolverExecutor(DuplicateResolver()).resolve_documents(
            (Document("doc-1", "ABC means alpha"),)
        )
    )
    with pytest.raises(TypeError, match="ResolverMetadata"):
        PredictionArtifact(cast(Any, object()), ())
    with pytest.raises(TypeError, match="tuple"):
        PredictionArtifact(ResolverMetadata("toy", "1"), cast(Any, []))
    with pytest.raises(ValueError, match="Unsupported prediction schema"):
        PredictionArtifact(ResolverMetadata("toy", "1"), (), "bad")
    with pytest.raises(TypeError, match="PredictionArtifact"):
        serialize_prediction_artifact(cast(Any, object()))
    with pytest.raises(TypeError, match="PredictionRecord"):
        prediction_record_to_dict(cast(Any, object()), ResolverMetadata("toy", "1"))

    invalid_records = (
        {"schema_version": "bad"},
        {"schema_version": PREDICTION_SCHEMA_VERSION, "resolver": None},
        {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "resolver": {"key": "toy", "version": "1"},
            "document_id": "doc-1",
            "predictions": {},
        },
        {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "resolver": {"key": "toy", "version": "1"},
            "document_id": "doc-1",
            "predictions": [],
            "diagnostics": {},
        },
        {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "resolver": {"key": "toy", "version": "1"},
            "document_id": "doc-1",
            "predictions": [],
            "record_id": 1,
        },
    )
    for invalid in invalid_records:
        with pytest.raises(PredictionSerializationError):
            prediction_record_from_dict(invalid)

    mapping = json.loads(artifact.to_json())
    mismatched = json.loads(json.dumps(mapping))
    mismatched["predictions"][0]["document_id"] = "other"
    with pytest.raises(PredictionSerializationError, match="does not match"):
        prediction_record_from_dict(mismatched)
    bad_diagnostics = json.loads(json.dumps(mapping))
    bad_diagnostics["diagnostics"] = [
        {
            "severity": "warning",
            "code": "X",
            "message": "x",
            "document_id": "doc-1",
            "action": "observed",
            "details": [],
        }
    ]
    with pytest.raises(PredictionSerializationError, match="details"):
        prediction_record_from_dict(bad_diagnostics)
    for diagnostic_update, match in (
        ({"prediction_index": True}, "prediction_index"),
        ({"phase": 1}, "phase"),
    ):
        malformed_diagnostic = json.loads(json.dumps(mapping))
        malformed_diagnostic["diagnostics"][0] = {
            "severity": "warning",
            "code": "X",
            "message": "x",
            "document_id": "doc-1",
            "action": "observed",
            **diagnostic_update,
        }
        with pytest.raises(PredictionSerializationError, match=match):
            prediction_record_from_dict(malformed_diagnostic)
    for field, value, match in (
        ("short_form", 1, "span"),
        ("short_form", {"start": "bad", "end": 1}, "start"),
    ):
        malformed = json.loads(json.dumps(mapping))
        malformed["predictions"][0][field] = value
        with pytest.raises(PredictionSerializationError, match=match):
            prediction_record_from_dict(malformed)
    empty_forms = json.loads(json.dumps(mapping))
    empty_forms["predictions"][0]["short_form"] = None
    empty_forms["predictions"][0]["long_form"] = None
    empty_forms["predictions"][0]["prediction"] = None
    empty_forms["predictions"][0]["provenance"] = {}
    parsed_empty = prediction_record_from_dict(empty_forms)[1]
    assert parsed_empty.predictions[0].short_form is None
    bad_provenance = json.loads(json.dumps(mapping))
    bad_provenance["predictions"][0]["provenance"] = {"transformation_notes": {}}
    with pytest.raises(PredictionSerializationError, match="transformation_notes"):
        prediction_record_from_dict(bad_provenance)
    bad_metadata = json.loads(json.dumps(mapping))
    bad_metadata["predictions"][0]["prediction"] = {"confidence": "bad"}
    with pytest.raises(PredictionSerializationError, match="confidence"):
        prediction_record_from_dict(bad_metadata)
    for field, value, match in (
        ("document_id", 1, "document_id"),
        ("short_form_text", 1, "short_form_text"),
    ):
        malformed = json.loads(json.dumps(mapping))
        if field == "short_form_text":
            malformed["predictions"][0][field] = value
        else:
            malformed[field] = value
        with pytest.raises(PredictionSerializationError, match=match):
            prediction_record_from_dict(malformed)
    bad_source_coordinates = json.loads(json.dumps(mapping))
    bad_source_coordinates["predictions"][0]["provenance"] = {
        "original_short_form": {"start": "bad", "end": 1}
    }
    with pytest.raises(PredictionSerializationError, match="start"):
        prediction_record_from_dict(bad_source_coordinates)
    bare = AbbreviationDefinition("doc-1", provenance=AnnotationProvenance())
    bare_artifact = PredictionArtifact(
        ResolverMetadata("toy", "1"), (PredictionRecord("doc-1", (bare,)),)
    )
    assert '"provenance":{"adapter_identity":null' in bare_artifact.to_json()

    output = tmp_path / "predictions.jsonl"
    assert write_prediction_artifact(artifact, output)
    assert read_predictions(output) == artifact
    assert write_predictions(artifact, output)
    assert serialize_predictions(artifact) == artifact.to_json()
    assert (
        read_prediction_artifact(
            output, documents={"doc-1": Document("doc-1", "ABC xxx alpha beta")}
        )
        == artifact
    )
    with pytest.raises(PredictionSerializationError, match="Unable to read"):
        read_prediction_artifact(tmp_path / "missing.jsonl")
    with pytest.raises(PredictionSerializationError, match="No canonical"):
        read_prediction_artifact(output, documents={})
    bad_span_path = tmp_path / "bad-span.jsonl"
    bad_span_path.write_text(
        artifact.to_json().replace('"end":18', '"end":100'), encoding="utf-8"
    )
    with pytest.raises(PredictionSerializationError, match="Invalid prediction"):
        read_prediction_artifact(
            bad_span_path,
            documents={"doc-1": Document("doc-1", "ABC xxx alpha beta")},
        )
    blank_path = tmp_path / "blank.jsonl"
    blank_path.write_text("\n", encoding="utf-8")
    with pytest.raises(PredictionSerializationError, match="blank line"):
        read_prediction_artifact(blank_path)
    invalid_json_path = tmp_path / "invalid.jsonl"
    invalid_json_path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(PredictionSerializationError, match="Invalid JSON"):
        read_prediction_artifact(invalid_json_path)
    list_path = tmp_path / "list.jsonl"
    list_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(PredictionSerializationError, match="object required"):
        read_prediction_artifact(list_path)
    inconsistent = artifact.to_json() + artifact.to_json().replace(
        '"key":"toy"', '"key":"other"', 1
    )
    inconsistent_path = tmp_path / "inconsistent.jsonl"
    inconsistent_path.write_text(inconsistent, encoding="utf-8")
    with pytest.raises(PredictionSerializationError, match="Inconsistent"):
        read_prediction_artifact(inconsistent_path)
    with pytest.raises(PredictionSerializationError, match="Unable to write"):
        write_prediction_artifact(artifact, tmp_path / "missing" / "out.jsonl")
    assert capsys.readouterr().out == ""

    cli_output = tmp_path / "cli-predictions.jsonl"
    assert (
        main(
            [
                "resolver",
                "run",
                "docs/examples/resolver-toy.yaml",
                "--input",
                "tests/fixtures/canonical_fixture.jsonl",
                "--output",
                str(cli_output),
            ]
        )
        == 0
    )
    assert cli_output.is_file()
    assert (
        main(
            [
                "resolver",
                "run",
                "docs/examples/resolver-toy.yaml",
                "--input",
                "tests/fixtures/does-not-exist.jsonl",
                "--output",
                str(cli_output),
            ]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err
