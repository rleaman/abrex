"""Structural fixtures for historical corpus adapters (no licensed data)."""

from __future__ import annotations

from pathlib import Path

from abrex.config import ComponentSpec
from abrex.corpora import (
    BioCCorpusAdapter,
    CorpusConfig,
    DelimitedPairCorpusAdapter,
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
