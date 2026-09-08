"""Unit tests for safe, download-only historical source acquisition."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import urllib.error
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

import abrex.cli as cli
import abrex.tools.download_datasets as downloads
from abrex.config import ConfigError
from abrex.tools.download_datasets import (
    DatasetDownloadConfig,
    DatasetDownloadGroup,
    DatasetDownloadGroups,
    DatasetDownloadsConfig,
    DownloadedDataset,
    DownloadError,
)


class _Response:
    def __init__(self, content: bytes) -> None:
        self.stream = io.BytesIO(content)

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


def _config(
    destination: Path, *, extract: bool = False, name: str = "sample"
) -> DatasetDownloadConfig:
    return DatasetDownloadConfig(
        name=name,
        url="https://example.test/sample",
        destination=destination,
        extract=extract,
    )


def test_download_config_loading_and_validation(tmp_path: Path) -> None:
    path = tmp_path / "downloads.yaml"
    path.write_text(
        "downloads:\n"
        "  datasets:\n"
        "    - name: sample\n"
        "      url: https://example.test\n"
        "      destination: sample.txt\n",
        encoding="utf-8",
    )
    config = downloads.load_download_config(path)
    assert config.datasets[0].name == "sample"
    assert downloads.download_datasets(DatasetDownloadsConfig()) == ()

    missing = tmp_path / "missing.yaml"
    missing.write_text("project: {}\n", encoding="utf-8")
    with pytest.raises(DownloadError, match="downloads mapping"):
        downloads.load_download_config(missing)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("downloads:\n  retries: -1\n", encoding="utf-8")
    with pytest.raises(DownloadError, match="Invalid download"):
        downloads.load_download_config(invalid)


def test_retrieve_success_retries_and_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[float] = []

    def success(request: Any, timeout: float) -> _Response:
        calls.append(timeout)
        return _Response(b"downloaded")

    monkeypatch.setattr("abrex.tools.download_datasets.urllib.request.urlopen", success)
    destination = tmp_path / "success.part"
    downloads._retrieve("https://example.test", destination, DatasetDownloadsConfig())
    assert destination.read_bytes() == b"downloaded"
    assert calls == [60.0]

    attempts = 0

    def retry(request: Any, timeout: float) -> _Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise urllib.error.URLError("temporary")
        return _Response(b"retried")

    waits: list[float] = []
    monkeypatch.setattr("abrex.tools.download_datasets.urllib.request.urlopen", retry)
    monkeypatch.setattr("abrex.tools.download_datasets.time.sleep", waits.append)
    downloads._retrieve(
        "https://example.test",
        tmp_path / "retry.part",
        DatasetDownloadsConfig(retries=1, retry_delay_seconds=3),
    )
    assert attempts == 2
    assert waits == [3]

    def failure(request: Any, timeout: float) -> _Response:
        raise OSError("offline")

    monkeypatch.setattr("abrex.tools.download_datasets.urllib.request.urlopen", failure)
    with pytest.raises(DownloadError, match="Unable to download"):
        downloads._retrieve(
            "https://example.test",
            tmp_path / "failure.part",
            DatasetDownloadsConfig(retries=0),
        )


def test_download_file_digest_overwrite_and_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def retrieve(url: str, destination: Path, config: DatasetDownloadsConfig) -> None:
        destination.write_bytes(b"content")

    monkeypatch.setattr(downloads, "_retrieve", retrieve)
    destination = tmp_path / "nested" / "sample.txt"
    expected = hashlib.sha256(b"content").hexdigest()
    config = DatasetDownloadsConfig(overwrite=False, datasets=(_config(destination),))
    result = downloads.download_datasets(config)
    assert result[0].sha256 == expected
    assert destination.read_bytes() == b"content"
    assert (
        json.loads(
            destination.with_name("sample.txt.download.json").read_text(
                encoding="utf-8"
            )
        )["name"]
        == "sample"
    )
    reused = downloads.download_datasets(config)
    assert reused[0].status == "reused"
    failed = downloads.download_datasets(
        DatasetDownloadsConfig(
            overwrite=True,
            datasets=(
                DatasetDownloadConfig(
                    name="bad-digest",
                    url="url",
                    destination=destination,
                    sha256="0" * 64,
                ),
            ),
        )
    )
    assert failed[0].status == "failed"
    assert failed[0].diagnostic is not None
    assert "SHA-256 mismatch" in failed[0].diagnostic


def test_archive_extractors_and_safe_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_archive:
        zip_archive.writestr("nested/", "")
        zip_archive.writestr("nested/file.txt", "zip data")
    zip_destination = tmp_path / "zip-output"
    zip_destination.mkdir()
    downloads._extract_archive(zip_path, zip_destination)
    assert (zip_destination / "nested/file.txt").read_text() == "zip data"

    tar_path = tmp_path / "sample.tar"
    with tarfile.open(tar_path, "w") as tar_archive:
        directory = tarfile.TarInfo("folder")
        directory.type = tarfile.DIRTYPE
        tar_archive.addfile(directory)
        data = b"tar data"
        member = tarfile.TarInfo("folder/file.txt")
        member.size = len(data)
        tar_archive.addfile(member, io.BytesIO(data))
    tar_destination = tmp_path / "tar-output"
    tar_destination.mkdir()
    downloads._extract_archive(tar_path, tar_destination)
    assert (tar_destination / "folder/file.txt").read_text() == "tar data"

    unsupported = tmp_path / "not-an-archive"
    unsupported.write_text("not an archive", encoding="utf-8")
    with pytest.raises(ValueError, match="supported"):
        downloads._extract_archive(unsupported, tmp_path)
    with pytest.raises(ValueError, match="unsafe"):
        downloads._safe_member(tmp_path, "../escape")
    with pytest.raises(ValueError, match="unsafe"):
        downloads._safe_member(tmp_path, "/absolute")

    class EscapingPath:
        def resolve(self) -> Path:
            return Path("C:/inside")

        def __truediv__(self, value: object) -> EscapingPath:
            return EscapingTarget()

    class EscapingTarget(EscapingPath):
        def resolve(self) -> Path:
            return Path("C:/outside")

    with pytest.raises(ValueError, match="unsafe"):
        downloads._safe_member(cast(Any, EscapingPath()), "file.txt")

    flattened_zip = tmp_path / "github-style.zip"
    with zipfile.ZipFile(flattened_zip, "w") as archive:
        archive.writestr("repository-main/", "")
        archive.writestr("repository-main/data/train.json", "rows")
    flattened_destination = tmp_path / "flattened-output"
    flattened_destination.mkdir()
    downloads._extract_archive(
        flattened_zip,
        flattened_destination,
        strip_top_level_directory=True,
    )
    assert (flattened_destination / "data/train.json").read_text() == "rows"
    assert not (flattened_destination / "repository-main").exists()

    multi_root = tmp_path / "multi-root.zip"
    with zipfile.ZipFile(multi_root, "w") as archive:
        archive.writestr("one/file.txt", "one")
        archive.writestr("two/file.txt", "two")
    with pytest.raises(ValueError, match="multi-root"):
        downloads._extract_archive(
            multi_root,
            tmp_path / "multi-root-output",
            strip_top_level_directory=True,
        )

    class EmptyTar:
        def __enter__(self) -> EmptyTar:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def getmembers(self) -> list[tarfile.TarInfo]:
            return [tarfile.TarInfo("missing")]

        def extractfile(self, member: tarfile.TarInfo) -> None:
            return None

    monkeypatch.setattr(
        "abrex.tools.download_datasets.tarfile.open",
        lambda *args, **kwargs: EmptyTar(),
    )
    with pytest.raises(ValueError, match="Unable to read archive"):
        downloads._extract_tar(tmp_path / "sample.tar", tmp_path / "out")


def test_download_extract_overwrite_existing_parts_and_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_source = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_source, "w") as zip_archive:
        zip_archive.writestr("file.txt", "archive")

    def retrieve(url: str, destination: Path, config: DatasetDownloadsConfig) -> None:
        destination.write_bytes(archive_source.read_bytes())

    monkeypatch.setattr(downloads, "_retrieve", retrieve)
    waits: list[float] = []
    monkeypatch.setattr("abrex.tools.download_datasets.time.sleep", waits.append)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "old.txt").write_text("old", encoding="utf-8")
    (tmp_path / "existing.part").mkdir()
    (tmp_path / "existing.download.part").mkdir()
    second = tmp_path / "second"
    config = DatasetDownloadsConfig(
        overwrite=True,
        polite_delay_seconds=0.5,
        datasets=(
            _config(existing, extract=True, name="existing"),
            _config(second, extract=True, name="second"),
        ),
    )
    result = downloads.download_datasets(config)
    assert len(result) == 2
    assert waits == [0.5]
    assert (existing / "file.txt").is_file()

    def invalid_archive(
        url: str, destination: Path, config: DatasetDownloadsConfig
    ) -> None:
        destination.write_bytes(b"not an archive")

    monkeypatch.setattr(downloads, "_retrieve", invalid_archive)
    failed = downloads.download_datasets(
        DatasetDownloadsConfig(
            overwrite=True,
            datasets=(_config(tmp_path / "bad", extract=True),),
        )
    )
    assert failed[0].status == "failed"
    assert failed[0].diagnostic is not None
    assert "Unable to extract" in failed[0].diagnostic


def test_download_archive_and_cli_download_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive_source = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_source, "w") as archive:
        archive.writestr("inside.txt", "archive")

    def retrieve(url: str, destination: Path, config: DatasetDownloadsConfig) -> None:
        destination.write_bytes(archive_source.read_bytes())

    monkeypatch.setattr(downloads, "_retrieve", retrieve)
    target = tmp_path / "extracted"
    config = DatasetDownloadsConfig(datasets=(_config(target, extract=True),))
    result = downloads.download_datasets(config)
    assert result[0].extracted is True
    assert (target / "inside.txt").read_text() == "archive"

    monkeypatch.setattr(cli, "load_download_config", lambda path: config)
    monkeypatch.setattr(cli, "download_datasets", lambda value: tuple(result))
    assert cli.main(["datasets", "download", "ignored.yaml"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "sample"

    def fail(value: DatasetDownloadsConfig) -> tuple[DownloadedDataset, ...]:
        raise DownloadError("download failed")

    monkeypatch.setattr(cli, "download_datasets", fail)
    assert cli.main(["datasets", "download", "ignored.yaml"]) == 2
    assert "download failed" in capsys.readouterr().err


def test_dry_run_and_conflict_make_no_network_or_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "missing.txt"
    calls: list[str] = []

    def unexpected_retrieve(
        url: str, path: Path, config: DatasetDownloadsConfig
    ) -> None:
        calls.append(url)
        raise AssertionError("dry run made a network request")

    monkeypatch.setattr(downloads, "_retrieve", unexpected_retrieve)
    config = DatasetDownloadsConfig(datasets=(_config(destination),))
    planned = downloads.download_datasets(config, dry_run=True)
    assert planned[0].status == "planned"
    assert calls == []
    assert not destination.exists()

    destination.write_text("changed", encoding="utf-8")
    conflict = downloads.download_datasets(config, dry_run=True)
    assert conflict[0].status == "conflict"
    assert "--force" in (conflict[0].diagnostic or "")
    assert calls == []


def test_legacy_file_sidecar_is_migrated_without_network(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "legacy.txt"
    destination.write_text("legacy", encoding="utf-8")
    digest = hashlib.sha256(b"legacy").hexdigest()
    sidecar = destination.with_name("legacy.txt.download.json")
    sidecar.write_text(
        json.dumps(
            {
                "name": "sample",
                "url": "https://example.test/sample",
                "path": str(destination),
                "sha256": digest,
                "extracted": False,
            }
        ),
        encoding="utf-8",
    )
    result = downloads.download_datasets(
        DatasetDownloadsConfig(datasets=(_config(destination),))
    )
    assert result[0].status == "reused"
    migrated = json.loads(sidecar.read_text(encoding="utf-8"))
    assert migrated["version"] == 2
    assert migrated["archive_sha256_verified"] is True


def test_legacy_directory_sidecar_records_unverified_archive(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "legacy-directory"
    destination.mkdir()
    (destination / "data.txt").write_text("legacy", encoding="utf-8")
    sidecar = destination.with_name("legacy-directory.download.json")
    sidecar.write_text(
        json.dumps(
            {
                "name": "sample",
                "url": "https://example.test/sample",
                "path": str(destination),
                "sha256": "archive-digest-no-longer-verifiable",
                "extracted": True,
            }
        ),
        encoding="utf-8",
    )
    result = downloads.download_datasets(
        DatasetDownloadsConfig(
            datasets=(_config(destination, extract=True),),
        )
    )
    assert result[0].status == "reused"
    migrated = json.loads(sidecar.read_text(encoding="utf-8"))
    assert migrated["archive_sha256_verified"] is False
    assert migrated["output_sha256"] == result[0].output_sha256


def test_download_all_group_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle.yaml"
    bundle.write_text(
        "downloads:\n"
        "  datasets:\n"
        "    - name: grouped\n"
        "      url: https://example.test/grouped\n"
        f"      destination: {(tmp_path / 'grouped.txt').as_posix()}\n",
        encoding="utf-8",
    )
    groups = tmp_path / "groups.yaml"
    groups.write_text(
        f"groups:\n  test:\n    configs:\n      - {bundle.as_posix()}\n",
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "datasets",
                "download-all",
                "--group",
                "test",
                "--groups-config",
                str(groups),
                "--dry-run",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result[0]["name"] == "grouped"
    assert result[0]["status"] == "planned"


def test_duplicate_selection_is_rejected_before_download(tmp_path: Path) -> None:
    first = DatasetDownloadsConfig(datasets=(_config(tmp_path / "one"),))
    second = DatasetDownloadsConfig(datasets=(_config(tmp_path / "one", name="other"),))
    with pytest.raises(DownloadError, match="destinations must be unique"):
        downloads.validate_download_selection((first, second))


def test_download_config_rejects_duplicate_names_and_destinations(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "duplicate"
    with pytest.raises(ValueError, match="names must be unique"):
        DatasetDownloadsConfig(
            datasets=(
                _config(destination, name="same"),
                _config(tmp_path / "other", name="same"),
            )
        )
    with pytest.raises(ValueError, match="destinations must be unique"):
        DatasetDownloadsConfig(
            datasets=(_config(destination), _config(destination, name="other"))
        )


def test_malformed_and_stale_sidecars_are_conflicts(tmp_path: Path) -> None:
    destination = tmp_path / "artifact"
    destination.write_text("content", encoding="utf-8")
    sidecar = destination.with_name("artifact.download.json")
    sidecar.write_text("[]", encoding="utf-8")
    config = DatasetDownloadsConfig(datasets=(_config(destination),))
    result = downloads.download_datasets(config)
    assert result[0].status == "conflict"
    assert "sidecar is not an object" in (result[0].diagnostic or "")

    downloads._write_manifest(config.datasets[0], "archive", "0" * 64)
    result = downloads.download_datasets(config)
    assert result[0].status == "conflict"
    assert "destination content" in (result[0].diagnostic or "")


def test_group_loader_reports_unknown_and_invalid_groups(tmp_path: Path) -> None:
    groups = DatasetDownloadGroups(
        groups={"known": DatasetDownloadGroup(configs=(tmp_path / "one.yaml",))}
    )
    with pytest.raises(ConfigError, match="available groups: known"):
        groups.paths_for("missing")

    invalid = tmp_path / "invalid-groups.yaml"
    invalid.write_text("groups:\n  broken:\n    configs: []\n", encoding="utf-8")
    with pytest.raises(DownloadError, match="Invalid dataset group"):
        downloads.load_download_groups(invalid)


def test_publish_guards_existing_destinations_and_backups(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.write_text("old", encoding="utf-8")
    staging = tmp_path / "staging"
    staging.write_text("new", encoding="utf-8")
    with pytest.raises(DownloadError, match="Destination already exists"):
        downloads._publish(staging, destination, force=False)

    staging.write_text("new", encoding="utf-8")
    backup = tmp_path / "destination.backup"
    backup.write_text("stale backup", encoding="utf-8")
    downloads._publish(staging, destination, force=True)
    assert destination.read_text(encoding="utf-8") == "new"
    assert not backup.exists()
