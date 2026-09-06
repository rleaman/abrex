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
from abrex.tools.download_datasets import (
    DatasetDownloadConfig,
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


def _config(destination: Path, *, extract: bool = False) -> DatasetDownloadConfig:
    return DatasetDownloadConfig(
        name="sample",
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
    with pytest.raises(DownloadError, match="already exists"):
        downloads.download_datasets(config)
    with pytest.raises(DownloadError, match="SHA-256 mismatch"):
        downloads.download_datasets(
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
    second = tmp_path / "second"
    config = DatasetDownloadsConfig(
        overwrite=True,
        polite_delay_seconds=0.5,
        datasets=(_config(existing, extract=True), _config(second, extract=True)),
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
    with pytest.raises(DownloadError, match="Unable to extract"):
        downloads.download_datasets(
            DatasetDownloadsConfig(
                overwrite=True, datasets=(_config(tmp_path / "bad", extract=True),)
            )
        )


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
