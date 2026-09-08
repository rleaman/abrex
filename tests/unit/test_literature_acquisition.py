"""Offline contract tests for bounded literature acquisition."""

from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping
from email.message import Message
from pathlib import Path

import pytest

from abrex.literature.acquisition import (
    AcquisitionError,
    LiteratureAcquisitionConfig,
    acquire_pubmed,
    estimate_acquisition,
    load_acquisition_config,
    replay_acquisition,
)


def _config(tmp_path: Path, **overrides: object) -> LiteratureAcquisitionConfig:
    values: dict[str, object] = {
        "identifiers": ("1", "2", "3"),
        "output_dir": tmp_path / "raw",
        "manifest_path": tmp_path / "manifest.json",
        "batch_size": 2,
        "rate_limit_delay_seconds": 0,
        "retry_delay_seconds": 0,
    }
    values.update(overrides)
    return LiteratureAcquisitionConfig.model_validate(values)


def test_load_config_and_dry_run_are_bounded(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "literature_acquisition:\n"
        f"  identifiers: ['1', '2', '3']\n  output_dir: {tmp_path / 'raw'}\n"
        f"  manifest_path: {tmp_path / 'manifest.json'}\n  batch_size: 2\n",
        encoding="utf-8",
    )
    config = load_acquisition_config(path)
    estimate = estimate_acquisition(config)
    assert estimate.to_dict() == {
        "identifier_count": 3,
        "request_count": 2,
        "estimated_bytes": 300_000,
        "batch_size": 2,
    }
    assert not (tmp_path / "raw").exists()


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        LiteratureAcquisitionConfig(identifiers=("1", "1"), output_dir=Path("raw"))


def test_acquisition_retries_writes_manifest_and_reuses(tmp_path: Path) -> None:
    calls: list[str] = []
    attempts = 0

    def transport(url: str, timeout: float, headers: Mapping[str, str]) -> bytes:
        nonlocal attempts
        del timeout, headers
        calls.append(url)
        attempts += 1
        if attempts == 1:
            raise urllib.error.URLError("temporary")
        return b"<PubmedArticleSet><PubmedArticle/></PubmedArticleSet>"

    config = _config(tmp_path, identifiers=("1", "2"))
    result = acquire_pubmed(config, transport=transport)
    manifest = json.loads(config.resolved_manifest_path.read_text(encoding="utf-8"))
    assert result.summary["downloaded"] == 1
    assert result.summary["requests_successful"] == 1
    assert len(calls) == 2
    assert replay_acquisition(config.resolved_manifest_path)["valid"] == 1

    reused = acquire_pubmed(
        config,
        transport=lambda *_args: pytest.fail("reused response must not fetch"),
    )
    assert reused.summary["reused"] == 1
    assert manifest["query_snapshot"]["identifiers"] == ["1", "2"]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"identifiers": ("",)}, "non-empty"),
        ({"endpoint": "ftp://example.test"}, "HTTP"),
        ({"tool": ""}, "tool"),
        ({"email": ""}, "email"),
    ],
)
def test_config_rejects_unsafe_request_metadata(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _config(tmp_path, **overrides)


def test_default_manifest_and_result_serialization(tmp_path: Path) -> None:
    config = LiteratureAcquisitionConfig(identifiers=("1",), output_dir=tmp_path)
    assert config.resolved_manifest_path == tmp_path / "manifest.json"
    result = acquire_pubmed(
        config,
        transport=lambda *_args: b"<ok/>",
    )
    assert result.to_dict()["manifest_path"] == str(tmp_path / "manifest.json")


def test_acquisition_records_nonmissing_http_and_transport_failures(
    tmp_path: Path,
) -> None:
    calls = 0

    def transport(url: str, timeout: float, headers: Mapping[str, str]) -> bytes:
        nonlocal calls
        del timeout, headers
        calls += 1
        if "id=1%2C2" in url:
            raise urllib.error.HTTPError(url, 500, "server", Message(), None)
        raise urllib.error.URLError("offline")

    result = acquire_pubmed(_config(tmp_path, retries=0), transport=transport)
    assert result.summary["failed"] == 2
    assert calls == 2


def test_write_interruption_is_recorded_as_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_write(self: Path, data: bytes) -> int:
        del self, data
        raise OSError("interrupted")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    result = acquire_pubmed(
        _config(tmp_path, identifiers=("1",), retries=0),
        transport=lambda *_args: b"<ok/>",
    )
    assert result.summary["partial"] == 1


def test_default_urlopen_transport_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"<ok/>"

    monkeypatch.setattr(
        "abrex.literature.acquisition.urllib.request.urlopen",
        lambda _request, timeout: Response(),
    )
    result = acquire_pubmed(_config(tmp_path, identifiers=("1",)))
    assert result.summary["downloaded"] == 1


def test_load_and_replay_reject_malformed_manifests(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("other: {}\n", encoding="utf-8")
    with pytest.raises(AcquisitionError, match="literature_acquisition"):
        load_acquisition_config(config_path)
    config_path.write_text(
        "literature_acquisition:\n"
        "  identifiers: ['1']\n"
        "  output_dir: raw\n"
        "  batch_size: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(AcquisitionError, match="Invalid acquisition"):
        load_acquisition_config(config_path)

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": [None, {"status": "failed"}, {"status": "downloaded"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AcquisitionError, match="entry must be an object"):
        replay_acquisition(manifest)

    manifest.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": [{"status": "downloaded"}],
            }
        ),
        encoding="utf-8",
    )
    assert replay_acquisition(manifest)["invalid"] == ["unknown"]

    with pytest.raises(AcquisitionError, match="Unable to read"):
        replay_acquisition(tmp_path / "does-not-exist.json")

    invalid_entries = tmp_path / "invalid-entries.json"
    invalid_entries.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AcquisitionError, match="entries must be an array"):
        replay_acquisition(invalid_entries)

    bad_raw = tmp_path / "raw"
    bad_raw.mkdir()
    (bad_raw / "file.xml").write_bytes(b"changed")
    hash_manifest = tmp_path / "hash.json"
    hash_manifest.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": [
                    {
                        "status": "downloaded",
                        "path": "raw/file.xml",
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert replay_acquisition(hash_manifest)["invalid"] == ["unknown"]

    manifest.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": [{"status": "downloaded", "path": "x", "sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )
    assert replay_acquisition(manifest)["invalid"] == ["unknown"]


