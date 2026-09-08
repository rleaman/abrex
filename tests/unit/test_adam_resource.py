"""Tests for the documented ADAM tabular format and T028 import path."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from typing import cast

import pytest

from abrex.resources import (
    AdamAcquisitionError,
    AdamImportConfig,
    import_adam,
    load_adam_config,
    parse_adam_line,
)

_ROW = "$ABC\t$ABC:4|$Abc:1\tAlpha beta:5:0.8|A. beta:2:0.4\t0.8\t5\n"


def _config(tmp_path: Path, **overrides: object) -> AdamImportConfig:
    values: dict[str, object] = {
        "tar_path": tmp_path / "adam.tar",
        "readme_path": tmp_path / "README",
        "manifest_path": tmp_path / "manifest.json",
        "normalized_path": tmp_path / "adam.json.gz",
        "sqlite_path": tmp_path / "adam.sqlite",
        "max_records": 1,
    }
    values.update(overrides)
    return AdamImportConfig.model_validate(values)


def _write_tar(path: Path, content: bytes) -> None:
    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo("adam_database")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))


def test_parse_adam_line_preserves_grouped_variants() -> None:
    record = parse_adam_line(_ROW)
    assert record.preferred_abbreviation == "$ABC"
    assert record.abbreviation_variants == ("$ABC", "$Abc")
    assert [variant.long_form for variant in record.long_form_variants] == [
        "Alpha beta",
        "A. beta",
    ]
    assert record.long_form_variants[0].count == 5
    assert record.phrase_score == 0.8
    assert record.definition_count == 5


def test_import_adam_reconciles_full_stream_and_queries_t028(tmp_path: Path) -> None:
    archive = tmp_path / "adam.tar"
    _write_tar(
        archive,
        ("# header\n" + _ROW + "bad\n" + _ROW.replace("$ABC", "$DEF", 1)).encode(),
    )
    readme = tmp_path / "README"
    readme.write_text("non-commercial terms\n", encoding="utf-8")
    result = import_adam(_config(tmp_path))
    assert result.parsed_records == 2
    assert result.imported_records == 1
    assert result.malformed_records == 1
    assert {
        variant.long_form_raw: variant.count
        for variant in result.resource.lookup("$ABC")
    } == {"Alpha beta": 5, "A. beta": 2}
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["variant_semantics"].startswith("ADAM")
    assert manifest["readme_sha256"] == result.readme_sha256


@pytest.mark.parametrize(
    "line, message",
    [
        ("bad", "five"),
        ("\tA:1\tB:1:0.5\t0.5\t1", "preferred"),
        ("A\tA:1\tB:not-count:0.5\t0.5\t1", "numeric"),
        ("A\tA:1\tB:1:0.5\t0.5\t-1", "non-negative"),
    ],
)
def test_parse_adam_line_rejects_malformed_rows(line: str, message: str) -> None:
    with pytest.raises(AdamAcquisitionError, match=message):
        parse_adam_line(line)


def test_import_adam_rejects_missing_or_empty_archive(tmp_path: Path) -> None:
    with pytest.raises(AdamAcquisitionError, match="does not exist"):
        import_adam(_config(tmp_path))
    archive = tmp_path / "adam.tar"
    _write_tar(archive, b"# only comments\n")
    with pytest.raises(AdamAcquisitionError, match="no valid"):
        import_adam(_config(tmp_path))


def test_adam_summary_and_archive_member_errors(tmp_path: Path) -> None:
    archive = tmp_path / "adam.tar"
    with tarfile.open(archive, "w") as handle:
        info = tarfile.TarInfo("other")
        info.size = 1
        handle.addfile(info, io.BytesIO(b"x"))
    result_config = _config(tmp_path)
    with pytest.raises(AdamAcquisitionError, match="lacks"):
        import_adam(result_config)
    _write_tar(archive, _ROW.encode())
    result = import_adam(_config(tmp_path, readme_path=tmp_path / "absent"))
    summary = result.to_dict()
    assert summary["readme_sha256"] is None
    resource_summary = cast(dict[str, object], summary["resource_summary"])
    assert resource_summary["variant_count"] == 2


@pytest.mark.parametrize(
    "line, message",
    [
        ("A\tA:1\tB:bad:0.5\t0.5\t1", "numeric"),
        ("A\tA:1\tB:1:-0.5\t0.5\t1", "between"),
        ("A\tA:1\tB:-1:0.5\t0.5\t1", "non-negative"),
        ("A\tA:1\tB:1:0.5\tbad\t1", "numeric"),
    ],
)
def test_adam_parser_rejects_invalid_variant_and_score_values(
    line: str, message: str
) -> None:
    with pytest.raises(AdamAcquisitionError, match=message):
        parse_adam_line(line)


def test_adam_config_loader_reports_missing_and_malformed_sections(
    tmp_path: Path,
) -> None:
    with pytest.raises(AdamAcquisitionError, match="Unable to read configuration"):
        load_adam_config(tmp_path / "missing.yaml")
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("adam_import: 4\n", encoding="utf-8")
    with pytest.raises(AdamAcquisitionError, match="mapping"):
        load_adam_config(malformed)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "adam_import:\n  tar_path: adam.tar\n  manifest_path: manifest\n"
        "  normalized_path: normalized\n  sqlite_path: sqlite\n  max_records: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(AdamAcquisitionError, match="invalid ADAM"):
        load_adam_config(invalid)


def test_adam_import_reports_corrupt_archive(tmp_path: Path) -> None:
    archive = tmp_path / "corrupt.tar"
    archive.write_bytes(b"not a tar archive")
    with pytest.raises(AdamAcquisitionError, match="unable to read"):
        import_adam(_config(tmp_path, tar_path=archive))
