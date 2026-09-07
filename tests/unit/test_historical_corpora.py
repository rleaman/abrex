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
    SDUAcronymDisambiguationAdapter,
    SDUAcronymExtractionAdapter,
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


def test_sdu_ad_preserves_expansion_without_inventing_a_long_form_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "ad-1",
                    "tokens": ["CNN", "is", "common"],
                    "acronym": 0,
                    "expansion": "Cable News Network",
                }
            ]
        ),
        encoding="utf-8",
    )
    source = SourceResourceConfig(identifier="ad", location=path)
    config = CorpusConfig(adapter=ComponentSpec(type="sdu_aaai21_ad"), source=source)
    annotation = (
        create_corpus_pipeline(config)
        .build(source.to_resource())
        .records[0]
        .gold_annotations[0]
    )
    assert annotation.short_form_text == "CNN"
    assert annotation.long_form is None
    assert annotation.long_form_text == "Cable News Network"
    assert annotation.provenance is not None
    assert annotation.provenance.transformation_notes
    assert SDUAcronymDisambiguationAdapter().identity == "sdu_aaai21_ad"


def test_sdu_aaai22_preserves_independent_half_open_spans_and_source_id(
    tmp_path: Path,
) -> None:
    text = "Alpha (A) and Beta (B)"
    path = tmp_path / "ae.json"
    path.write_text(
        json.dumps(
            [
                {
                    "ID": "source-1",
                    "text": text,
                    "acronyms": [
                        [text.index("A"), text.index("A") + 1],
                        [text.index("B"), text.index("B") + 1],
                    ],
                    "long-forms": [[0, 5]],
                }
            ]
        ),
        encoding="utf-8",
    )
    source = SourceResourceConfig(identifier="ae", location=path)
    config = CorpusConfig(adapter=ComponentSpec(type="sdu_aaai22_ae"), source=source)
    annotation = create_corpus_pipeline(config).build(source.to_resource()).records[0]
    assert annotation.document.document_id == "source-1"
    assert [item.short_form_text for item in annotation.gold_annotations] == [
        "A",
        "B",
        None,
    ]
    assert [item.long_form_text for item in annotation.gold_annotations] == [
        None,
        None,
        "Alpha",
    ]
    assert annotation.gold_annotations[0].short_form is not None
    assert annotation.gold_annotations[0].short_form.end == text.index("A") + 1
    assert annotation.gold_annotations[2].long_form is not None
    assert annotation.gold_annotations[2].long_form.end == 5
    assert all(
        item.provenance is not None
        and item.provenance.transformation_notes
        == ("source acronym and long-form spans preserved independently",)
        for item in annotation.gold_annotations
    )
    assert SDUAcronymExtractionAdapter().identity == "sdu_aaai22_ae"


def test_sdu_aaai22_requires_official_uppercase_id(tmp_path: Path) -> None:
    path = tmp_path / "ae-lowercase-id.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "not-the-official-field",
                    "text": "Alpha (A)",
                    "acronyms": [[7, 8]],
                    "long-forms": [[0, 5]],
                }
            ]
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    records = tuple(
        SDUAcronymExtractionAdapter().parse(
            SourceResourceConfig(identifier="ae", location=path).to_resource(),
            collector,
        )
    )
    assert records == ()
    assert collector.diagnostics[0].code == "SDU_AE_ROW_INVALID"
    assert "non-empty ID" in collector.diagnostics[0].message


