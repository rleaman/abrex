"""Source-specific ALLIE acquisition tests using bounded local XML fixtures."""

from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping
from pathlib import Path

import pytest

from abrex.resources import (
    AllieAcquisitionConfig,
    AllieAcquisitionError,
    acquire_allie,
    load_allie_config,
    parse_allie_xml,
)

_XML = b"""<?xml version="1.0"?>
<entry query="AML">
  <item seqid="0"><pair_id>10</pair_id><abbreviation>AML</abbreviation>
    <long_form>acute myeloid leukemia</long_form><pair_number>35329</pair_number></item>
  <item seqid="1"><pair_id>11</pair_id><abbreviation>AML</abbreviation>
    <long_form>angiomyolipoma</long_form><pair_number>807</pair_number></item>
</entry>
"""


def _config(tmp_path: Path, **overrides: object) -> AllieAcquisitionConfig:
    values: dict[str, object] = {
        "keywords": ("AML",),
        "output_dir": tmp_path / "raw",
        "manifest_path": tmp_path / "manifest.json",
        "normalized_path": tmp_path / "allie.json.gz",
        "sqlite_path": tmp_path / "allie.sqlite",
        "retries": 1,
    }
    values.update(overrides)
    return AllieAcquisitionConfig.model_validate(values)


def test_parse_allie_xml_preserves_ids_variants_counts() -> None:
    pairs = parse_allie_xml(_XML, max_pairs=1)
    assert len(pairs) == 1
    assert pairs[0].pair_id == 10
    assert pairs[0].long_form == "acute myeloid leukemia"
    assert pairs[0].appearance_count == 35329


def test_acquire_allie_imports_through_t028_and_reuses_raw_response(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def transport(url: str, timeout: float, headers: Mapping[str, str]) -> bytes:
        del timeout, headers
        calls.append(url)
        return _XML

    result = acquire_allie(_config(tmp_path), transport=transport)
    assert len(calls) == 1
    assert result.to_dict()["pair_count"] == 2
    assert result.resource.lookup("AML")[0].count == 35329
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["count_unit"] == "pair-appearance-count"
    assert manifest["pairs"][0]["pair_id"] == 10
    assert manifest["rights_status"].startswith("official_terms_reference")

    reused = acquire_allie(
        _config(tmp_path),
        transport=lambda *_args: pytest.fail("existing raw response must be reused"),
    )
    assert reused.raw_sha256 == result.raw_sha256


def test_allie_config_and_transport_failures_are_explicit(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "allie_acquisition:\n"
        f"  keywords: [AML]\n  output_dir: {tmp_path / 'raw'}\n"
        f"  manifest_path: {tmp_path / 'manifest.json'}\n"
        f"  normalized_path: {tmp_path / 'allie.json.gz'}\n"
        f"  sqlite_path: {tmp_path / 'allie.sqlite'}\n",
        encoding="utf-8",
    )
    assert load_allie_config(config_path).keywords == ("AML",)
    with pytest.raises(AllieAcquisitionError, match="request failed"):
        acquire_allie(
            _config(tmp_path / "failed"),
            transport=lambda *_args: (_ for _ in ()).throw(
                AllieAcquisitionError("request failed")
            ),
        )
    missing = tmp_path / "missing.yaml"
    with pytest.raises(AllieAcquisitionError, match="Unable to read configuration"):
        load_allie_config(missing)
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("allie_acquisition: 4\n", encoding="utf-8")
    with pytest.raises(AllieAcquisitionError, match="mapping"):
        load_allie_config(malformed)


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"not xml", "invalid ALLIE XML"),
        (b"<entry><item><pair_id>1</pair_id></item></entry>", "abbreviation"),
        (
            b"<entry><item><pair_id>1</pair_id><abbreviation>A</abbreviation>"
            b"<long_form>B</long_form><pair_number>1</pair_number></item>"
            b"<item><pair_id>1</pair_id><abbreviation>A</abbreviation>"
            b"<long_form>C</long_form><pair_number>1</pair_number></item></entry>",
            "duplicate",
        ),
        (b"<entry />", "no pair"),
    ],
)
def test_parse_allie_rejects_malformed_responses(payload: bytes, message: str) -> None:
    with pytest.raises(AllieAcquisitionError, match=message):
        parse_allie_xml(payload)


def test_allie_config_rejects_unsafe_or_ambiguous_values(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        _config(tmp_path, keywords=("AML", "AML"))
    with pytest.raises(ValueError, match="HTTPS"):
        _config(tmp_path, endpoint="http://example.test")
    with pytest.raises(ValueError, match="non-empty"):
        _config(tmp_path, source_label=" ")
    with pytest.raises(ValueError, match="non-empty"):
        _config(tmp_path, keywords=("",))


def test_allie_default_transport_and_numeric_parser_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return _XML

    monkeypatch.setattr(
        "abrex.resources.allie.urllib.request.urlopen",
        lambda _request, timeout: Response(),
    )
    assert acquire_allie(_config(tmp_path)).pairs[0].pair_id == 10
    monkeypatch.setattr(
        "abrex.resources.allie.urllib.request.urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(
            urllib.error.URLError("offline")
        ),
    )
    with pytest.raises(AllieAcquisitionError, match="request failed"):
        acquire_allie(_config(tmp_path / "offline"))
    with pytest.raises(AllieAcquisitionError, match="integer"):
        parse_allie_xml(
            b"<entry><item><pair_id>bad</pair_id><abbreviation>A</abbreviation>"
            b"<long_form>B</long_form><pair_number>1</pair_number></item></entry>"
        )
    with pytest.raises(AllieAcquisitionError, match="non-negative"):
        parse_allie_xml(
            b"<entry><item><pair_id>1</pair_id><abbreviation>A</abbreviation>"
            b"<long_form>B</long_form><pair_number>-1</pair_number></item></entry>"
        )
