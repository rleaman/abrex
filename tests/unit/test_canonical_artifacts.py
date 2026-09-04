"""Tests for canonical validation, JSONL artifacts, and dataset manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from abrex.cli import main
from abrex.config import ComponentSpec
from abrex.corpora import (
    CANONICAL_SCHEMA_VERSION,
    AdapterDiagnostic,
    CanonicalSerializationError,
    CanonicalValidationError,
    CanonicalValidator,
    CorpusConfig,
    DatasetManifest,
    DiagnosticsSummary,
    SourceResourceConfig,
    ValidationIssue,
    ValidationSummary,
    build_dataset_manifest,
    create_corpus_pipeline,
    fingerprint_records,
    read_canonical_dataset,
    read_canonical_jsonl,
    read_dataset_manifest,
    record_from_dict,
    record_to_dict,
    serialize_records,
    write_canonical_dataset,
    write_canonical_jsonl,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)


def _record(record_id: str = "record") -> CorpusRecord:
    document = Document(record_id, "Alpha beta (AB).")
    annotation = AbbreviationDefinition(
        record_id,
        short_form=TextSpan(12, 14),
        long_form=TextSpan(0, 10),
        short_form_text="AB",
        long_form_text="Alpha beta",
        provenance=AnnotationProvenance(
            source_corpus="toy",
            source_record_id=record_id,
            source_annotation_id="ann-1",
            original_short_form=SourceTextSpan(12, 14, "AB"),
            original_long_form=SourceTextSpan(0, 10, "Alpha beta"),
            adapter_identity="toy",
            adapter_version="1",
            transformation_notes=("normalized",),
        ),
        prediction=PredictionMetadata(
            confidence=0.5, score=2.0, component="toy", component_version="1"
        ),
    )
    return CorpusRecord(
        document,
        (annotation,),
        record_id=record_id,
        provenance=AnnotationProvenance(source_record_id=record_id),
    )


def _fixture_result() -> Any:
    config = CorpusConfig(
        adapter=ComponentSpec(type="fixture"),
        source=SourceResourceConfig(identifier="embedded-fixture"),
        normalizers=(ComponentSpec(type="trim_captured_text"),),
    )
    return create_corpus_pipeline(config).build(config.source.to_resource())


def test_golden_jsonl_and_domain_round_trip() -> None:
    result = _fixture_result()
    expected = Path("tests/fixtures/canonical_fixture.jsonl").read_text(
        encoding="utf-8"
    )
    assert serialize_records(result.records) == expected
    loaded = read_canonical_jsonl(Path("tests/fixtures/canonical_fixture.jsonl"))
    assert loaded == result.records
    record = _record()
    assert record_from_dict(record_to_dict(record)) == record


def test_validation_reports_repair_drop_ambiguous_and_unscoreable() -> None:
    document = Document("doc", "AB alpha beta")
    complete = AbbreviationDefinition(
        "doc", TextSpan(0, 2), TextSpan(3, 8), "AB", "alpha"
    )
    overlapping = AbbreviationDefinition(
        "doc", TextSpan(1, 3), TextSpan(4, 8), "B ", "lpha"
    )
    incomplete = AbbreviationDefinition("doc", short_form_text="AB")
    result = CanonicalValidator().validate(
        (CorpusRecord(document, (complete, overlapping, incomplete)),),
        diagnostics=DiagnosticsSummary(
            (
                # Adapter diagnostics are intentionally included in the same report.
                AdapterDiagnostic(
                    "warning",
                    "REPAIRED",
                    "repair",
                    action="repaired",
                ),
            )
        ),
    )
    assert result.summary.repaired == 1
    assert result.summary.ambiguous == 1
    assert result.summary.unscoreable == 1
    assert result.summary.dropped == 0
    assert result.summary.records_kept == 1


def test_validation_modes_and_inputs_are_explicit() -> None:
    validator = CanonicalValidator(flag_overlaps=False)
    result = validator.validate((cast(Any, object()),), mode="permissive")
    assert result.records == ()
    assert result.summary.dropped == 1
    assert result.summary.records_dropped == 1
    with pytest.raises(CanonicalValidationError) as error:
        validator.validate((cast(Any, object()),), mode="strict")
    assert error.value.summary.records_dropped == 1
    with pytest.raises(ValueError, match="validation mode"):
        validator.validate((), mode=cast(Any, "unknown"))
    with pytest.raises(TypeError, match="issues"):
        ValidationSummary(cast(Any, (object(),)))
    with pytest.raises(ValueError, match="severity"):
        ValidationIssue("bad", "CODE", "message")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="details"):
        ValidationIssue("info", "CODE", "message", details=cast(Any, {"a": "b"}))
    with pytest.raises(ValueError, match="code"):
        ValidationIssue("info", " ", "message")
    with pytest.raises(ValueError, match="message"):
        ValidationIssue("info", "CODE", " ")
    with pytest.raises(ValueError, match="action"):
        ValidationIssue("info", "CODE", "message", action=cast(Any, "bad"))
    with pytest.raises(TypeError, match="location"):
        ValidationIssue("info", "CODE", "message", location=cast(Any, 1))
    from abrex.corpora.validation import validation_issue_from_diagnostic

    assert (
        validation_issue_from_diagnostic(
            AdapterDiagnostic("info", "CODE", "message")
        ).code
        == "CODE"
    )


def test_validation_summary_is_machine_readable_and_manifest_round_trips(
    tmp_path: Path,
) -> None:
    issue = ValidationIssue(
        "warning",
        "REPAIRED",
        "A repair occurred",
        action="repaired",
        details=(("field", "text"),),
    )
    summary = ValidationSummary((issue,), records_seen=1, records_kept=1)
    manifest = build_dataset_manifest(
        (_record(),),
        dataset_id="toy",
        validation=summary,
        config_fingerprint="0" * 64,
    )
    path = tmp_path / "manifest.json"
    path.write_text(manifest.to_json(), encoding="utf-8")
    assert read_dataset_manifest(path) == manifest
    assert json.loads(summary.to_json())["diagnostics"][0]["details"] == {
        "field": "text"
    }
    with pytest.raises(ValueError, match="dataset_id"):
        DatasetManifest("", manifest.fingerprint, 0, 0)
    with pytest.raises(ValueError, match="fingerprint"):
        DatasetManifest("toy", "bad", 0, 0)
    with pytest.raises(ValueError, match="config_fingerprint"):
        DatasetManifest("toy", manifest.fingerprint, 0, 0, config_fingerprint="bad")
    with pytest.raises(ValueError, match="source_fingerprint"):
        DatasetManifest("toy", manifest.fingerprint, 0, 0, source_fingerprint="bad")
    with pytest.raises(ValueError, match="records_kept"):
        ValidationSummary(records_seen=0, records_kept=1)
    with pytest.raises(ValueError, match="non-negative"):
        ValidationSummary(records_seen=True)


def test_artifact_write_load_fingerprint_and_corruption_detection(
    tmp_path: Path,
) -> None:
    result = _fixture_result()
    output = tmp_path / "canonical.jsonl"
    manifest_path = tmp_path / "manifest.json"
    manifest = write_canonical_dataset(
        result,
        output,
        manifest_path=manifest_path,
        config_fingerprint="1" * 64,
    )
    assert manifest.fingerprint == fingerprint_records(result.records)
    records, loaded_manifest = read_canonical_dataset(output, manifest_path)
    assert records == result.records
    assert loaded_manifest == manifest
    assert (
        write_canonical_jsonl(tuple(reversed(result.records)), output)
        == manifest.fingerprint
    )
    output.write_text("not json\n", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="Invalid JSON"):
        read_canonical_jsonl(output)
    output.write_text("\n", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="blank line"):
        read_canonical_jsonl(output)


def test_serialization_rejects_bad_types_and_io_errors(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="CorpusRecord"):
        record_to_dict(cast(Any, object()))
    data = record_to_dict(_record())
    incomplete = CorpusRecord(
        Document("incomplete", "text"),
        (AbbreviationDefinition("incomplete"),),
    )
    assert record_from_dict(record_to_dict(incomplete)) == incomplete

    invalid_values: tuple[tuple[str, object], ...] = (
        ("document", []),
        ("gold_annotations", {}),
        ("record_id", 1),
    )
    for key, value in invalid_values:
        changed = dict(data)
        changed[key] = value
        with pytest.raises(CanonicalSerializationError):
            record_from_dict(changed)
    bad_document = dict(cast(dict[str, object], data["document"]))
    bad_document["document_id"] = 1
    changed = dict(data)
    changed["document"] = bad_document
    with pytest.raises(CanonicalSerializationError, match="string"):
        record_from_dict(changed)

    annotation = cast(list[dict[str, object]], data["gold_annotations"])[0]
    bad_annotation = dict(annotation)
    bad_annotation["short_form"] = []
    changed = dict(data)
    changed["gold_annotations"] = [bad_annotation]
    with pytest.raises(CanonicalSerializationError, match="span"):
        record_from_dict(changed)

    for field, value in (("short_form_text", 1), ("long_form_text", 1)):
        bad = dict(annotation)
        bad[field] = value
        changed = dict(data)
        changed["gold_annotations"] = [bad]
        with pytest.raises(CanonicalSerializationError, match="string"):
            record_from_dict(changed)

    bad_prediction = dict(cast(dict[str, object], annotation["prediction"]))
    bad_prediction["confidence"] = "bad"
    bad = dict(annotation)
    bad["prediction"] = bad_prediction
    changed = dict(data)
    changed["gold_annotations"] = [bad]
    with pytest.raises(CanonicalSerializationError, match="number"):
        record_from_dict(changed)

    bad_provenance = dict(cast(dict[str, object], annotation["provenance"]))
    bad_provenance["transformation_notes"] = "bad"
    bad = dict(annotation)
    bad["provenance"] = bad_provenance
    changed = dict(data)
    changed["gold_annotations"] = [bad]
    with pytest.raises(CanonicalSerializationError, match="transformation_notes"):
        record_from_dict(changed)

    source = dict(bad_provenance)
    source["transformation_notes"] = []
    source["original_short_form"] = {"start": "bad", "end": 2, "text": "AB"}
    bad = dict(annotation)
    bad["provenance"] = source
    changed = dict(data)
    changed["gold_annotations"] = [bad]
    with pytest.raises(CanonicalSerializationError, match="integer"):
        record_from_dict(changed)

    bad = dict(annotation)
    bad["provenance"] = {"source_corpus": 1}
    changed = dict(data)
    changed["gold_annotations"] = [bad]
    with pytest.raises(CanonicalSerializationError, match="string"):
        record_from_dict(changed)

    missing_path = tmp_path / "missing" / "artifact.jsonl"
    with pytest.raises(CanonicalSerializationError, match="Unable to write"):
        write_canonical_jsonl((_record(),), missing_path)
    with pytest.raises(CanonicalSerializationError, match="Unable to read"):
        read_canonical_jsonl(missing_path)
    with pytest.raises(CanonicalSerializationError, match="Unable to fingerprint"):
        from abrex.corpora import fingerprint_file

        fingerprint_file(missing_path)


def test_manifest_validation_and_pair_consistency_errors(tmp_path: Path) -> None:
    result = _fixture_result()
    output = tmp_path / "artifact.jsonl"
    manifest_path = tmp_path / "artifact.manifest.json"
    manifest = write_canonical_dataset(result, output, manifest_path=manifest_path)
    raw = manifest.to_dict()
    with pytest.raises(CanonicalSerializationError, match="normalizers"):
        broken = dict(raw)
        broken["normalizers"] = "bad"
        manifest_path.write_text(json.dumps(broken), encoding="utf-8")
        read_dataset_manifest(manifest_path)
    with pytest.raises(CanonicalSerializationError, match="validation diagnostics"):
        broken = dict(raw)
        broken["validation"] = {"diagnostics": "bad"}
        manifest_path.write_text(json.dumps(broken), encoding="utf-8")
        read_dataset_manifest(manifest_path)
    with pytest.raises(CanonicalSerializationError, match="details"):
        broken = dict(raw)
        broken["validation"] = {
            "records_seen": 0,
            "records_kept": 0,
            "diagnostics": [
                {
                    "severity": "info",
                    "code": "CODE",
                    "message": "message",
                    "action": "observed",
                    "details": [],
                }
            ],
        }
        manifest_path.write_text(json.dumps(broken), encoding="utf-8")
        read_dataset_manifest(manifest_path)

    broken = dict(raw)
    broken["fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="fingerprint does not"):
        read_canonical_dataset(output, manifest_path)
    broken["fingerprint"] = manifest.fingerprint
    broken["record_count"] = 99
    manifest_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="record count"):
        read_canonical_dataset(output, manifest_path)
    broken["record_count"] = manifest.record_count
    broken["annotation_count"] = 99
    manifest_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="annotation count"):
        read_canonical_dataset(output, manifest_path)
    broken["annotation_count"] = manifest.annotation_count
    broken["record_count"] = "bad"
    manifest_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="integer"):
        read_dataset_manifest(manifest_path)

    with pytest.raises(CanonicalSerializationError, match="Unable to write dataset"):
        write_canonical_dataset(
            result, output, manifest_path=tmp_path / "missing" / "m.json"
        )
    with pytest.raises(CanonicalSerializationError, match="Unable to read dataset"):
        read_dataset_manifest(tmp_path / "missing.json")


def test_manifest_rejects_invalid_metadata_and_sources(tmp_path: Path) -> None:
    result = _fixture_result()
    source_path = tmp_path / "source.txt"
    source_path.write_text("source", encoding="utf-8")
    from dataclasses import replace

    from abrex.corpora import SourceResource

    with_source = replace(
        result,
        source=SourceResource.from_path("source", source_path, format="txt"),
    )
    manifest = build_dataset_manifest(
        result.records, dataset_id="toy", build_result=with_source
    )
    assert manifest.source_fingerprint is not None
    assert manifest.source_identifier == "source"
    with pytest.raises(ValueError, match="record_count"):
        DatasetManifest("toy", manifest.fingerprint, -1, 0)
    with pytest.raises(ValueError, match="record_count"):
        DatasetManifest("toy", manifest.fingerprint, True, 0)
    with pytest.raises(ValueError, match="annotation_count"):
        DatasetManifest("toy", manifest.fingerprint, 0, -1)
    with pytest.raises(TypeError, match="normalizer"):
        DatasetManifest(
            "toy", manifest.fingerprint, 0, 0, normalizer_identities=cast(Any, [1])
        )
    with pytest.raises(TypeError, match="validation"):
        DatasetManifest("toy", manifest.fingerprint, 0, 0, validation=cast(Any, None))
    with pytest.raises(ValueError, match="schema version"):
        DatasetManifest("toy", manifest.fingerprint, 0, 0, schema_version="old")
    with pytest.raises(ValueError, match="manifest version"):
        DatasetManifest("toy", manifest.fingerprint, 0, 0, manifest_version="old")


def test_corrupt_version_and_manifest_are_rejected(tmp_path: Path) -> None:
    record = record_to_dict(_record())
    record["schema_version"] = "canonical-v999"
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="version"):
        read_canonical_jsonl(path)
    path.write_text(
        json.dumps({"schema_version": CANONICAL_SCHEMA_VERSION}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CanonicalSerializationError, match="document"):
        read_canonical_jsonl(path)
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="object required"):
        read_canonical_jsonl(path)
    manifest_path = tmp_path / "bad-manifest.json"
    manifest_path.write_text("[]", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="JSON object"):
        read_dataset_manifest(manifest_path)
    manifest_path.write_text("{bad", encoding="utf-8")
    with pytest.raises(CanonicalSerializationError, match="Unable to read"):
        read_dataset_manifest(manifest_path)


def test_cli_corpus_build_is_repeatable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli.jsonl"
    manifest = tmp_path / "cli.manifest.json"
    args = [
        "corpus",
        "build",
        "docs/examples/corpus-fixture.yaml",
        "--output",
        str(output),
        "--manifest",
        str(manifest),
    ]
    assert main(args) == 0
    first_output = output.read_bytes()
    first_fingerprint = json.loads(capsys.readouterr().out)["fingerprint"]
    assert main(args) == 0
    assert output.read_bytes() == first_output
    assert json.loads(capsys.readouterr().out)["fingerprint"] == first_fingerprint
    assert (
        main(["corpus", "build", "docs/examples/base.yaml", "--output", str(output)])
        == 2
    )
    assert "error:" in capsys.readouterr().err
