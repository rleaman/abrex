"""Structural fixtures for historical corpus adapters (no licensed data)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.config import ComponentSpec
from abrex.corpora import (
    BioCCorpusAdapter,
    CorpusAdapterError,
    CorpusConfig,
    DelimitedPairCorpusAdapter,
    DiagnosticsCollector,
    SDUAcronymIdentificationAdapter,
    SourceResourceConfig,
    create_corpus_pipeline,
)


def test_bioc_xml_relations_preserve_offsets_and_variant() -> None:
    path = Path("tests/fixtures/historical_bioc.xml")
    config = CorpusConfig(
        adapter=ComponentSpec(type="schwartz_hearst"),
        source=SourceResourceConfig(identifier="sh", location=path),
    )
    result = create_corpus_pipeline(config).build(config.source.to_resource())
    annotation = result.records[0].gold_annotations[0]
    assert annotation.short_form is not None and annotation.short_form.start == 23
    assert annotation.provenance is not None
    assert annotation.provenance.original_short_form is not None
    assert annotation.provenance.original_short_form.start == 23
    assert annotation.long_form is not None and annotation.long_form.end == 21
    assert annotation.provenance.source_corpus == "schwartz_hearst"


def test_sdu_bio_labels_reconstruct_auditable_spans() -> None:
    path = Path("tests/fixtures/historical_sdu.json")
    config = CorpusConfig(
        adapter=ComponentSpec(type="sdu_aaai21_ai"),
        source=SourceResourceConfig(identifier="sdu", location=path),
    )
    result = create_corpus_pipeline(config).build(config.source.to_resource())
    annotation = result.records[0].gold_annotations[0]
    assert annotation.long_form_text == "Tumor necrosis factor"
    assert annotation.short_form_text == "TNF"
    assert annotation.provenance is not None
    assert (
        SDUAcronymIdentificationAdapter(dataset_variant="sdu_aaai21_ai").identity
        == "sdu_aaai21_ai"
    )


def test_pair_correction_requires_explicit_reconstruction_template() -> None:
    path = Path("tests/fixtures/historical_pairs.txt")
    config = CorpusConfig(
        adapter=ComponentSpec(
            type="medstract_badrex", params={"document_template": "{long} ({short})"}
        ),
        source=SourceResourceConfig(identifier="corrected", location=path),
    )
    result = create_corpus_pipeline(config).build(config.source.to_resource())
    assert len(result.records) == 1
    assert result.records[0].gold_annotations[0].provenance is not None
    assert (
        result.records[0].gold_annotations[0].provenance.adapter_identity
        == "medstract_badrex"
    )
    assert BioCCorpusAdapter(dataset_variant="bioadi").identity == "bioadi"
    assert (
        DelimitedPairCorpusAdapter(dataset_variant="medstract_badrex").identity
        == "medstract_badrex"
    )


def test_historical_adapters_reject_invalid_configuration_and_sources(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="dataset_variant"):
        BioCCorpusAdapter(dataset_variant=" ")
    with pytest.raises(ValueError, match="dataset_variant"):
        SDUAcronymIdentificationAdapter(dataset_variant=" ")
    with pytest.raises(ValueError, match="token_separator"):
        SDUAcronymIdentificationAdapter(token_separator="")
    with pytest.raises(ValueError, match="dataset_variant"):
        DelimitedPairCorpusAdapter(dataset_variant=" ")

    missing = SourceResourceConfig(
        identifier="missing", location=tmp_path / "missing.xml"
    ).to_resource()
    with pytest.raises(CorpusAdapterError, match="does not exist"):
        BioCCorpusAdapter().parse(missing, DiagnosticsCollector())
    embedded = SourceResourceConfig(identifier="embedded").to_resource()
    with pytest.raises(CorpusAdapterError, match="source.location"):
        BioCCorpusAdapter().parse(embedded, DiagnosticsCollector())


def test_bioc_json_parser_supports_variants_and_reports_bad_structures(
    tmp_path: Path,
) -> None:
    content = {
        "documents": [
            {
                "id": "",
                "passages": [
                    {
                        "offset": 0,
                        "text": "Long (S)",
                        "annotations": [
                            {
                                "id": "long",
                                "locations": [{"offset": 0, "length": 4}],
                                "text": "Long",
                                "infons": {"type": "Long Form"},
                            },
                            {
                                "id": "short",
                                "locations": [{"offset": 7, "length": 1}],
                                "text": "S",
                                "infons": {"type": "short_form"},
                            },
                            "not-an-object",
                            {"id": "bad-location", "locations": ["bad"]},
                            {"id": "empty-location", "locations": []},
                            {
                                "id": "no-text",
                                "locations": [{"offset": 0, "length": 0}],
                                "infons": [],
                            },
                        ],
                        "relations": [
                            {
                                "nodes": [
                                    {"role": "short", "refid": "short"},
                                    {"role": "long", "refid": "long"},
                                ]
                            },
                            {"nodes": []},
                            "not-an-object",
                        ],
                    }
                ],
            }
        ]
    }
    path = tmp_path / "bioc.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    source = SourceResourceConfig(identifier="json", location=path, format="json")
    result = create_corpus_pipeline(
        CorpusConfig(adapter=ComponentSpec(type="bioadi"), source=source)
    ).build(source.to_resource())
    assert result.records[0].document.document_id == "bioadi-0"
    assert result.records[0].gold_annotations[0].short_form_text == "S"

    list_path = tmp_path / "bioc-list.json"
    list_path.write_text("[]", encoding="utf-8")
    list_source = SourceResourceConfig(
        identifier="list", location=list_path, format="json"
    )
    assert (
        tuple(
            BioCCorpusAdapter().parse(list_source.to_resource(), DiagnosticsCollector())
        )
        == ()
    )
    bad_values: tuple[tuple[dict[str, object], str], ...] = (
        ({"documents": {}}, "documents array"),
        ({"documents": ["bad"]}, "document 0"),
        ({"documents": [{"passages": {}}]}, "passages.*array"),
    )
    for index, (value, message) in enumerate(bad_values):
        bad_path = tmp_path / f"bad-{index}.json"
        bad_path.write_text(json.dumps(value), encoding="utf-8")
        bad_source = SourceResourceConfig(
            identifier="bad", location=bad_path, format="json"
        )
        with pytest.raises(CorpusAdapterError, match=message):
            BioCCorpusAdapter().parse(bad_source.to_resource(), DiagnosticsCollector())

    bad_passage = tmp_path / "bad-passage.json"
    bad_passage.write_text(
        json.dumps({"documents": [{"passages": ["bad"]}]}), encoding="utf-8"
    )
    bad_source = SourceResourceConfig(
        identifier="bad", location=bad_passage, format="json"
    )
    with pytest.raises(CorpusAdapterError, match="passage"):
        BioCCorpusAdapter().parse(bad_source.to_resource(), DiagnosticsCollector())


def test_historical_xml_pair_and_sdu_malformed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml_path = tmp_path / "minimal.xml"
    xml_path.write_text(
        """<collection><document><id>x</id><passage><text>Long S</text>
        <annotation id="missing"><infon key="type">long</infon></annotation>
        <annotation id="long"><location offset="0" length="4"/>
        <infon key="type">long</infon><text>Long</text></annotation>
        <annotation id="short"><location offset="5" length="1"/>
        <infon key="type">short</infon><text>S</text></annotation>
        </passage></document></collection>""",
        encoding="utf-8",
    )
    source = SourceResourceConfig(identifier="xml", location=xml_path)
    result = create_corpus_pipeline(
        CorpusConfig(adapter=ComponentSpec(type="schwartz_hearst"), source=source)
    ).build(source.to_resource())
    assert result.records[0].gold_annotations[0].short_form_text == "S"

    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<collection>", encoding="utf-8")
    bad_source = SourceResourceConfig(identifier="bad", location=bad_xml)
    with pytest.raises(CorpusAdapterError, match="Unable to parse BioC"):
        BioCCorpusAdapter().parse(bad_source.to_resource(), DiagnosticsCollector())

    no_io = tmp_path / "no-io.txt"
    no_io.write_text("content", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_io(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        if self == no_io:
            raise OSError("unreadable")
        return original_read_text(
            self, encoding=encoding, errors=errors, newline=newline
        )

    monkeypatch.setattr(Path, "read_text", raise_io)
    with pytest.raises(CorpusAdapterError, match="Unable to parse pair"):
        DelimitedPairCorpusAdapter(dataset_variant="corrected").parse(
            SourceResourceConfig(identifier="pairs", location=no_io).to_resource(),
            DiagnosticsCollector(),
        )

    pairs = tmp_path / "pairs.txt"
    pairs.write_text(
        "# comment\n\nid\tLong (S)\t6\t7\t0\t4\ninvalid\trow\ttoo\tfew\n",
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    pair_source = SourceResourceConfig(identifier="pairs", location=pairs)
    records = tuple(
        DelimitedPairCorpusAdapter(dataset_variant="corrected").parse(
            pair_source.to_resource(), collector
        )
    )
    assert len(records) == 1
    assert collector.diagnostics[0].code == "PAIR_ROW_INVALID"

    for index, value in enumerate(("not-json", "{}")):
        path = tmp_path / f"bad-sdu-{index}.json"
        path.write_text(value, encoding="utf-8")
        source = SourceResourceConfig(identifier="sdu", location=path)
        with pytest.raises(CorpusAdapterError):
            SDUAcronymIdentificationAdapter().parse(
                source.to_resource(), DiagnosticsCollector()
            )

    invalid_sdu = tmp_path / "invalid-sdu.json"
    invalid_sdu.write_text(json.dumps(["bad"]), encoding="utf-8")
    collector = DiagnosticsCollector()
    source = SourceResourceConfig(identifier="sdu", location=invalid_sdu)
    assert (
        tuple(SDUAcronymIdentificationAdapter().parse(source.to_resource(), collector))
        == ()
    )
    assert collector.diagnostics[0].code == "SDU_ROW_INVALID"

    invalid_row = tmp_path / "invalid-row.json"
    invalid_row.write_text(
        json.dumps([{"tokens": ["one"], "labels": []}]), encoding="utf-8"
    )
    source = SourceResourceConfig(identifier="invalid", location=invalid_row)
    with pytest.raises(CorpusAdapterError, match="equal-length"):
        SDUAcronymIdentificationAdapter().parse(
            source.to_resource(), DiagnosticsCollector()
        )

    final_span = tmp_path / "final-span.json"
    final_span.write_text(
        json.dumps([{"tokens": ["Long", "S"], "labels": ["B-long", "B-short"]}]),
        encoding="utf-8",
    )
    source = SourceResourceConfig(identifier="final", location=final_span)
    parsed = tuple(
        SDUAcronymIdentificationAdapter().parse(
            source.to_resource(), DiagnosticsCollector()
        )
    )
    assert parsed[0].annotations[0].short_form is not None

    six_fields = tmp_path / "six-fields.txt"
    six_fields.write_text("id\tLong (S)\t6\t7\t0\t4\n", encoding="utf-8")
    source = SourceResourceConfig(identifier="six", location=six_fields)
    config = CorpusConfig(adapter=ComponentSpec(type="medstract_badrex"), source=source)
    assert create_corpus_pipeline(config).build(source.to_resource()).records


def test_pair_adapter_reports_two_column_rows_without_reconstruction_template(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pairs.txt"
    path.write_text("short\tlong\n", encoding="utf-8")
    collector = DiagnosticsCollector()
    source = SourceResourceConfig(identifier="pairs", location=path)
    assert (
        tuple(
            DelimitedPairCorpusAdapter(dataset_variant="corrected").parse(
                source.to_resource(), collector
            )
        )
        == ()
    )
    assert collector.diagnostics[0].code == "PAIR_ROW_INVALID"