def test_rate_limit_and_endpoint_metadata_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter((0.0, 0.0, 1.0, 1.0))
    waits: list[float] = []
    monkeypatch.setenv("T025_API_KEY", "secret")
    config = _config(
        tmp_path,
        identifiers=("1", "2"),
        batch_size=1,
        rate_limit_delay_seconds=0.5,
        email="registered@example.org",
        api_key_env="T025_API_KEY",
    )
    acquire_pubmed(
        config,
        transport=lambda *_args: b"<ok/>",
        clock=lambda: next(times),
        sleep=waits.append,
    )
    manifest = json.loads(config.resolved_manifest_path.read_text(encoding="utf-8"))
    assert waits == [0.5]
    assert manifest["request_policy"]["email_configured"] is True
    assert manifest["request_policy"]["api_key_configured"] is True
    assert "api_key=secret" in manifest["query_snapshot"]["request_urls"][0]


def test_missing_response_is_counted_and_other_batches_continue(tmp_path: Path) -> None:
    def transport(url: str, timeout: float, headers: Mapping[str, str]) -> bytes:
        del timeout, headers
        if "id=1%2C2" in url:
            raise urllib.error.HTTPError(url, 404, "missing", Message(), None)
        return b"<ok/>"

    result = acquire_pubmed(_config(tmp_path), transport=transport)
    assert result.summary["missing"] == 1
    assert result.summary["downloaded"] == 1
    assert result.summary["requests"] == 2
    assert replay_acquisition(result.manifest_path)["checked"] == 1


def test_replay_rejects_path_escape_and_hash_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "literature-acquisition-v1",
                "entries": [
                    {"status": "downloaded", "path": "../outside", "sha256": "0" * 64}
                ],
            }
        ),
        encoding="utf-8",
    )
    report = replay_acquisition(manifest)
    assert report["invalid"] == ["unknown"]

    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(AcquisitionError, match="unsupported"):
        replay_acquisition(bad)