def test_sdu_aaai22_drops_invalid_rows_with_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "ae-invalid.json"
    path.write_text(
        json.dumps(
            [
                {
                    "ID": "bad",
                    "text": "Alpha (A)",
                    "acronyms": [[7, 12]],
                    "long-forms": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    records = tuple(
        SDUAcronymExtractionAdapter().parse(
            SourceResourceConfig(identifier="ae", location=path).to_resource(),
            collector,
        )
    )
    assert records == ()
    assert collector.diagnostics[0].record_id == "bad"
    assert collector.diagnostics[0].code == "SDU_AE_ROW_INVALID"


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
                                "locations": [{"offset": 6, "length": 1}],
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
    assert tuple(
        DelimitedPairCorpusAdapter(dataset_variant="corrected").parse(
            source.to_resource(), DiagnosticsCollector()
        )
    )


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


def test_bioc_order_fallback_keeps_unpaired_entities_and_counts_unequal_lists(
    tmp_path: Path,
) -> None:
    text = "Long one (A) and Long two"
    path = tmp_path / "fallback.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "fallback-1",
                        "passages": [
                            {
                                "offset": 0,
                                "text": text,
                                "annotations": [
                                    {
                                        "id": "LF0",
                                        "text": "Long one",
                                        "locations": [{"offset": 0, "length": 8}],
                                        "infons": {"type": "LongForm"},
                                    },
                                    {
                                        "id": "SF0",
                                        "text": "A",
                                        "locations": [{"offset": 10, "length": 1}],
                                        "infons": {"type": "ShortForm"},
                                    },
                                    {
                                        "id": "LF1",
                                        "text": "Long two",
                                        "locations": [
                                            {
                                                "offset": text.index("Long two"),
                                                "length": 8,
                                            }
                                        ],
                                        "infons": {"type": "LongForm"},
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    records = tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="fallback", location=path).to_resource(),
            collector,
        )
    )
    assert len(records[0].annotations) == 2
    assert records[0].annotations[1].long_form is not None
    codes = [item.code for item in collector.diagnostics]
    assert "BIOC_ORDER_FALLBACK_USED" in codes
    assert "BIOC_UNPAIRED_ENTITY" in codes


def test_bioc_dangling_relation_and_duplicate_id_never_select_an_endpoint(
    tmp_path: Path,
) -> None:
    text = "Long (A)"
    path = tmp_path / "dirty.json"

    def annotation(
        identifier: str, value: str, offset: int, role: str
    ) -> dict[str, object]:
        return {
            "id": identifier,
            "text": value,
            "locations": [{"offset": offset, "length": len(value)}],
            "infons": {"type": role},
        }

    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "dirty-1",
                        "passages": [
                            {
                                "offset": 0,
                                "text": text,
                                "annotations": [
                                    annotation("LF", "Long", 0, "LongForm"),
                                    annotation("SF", "A", 6, "ShortForm"),
                                    annotation("SF", "A", 6, "ShortForm"),
                                ],
                                "relations": [
                                    {
                                        "nodes": [
                                            {"role": "long", "refid": "LF"},
                                            {"role": "short", "refid": "missing"},
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    parsed = tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="dirty", location=path).to_resource(),
            collector,
        )
    )
    assert len(parsed[0].annotations) == 3
    assert all(
        annotation.short_form is None or annotation.long_form is None
        for annotation in parsed[0].annotations
    )
    codes = [item.code for item in collector.diagnostics]
    assert "BIOC_DUPLICATE_ANNOTATION_ID" in codes
    assert "BIOC_RELATION_ENDPOINT_UNRESOLVED" in codes


def test_bioc_json_preserves_source_text_and_matches_equivalent_xml(
    tmp_path: Path,
) -> None:
    text = "Long (S)"
    json_path = tmp_path / "source.json"
    json_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "equivalent",
                        "passages": [
                            {
                                "offset": 0,
                                "text": text,
                                "annotations": [
                                    {
                                        "id": "long",
                                        "text": "WRONG",
                                        "locations": [{"offset": 0, "length": 4}],
                                        "infons": {"type": "LongForm"},
                                    },
                                    {
                                        "id": "short",
                                        "text": "S",
                                        "locations": [{"offset": 6, "length": 1}],
                                        "infons": {"type": "ShortForm"},
                                    },
                                ],
                                "relations": [
                                    {
                                        "nodes": [
                                            {"role": "long", "refid": "long"},
                                            {"role": "short", "refid": "short"},
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    xml_path = tmp_path / "source.xml"
    xml_path.write_text(
        """<collection><document><id>equivalent</id><passage>
        <offset>0</offset><text>Long (S)</text>
        <annotation id="long"><infon key="type">LongForm</infon>
        <location offset="0" length="4"/><text>WRONG</text></annotation>
        <annotation id="short"><infon key="type">ShortForm</infon>
        <location offset="6" length="1"/><text>S</text></annotation>
        <relation><node role="long" refid="long"/>
        <node role="short" refid="short"/></relation>
        </passage></document></collection>""",
        encoding="utf-8",
    )
    json_result = tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="json", location=json_path).to_resource(),
            DiagnosticsCollector(),
        )
    )
    xml_result = tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="xml", location=xml_path).to_resource(),
            DiagnosticsCollector(),
        )
    )
    assert json_result[0].text == text
    assert json_result[0].text == xml_result[0].text
    assert json_result[0].annotations == xml_result[0].annotations


def test_bioc_multiple_locations_are_explicitly_diagnosed(tmp_path: Path) -> None:
    path = tmp_path / "multi.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "multi",
                        "passages": [
                            {
                                "offset": 0,
                                "text": "Long A",
                                "annotations": [
                                    {
                                        "id": "long",
                                        "text": "Long",
                                        "locations": [
                                            {"offset": 0, "length": 4},
                                            {"offset": 5, "length": 1},
                                        ],
                                        "infons": {"type": "LongForm"},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="multi", location=path).to_resource(),
            collector,
        )
    )
    assert any(item.code == "BIOC_MULTIPLE_LOCATIONS" for item in collector.diagnostics)


def test_bioc_named_text_and_location_policies_cover_repairs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pairing_policy"):
        BioCCorpusAdapter(pairing_policy="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="text_policy"):
        BioCCorpusAdapter(text_policy="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="location_policy"):
        BioCCorpusAdapter(location_policy="bad")  # type: ignore[arg-type]

    path = tmp_path / "policies.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "policies",
                        "passages": [
                            {
                                "offset": 0,
                                "text": "Long (A)",
                                "annotations": [
                                    {
                                        "id": "SF0",
                                        "text": "Z",
                                        "locations": [{"offset": 6, "length": 1}],
                                        "infons": {"type": "ABBR"},
                                    },
                                    {
                                        "id": "LF0",
                                        "text": "Long (A)",
                                        "locations": [
                                            {"offset": 0, "length": 4},
                                            {"offset": 5, "length": 3},
                                        ],
                                        "infons": {"type": "ABBR"},
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    collector = DiagnosticsCollector()
    parsed = tuple(
        BioCCorpusAdapter(
            text_policy="overlay_annotation_text",
            location_policy="reject_discontinuous",
        ).parse(
            SourceResourceConfig(identifier="policies", location=path).to_resource(),
            collector,
        )
    )
    assert parsed[0].text == "Long (Z)"
    assert parsed[0].transformation_notes
    assert parsed[0].annotations[0].short_form is not None
    assert any(item.code == "BIOC_MULTIPLE_LOCATIONS" for item in collector.diagnostics)

    empty_path = tmp_path / "empty.json"
    empty_path.write_text(
        json.dumps({"documents": [{"id": "empty", "passages": []}]}), encoding="utf-8"
    )
    empty = tuple(
        BioCCorpusAdapter().parse(
            SourceResourceConfig(identifier="empty", location=empty_path).to_resource(),
            DiagnosticsCollector(),
        )
    )
    assert empty[0].text == ""

    negative_path = tmp_path / "negative.json"
    negative_path.write_text(
        json.dumps({"documents": [{"passages": [{"offset": -1, "text": "bad"}]}]}),
        encoding="utf-8",
    )
    with pytest.raises(CorpusAdapterError, match="non-negative"):
        BioCCorpusAdapter().parse(
            SourceResourceConfig(
                identifier="negative", location=negative_path
            ).to_resource(),
            DiagnosticsCollector(),
        )
