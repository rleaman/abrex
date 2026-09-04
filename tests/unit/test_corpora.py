"""Unit and contract tests for the corpus adapter framework."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abrex.config import ComponentSpec, ResolvedConfig
from abrex.corpora import (
    AdapterDiagnostic,
    CorpusAdapterError,
    CorpusBuildError,
    CorpusConfig,
    CorpusPipeline,
    DiagnosticsCollector,
    DiagnosticsSummary,
    FixtureCorpusAdapter,
    NormalizationPipeline,
    NormalizationStep,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    SourceResourceConfig,
    TrimCapturedText,
    corpus_config_from_resolved,
    create_corpus_pipeline,
    map_source_record,
)
from abrex.corpora.registry import CORPUS_ADAPTERS, NORMALIZERS
from abrex.domain import (
    AbbreviationDefinition,
    CorpusRecord,
    Document,
    SourceTextSpan,
    TextSpan,
)
from abrex.registry import Registry


def test_fixture_adapter_pipeline_repairs_drops_and_sorts() -> None:
    config = CorpusConfig(
        adapter=ComponentSpec(type="fixture"),
        source=SourceResourceConfig(identifier="embedded-fixture"),
        normalizers=(ComponentSpec(type="trim_captured_text"),),
    )

    result = create_corpus_pipeline(config).build(config.source.to_resource())

    assert tuple(record.id for record in result.records) == ("clean-1", "repairable-1")
    assert result.adapter_identity == "fixture"
    assert result.normalizer_identities == ("trim_captured_text",)
    assert result.diagnostics.to_dict()["by_action"] == {
        "observed": 1,
        "repaired": 1,
        "dropped": 1,
    }
    repair = result.records[1].gold_annotations[0]
    assert repair.short_form_text == "MRI"
    assert repair.provenance is not None
    assert "trimmed short_form_text" in repair.provenance.transformation_notes[0]
    assert json.loads(result.diagnostics_json())["total"] == 3


def test_fixture_rejects_filesystem_resources_and_strict_build_exposes_summary() -> (
    None
):
    resource = SourceResource.from_path("fixture-file", Path("fixture.json"))
    with pytest.raises(ValueError, match="does not read filesystem"):
        CorpusPipeline(FixtureCorpusAdapter()).build(resource)

    config = CorpusConfig(
        adapter=ComponentSpec(type="fixture"),
        normalizers=(ComponentSpec(type="identity"),),
        strict=True,
    )
    pipeline = create_corpus_pipeline(config)
    with pytest.raises(CorpusBuildError, match="had errors") as error:
        pipeline.build(config.source.to_resource())
    summary = error.value.diagnostics.to_dict()
    assert cast(dict[str, int], summary["by_action"])["dropped"] == 2


def test_yaml_resolved_corpus_section_is_typed_at_composition_boundary() -> None:
    resolved = ResolvedConfig.model_validate(
        {
            "corpus": {
                "adapter": {"type": "fixture", "params": {}},
                "source": {"identifier": "yaml-fixture"},
                "normalizers": [{"type": "trim_captured_text", "params": {}}],
            }
        }
    )
    config = corpus_config_from_resolved(resolved)
    assert config.source.identifier == "yaml-fixture"
    assert (
        len(create_corpus_pipeline(config).build(config.source.to_resource()).records)
        == 2
    )
    with pytest.raises(ValueError, match="does not contain"):
        corpus_config_from_resolved(ResolvedConfig())


def test_checked_in_yaml_example_composes_and_runs() -> None:
    from abrex.config import load_resolved_config

    config = corpus_config_from_resolved(
        load_resolved_config((Path("docs/examples/corpus-fixture.yaml"),))
    )
    assert (
        len(create_corpus_pipeline(config).build(config.source.to_resource()).records)
        == 2
    )


def test_source_and_parsed_value_objects_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="identifier"):
        SourceResource("")
    with pytest.raises(TypeError, match="pathlib"):
        SourceResource("source", location="source.txt")  # type: ignore[arg-type]
    assert SourceResource("source", metadata={"key": "value"}).metadata == (
        ("key", "value"),
    )
    with pytest.raises(TypeError, match="metadata"):
        SourceResource("source", metadata=("bad",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="metadata"):
        SourceResource("source", metadata=(("key", 1),))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="format"):
        SourceResource("source", format=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="record_id"):
        ParsedSourceRecord("", "doc", "text")
    with pytest.raises(ValueError, match="document_id"):
        ParsedSourceRecord("record", "", "text")
    with pytest.raises(TypeError, match="text"):
        ParsedSourceRecord("record", "doc", 1)  # type: ignore[arg-type]
    assert ParsedSourceRecord("record", "doc", "text", ()).annotations == ()
    assert ParsedSourceRecord("record", "doc", "text", []).annotations == ()
    with pytest.raises(TypeError, match="annotations"):
        ParsedSourceRecord("record", "doc", "text", "bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="annotations"):
        ParsedSourceRecord("record", "doc", "text", object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="source_corpus"):
        ParsedSourceRecord("record", "doc", "text", source_corpus=1)  # type: ignore[arg-type]

    valid = ParsedSourceAnnotation()
    assert valid.short_form is None
    with pytest.raises(TypeError, match="annotations"):
        ParsedSourceRecord("record", "doc", "text", (object(),))  # type: ignore[arg-type]


def test_source_mapping_preserves_incomplete_annotations_and_provenance() -> None:
    source = ParsedSourceRecord(
        "record-1",
        "doc-1",
        "ABC means alpha",
        (ParsedSourceAnnotation("ann-1", SourceTextSpan(text="ABC"), None),),
        "toy",
    )
    record = map_source_record(source, adapter_identity="toy", adapter_version="2")
    annotation = record.gold_annotations[0]
    assert annotation.short_form is None
    assert annotation.short_form_text == "ABC"
    assert annotation.provenance is not None
    assert annotation.provenance.original_short_form == source.annotations[0].short_form
    record.validate()


def test_trim_normalizer_handles_noop_mismatch_and_missing_provenance() -> None:
    document = Document("doc", "ABC alpha")
    annotation = AbbreviationDefinition(
        "doc",
        short_form=TextSpan(0, 3),
        long_form=TextSpan(4, 9),
        short_form_text="ABC",
        long_form_text=" alpha ",
    )
    collector = DiagnosticsCollector()
    result = TrimCapturedText().normalize(
        CorpusRecord(document, (annotation,)), collector
    )
    assert result.gold_annotations[0].long_form_text == "alpha"
    assert result.gold_annotations[0].provenance is not None
    assert (
        cast(dict[str, int], collector.summary().to_dict()["by_action"])["repaired"]
        == 1
    )

    mismatch = AbbreviationDefinition(
        "doc", short_form_text=" ABC ", long_form_text="not the text"
    )
    collector = DiagnosticsCollector()
    unchanged = TrimCapturedText().normalize(
        CorpusRecord(document, (mismatch,)), collector
    )
    assert unchanged.gold_annotations[0] == mismatch
    assert collector.summary().total == 0


def test_diagnostics_are_immutable_and_machine_readable() -> None:
    diagnostic = AdapterDiagnostic(
        "warning",
        "REPAIRED",
        "A repair occurred",
        action="repaired",
        details=(("field", "text"),),
    )
    summary = DiagnosticsSummary((diagnostic,))
    assert summary.to_dict()["by_severity"] == {"info": 0, "warning": 1, "error": 0}
    assert json.loads(summary.to_json())["diagnostics"][0]["details"] == {
        "field": "text"
    }
    collector = DiagnosticsCollector()
    collector.extend((diagnostic,))
    assert collector.summary() == summary
    with pytest.raises(ValueError, match="severity"):
        AdapterDiagnostic("bad", "CODE", "message")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="code"):
        AdapterDiagnostic("info", " ", "message")
    with pytest.raises(ValueError, match="message"):
        AdapterDiagnostic("info", "CODE", " ")
    with pytest.raises(ValueError, match="action"):
        AdapterDiagnostic("info", "CODE", "message", action="bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="record_id"):
        AdapterDiagnostic("info", "CODE", "message", record_id=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="details"):
        AdapterDiagnostic("info", "CODE", "message", details=("bad",))  # type: ignore[arg-type]


class MemoryAdapter:
    identity = "memory"
    version = "1"

    def __init__(self, *, reverse: bool = False) -> None:
        self.reverse = reverse

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> tuple[ParsedSourceRecord, ...]:
        records = (
            ParsedSourceRecord("b", "doc-b", "B"),
            ParsedSourceRecord("a", "doc-a", "A"),
        )
        return tuple(reversed(records)) if self.reverse else records

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        return map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )


class DuplicateAdapter(MemoryAdapter):
    identity = "duplicate"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> tuple[ParsedSourceRecord, ...]:
        record = ParsedSourceRecord("same", "doc", "text")
        return (record, record)


class FailingParseAdapter(MemoryAdapter):
    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> tuple[ParsedSourceRecord, ...]:
        raise OSError("broken source")


class PropagatingParseAdapter(MemoryAdapter):
    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> tuple[ParsedSourceRecord, ...]:
        raise CorpusAdapterError("adapter failure")


class BadMapAdapter(MemoryAdapter):
    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        raise ValueError("bad source row")


class InvalidYieldAdapter:
    identity = "invalid-yield"
    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> tuple[ParsedSourceRecord, ...]:
        return cast(tuple[ParsedSourceRecord, ...], (object(),))

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        return map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )


def test_adapter_contract_is_deterministic_and_duplicate_policy_is_observable() -> None:
    resource = SourceResource("memory")
    first = CorpusPipeline(MemoryAdapter()).build(resource)
    second = CorpusPipeline(MemoryAdapter(reverse=True)).build(resource)
    assert tuple(item.id for item in first.records) == ("a", "b")
    assert first.records == second.records

    duplicate = CorpusPipeline(DuplicateAdapter()).build(resource)
    assert len(duplicate.records) == 2
    assert (
        cast(dict[str, int], duplicate.diagnostics.to_dict()["by_severity"])["warning"]
        == 1
    )


def test_normalization_pipeline_preserves_declared_order() -> None:
    first = IdentityStep()
    second = IdentityStep()
    pipeline = NormalizationPipeline((first, second))
    collector = DiagnosticsCollector()
    record = CorpusRecord(Document("doc", "text"))
    assert pipeline.apply(record, collector) == record
    assert pipeline.identities == ("identity", "identity")


def test_pipeline_diagnoses_mapping_failures_and_wraps_source_failures() -> None:
    resource = SourceResource("memory")
    mapped = CorpusPipeline(BadMapAdapter()).build(resource)
    assert mapped.records == ()
    assert (
        cast(dict[str, int], mapped.diagnostics.to_dict()["by_action"])["dropped"] == 2
    )
    with pytest.raises(CorpusAdapterError, match="broken source"):
        CorpusPipeline(FailingParseAdapter()).build(resource)
    with pytest.raises(CorpusAdapterError, match="adapter failure"):
        CorpusPipeline(PropagatingParseAdapter()).build(resource)
    with pytest.raises(TypeError, match="ParsedSourceRecord"):
        CorpusPipeline(InvalidYieldAdapter()).build(resource)


def test_local_registries_can_compose_typed_plugins() -> None:
    adapters = Registry[object]("local-adapters")
    normalizers = Registry[object]("local-normalizers")
    adapters.register("memory", MemoryAdapter)
    normalizers.register("identity", lambda: IdentityStep())
    config = CorpusConfig(
        adapter=ComponentSpec(type="memory", params={"reverse": True}),
        normalizers=(ComponentSpec(type="identity"),),
    )
    pipeline = create_corpus_pipeline(
        config,
        adapter_registry=adapters,  # type: ignore[arg-type]
        normalizer_registry=normalizers,  # type: ignore[arg-type]
    )
    assert tuple(
        record.id for record in pipeline.build(SourceResource("local")).records
    ) == (
        "a",
        "b",
    )
    assert "fixture" in CORPUS_ADAPTERS
    assert "trim_captured_text" in NORMALIZERS


class IdentityStep:
    identity = "identity"
    version = "1"

    def normalize(
        self, record: CorpusRecord, diagnostics: DiagnosticsCollector
    ) -> CorpusRecord:
        return record


def test_protocol_alias_is_importable() -> None:
    assert isinstance(TrimCapturedText(), NormalizationStep)
