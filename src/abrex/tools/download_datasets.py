"""Polite, resumable-ish downloads for user-supplied historical corpora.

This module intentionally uses only the standard library plus the project's
existing YAML loader. It never downloads at import time. Downloads are written
to a sibling ``.part`` file, optionally verified, and atomically moved into
place; archives are extracted with path-traversal protection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import load_config_layer

logger = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    """Raised when a configured dataset cannot be downloaded or verified."""


class DatasetDownloadConfig(BaseModel):
    """One declarative source and destination."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    destination: Path
    extract: bool = False
    strip_top_level_directory: bool = False
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class DatasetDownloadsConfig(BaseModel):
    """YAML boundary model for the downloader."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_agent: str = "abrex-dataset-downloader/1.0"
    timeout_seconds: float = Field(default=60.0, gt=0)
    retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=2.0, ge=0, le=3600)
    polite_delay_seconds: float = Field(default=1.0, ge=0, le=3600)
    overwrite: bool = False
    datasets: tuple[DatasetDownloadConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class DownloadedDataset:
    """A completed download and its content digest."""

    name: str
    url: str
    path: Path
    sha256: str
    extracted: bool


def load_download_config(path: Path) -> DatasetDownloadsConfig:
    """Load and validate the top-level ``downloads`` YAML section."""

    logger.info("Loading dataset download configuration: %s", path)
    raw = load_config_layer(path)
    section = raw.get("downloads")
    if not isinstance(section, dict):
        raise DownloadError(f"Configuration {path} must contain a downloads mapping")
    try:
        return DatasetDownloadsConfig.model_validate(section)
    except ValueError as error:
        raise DownloadError(
            f"Invalid download configuration {path}: {error}"
        ) from error


def download_datasets(config: DatasetDownloadsConfig) -> tuple[DownloadedDataset, ...]:
    """Download configured sources sequentially and write a provenance manifest."""

    logger.info("Starting download of %d dataset source(s)", len(config.datasets))
    results: list[DownloadedDataset] = []
    for index, dataset in enumerate(config.datasets):
        if index:
            time.sleep(config.polite_delay_seconds)
        results.append(_download_one(dataset, config))
    logger.info("Dataset download complete: %d source(s)", len(results))
    return tuple(results)


def _download_one(
    dataset: DatasetDownloadConfig, config: DatasetDownloadsConfig
) -> DownloadedDataset:
    logger.info("Downloading dataset %s", dataset.name)
    destination = dataset.destination
    if dataset.extract:
        archive = destination.with_suffix(destination.suffix + ".download")
        target = destination
    else:
        archive = destination
        target = destination
    if target.exists() and not config.overwrite:
        raise DownloadError(f"Destination already exists: {target}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(archive.name + ".part")
    _retrieve(dataset.url, temporary, config)
    digest = _sha256(temporary)
    if dataset.sha256 is not None and digest.lower() != dataset.sha256.lower():
        raise DownloadError(f"SHA-256 mismatch for {dataset.name}: {digest}")
    if dataset.extract:
        if target.exists():
            shutil.rmtree(target)
        extraction = target.with_name(target.name + ".part")
        if extraction.exists():
            shutil.rmtree(extraction)
        extraction.mkdir(parents=True)
        try:
            _extract_archive(
                temporary,
                extraction,
                strip_top_level_directory=dataset.strip_top_level_directory,
            )
            extraction.replace(target)
        except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as error:
            raise DownloadError(f"Unable to extract {dataset.name}: {error}") from error
        temporary.unlink()
        output_path = target
    else:
        temporary.replace(target)
        output_path = target
    result = DownloadedDataset(
        dataset.name, dataset.url, output_path, digest, dataset.extract
    )
    _write_manifest(result)
    logger.info(
        "Downloaded %s to %s (sha256=%s)", result.name, result.path, result.sha256
    )
    return result


def _retrieve(url: str, destination: Path, config: DatasetDownloadsConfig) -> None:
    last_error: Exception | None = None
    for attempt in range(config.retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": config.user_agent, "Accept": "*/*"},
            )
            with (
                urllib.request.urlopen(
                    request, timeout=config.timeout_seconds
                ) as response,
                destination.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream, length=1024 * 1024)
            return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            if attempt < config.retries:
                time.sleep(config.retry_delay_seconds * (2**attempt))
    raise DownloadError(f"Unable to download {url!r}: {last_error}") from last_error


def _extract_archive(
    archive: Path,
    destination: Path,
    *,
    strip_top_level_directory: bool = False,
) -> None:
    if zipfile.is_zipfile(archive):
        _extract_zip(
            archive,
            destination,
            strip_top_level_directory=strip_top_level_directory,
        )
        return
    if tarfile.is_tarfile(archive):
        _extract_tar(
            archive,
            destination,
            strip_top_level_directory=strip_top_level_directory,
        )
        return
    raise ValueError("download is not a supported ZIP or TAR archive")


def _extract_zip(
    archive: Path,
    destination: Path,
    *,
    strip_top_level_directory: bool = False,
) -> None:
    with zipfile.ZipFile(archive) as source:
        root = _top_level_directory(
            (member.filename for member in source.infolist()),
            strip=strip_top_level_directory,
        )
        for member in source.infolist():
            name = _strip_top_level_directory(member.filename, root)
            target = _safe_member(destination, name)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with (
                    source.open(member) as input_stream,
                    target.open("wb") as output_stream,
                ):
                    shutil.copyfileobj(input_stream, output_stream)


def _extract_tar(
    archive: Path,
    destination: Path,
    *,
    strip_top_level_directory: bool = False,
) -> None:
    with tarfile.open(archive) as source:
        root = _top_level_directory(
            (member.name for member in source.getmembers()),
            strip=strip_top_level_directory,
        )
        for member in source.getmembers():
            name = _strip_top_level_directory(member.name, root)
            target = _safe_member(destination, name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                input_stream = source.extractfile(member)
                if input_stream is None:
                    raise ValueError(f"Unable to read archive member {member.name!r}")
                with input_stream, target.open("wb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)


def _top_level_directory(names: Iterable[str], *, strip: bool) -> str | None:
    """Validate and return the sole archive root when root stripping is enabled."""

    if not strip:
        return None
    roots: set[str] = set()
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError(f"unsafe archive member path: {name!r}")
        roots.add(path.parts[0])
    if len(roots) != 1:
        raise ValueError("cannot strip top-level directory from a multi-root archive")
    return next(iter(roots))


def _strip_top_level_directory(member_name: str, root: str | None) -> str:
    """Remove one validated GitHub-style archive directory, if requested."""

    if root is None:
        return member_name
    path = PurePosixPath(member_name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    if path.parts[0] != root:
        raise ValueError(
            f"archive member is outside top-level directory: {member_name!r}"
        )
    relative = path.parts[1:]
    return "/".join(relative) if relative else "."


def _safe_member(destination: Path, member_name: str) -> Path:
    relative = PurePosixPath(member_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    target = (destination / Path(*relative.parts)).resolve()
    if destination.resolve() not in target.parents and target != destination.resolve():
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(result: DownloadedDataset) -> None:
    manifest = result.path.with_name(result.path.name + ".download.json")
    manifest.write_text(
        json.dumps(
            {
                "name": result.name,
                "url": result.url,
                "path": str(result.path),
                "sha256": result.sha256,
                "extracted": result.extracted,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def results_to_json(results: tuple[DownloadedDataset, ...]) -> str:
    """Serialize download results for CLI automation."""

    return (
        json.dumps(
            [
                {
                    "name": item.name,
                    "url": item.url,
                    "path": str(item.path),
                    "sha256": item.sha256,
                    "extracted": item.extracted,
                }
                for item in results
            ],
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


__all__ = [
    "DatasetDownloadConfig",
    "DatasetDownloadsConfig",
    "DownloadError",
    "DownloadedDataset",
    "download_datasets",
    "load_download_config",
    "results_to_json",
]
