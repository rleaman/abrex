"""Offline tests for the provenance-preserving frequency resource."""

from __future__ import annotations

import gzip
import io
import json
from pathlib import Path

import pytest

from abrex.resources.frequency import (
    FrequencyResourceConfig,
    FrequencyResourceError,
    _iter_frequency_entries,
    import_frequency_resource,
    load_frequency_config,
)


def _source(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "resource.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream)
    return path


def test_streaming_import_preserves_raw_variants_and_unknown_document_frequency(
    tmp_path: Path,
) -> None:
    source = _source(
        tmp_path,
        {
            "TNF": {"tumor necrosis factor": 2, "Tumor Necrosis Factor": 1},
            "IL-6": {"interleukin 6": 3},
        },
    )
    config = FrequencyResourceConfig(
        source_path=source,
        sqlite_path=tmp_path / "resource.sqlite",
        normalization="casefold",
        count_unit="extraction-count-unknown-unit",
    )
    resource = import_frequency_resource(config)
    variants = resource.lookup("tnf")
    assert [item.long_form_raw for item in variants] == [
        "tumor necrosis factor",
        "Tumor Necrosis Factor",
    ]
    assert all(item.short_form_key == "tnf" for item in variants)
    assert resource.document_frequency("tnf") is None
    assert resource.summary().variant_count == 3
    assert resource.summary().short_form_key_count == 2
    assert resource.summary().total_count == 6
    assert resource.summary().count_unit == "extraction-count-unknown-unit"
    assert len(resource.summary().source_sha256) == 64


def test_max_entries_and_repeat_import_are_reproducible(tmp_path: Path) -> None:
    source = _source(tmp_path, {"A": {"alpha": 1}, "B": {"beta": 2}})
    config = FrequencyResourceConfig(
        source_path=source,
        sqlite_path=tmp_path / "resource.sqlite",
        max_entries=1,
    )
    first = import_frequency_resource(config).summary()
    second = import_frequency_resource(config).summary()
    assert first == second
    assert first.variant_count == 1


def test_stream_parser_handles_small_chunks_and_rejects_bad_counts() -> None:
    assert tuple(_iter_frequency_entries(io.StringIO("{}"), 2)) == ()
    entries = tuple(_iter_frequency_entries(io.StringIO('{"A":{"B":1}}'), 2))
    assert entries == (("A", "B", 1),)
    with pytest.raises(ValueError, match="non-negative"):
        tuple(_iter_frequency_entries(io.StringIO('{"A":{"B":-1}}'), 2))
    with pytest.raises(ValueError, match="short-form"):
        tuple(_iter_frequency_entries(io.StringIO('{1:{"B":1}}'), 2))


def test_resource_config_loader_and_failures(tmp_path: Path) -> None:
    source = _source(tmp_path, {"A": {"B": 1}})
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "frequency_resource:\n"
        f"  source_path: {source}\n"
        f"  sqlite_path: {tmp_path / 'resource.sqlite'}\n"
        "  max_entries: 1\n",
        encoding="utf-8",
    )
    assert load_frequency_config(config_path).max_entries == 1
    missing_section = tmp_path / "missing-section.yaml"
    missing_section.write_text("other: {}\n", encoding="utf-8")
    with pytest.raises(FrequencyResourceError, match="lacks"):
        load_frequency_config(missing_section)
    with pytest.raises(FrequencyResourceError, match="does not exist"):
        import_frequency_resource(
            FrequencyResourceConfig(
                source_path=tmp_path / "none.gz", sqlite_path=tmp_path / "x.sqlite"
            )
        )


def test_resource_config_rejects_unknown_adapter_and_normalization(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="unsupported resource adapter"):
        FrequencyResourceConfig(
            source_path=tmp_path / "x", sqlite_path=tmp_path / "y", adapter="other"
        )
    with pytest.raises(ValueError, match="normalization"):
        FrequencyResourceConfig(
            source_path=tmp_path / "x",
            sqlite_path=tmp_path / "y",
            normalization="strip",
        )
    with pytest.raises(ValueError, match="non-empty"):
        FrequencyResourceConfig(
            source_path=tmp_path / "x", sqlite_path=tmp_path / "y", count_unit=""
        )
