"""Safe, idempotent acquisition of configured historical dataset sources."""

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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abrex.config import ConfigError, load_config_layer

logger = logging.getLogger(__name__)
PROVENANCE_VERSION = 2


class DownloadError(RuntimeError):
    """Raised for configuration or operational download failures."""


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
    """Typed YAML boundary model for one acquisition bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    user_agent: str = "abrex-dataset-downloader/1.0"
    timeout_seconds: float = Field(default=60.0, gt=0)
    retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=2.0, ge=0, le=3600)
    polite_delay_seconds: float = Field(default=1.0, ge=0, le=3600)
    overwrite: bool = False  # Legacy compatibility; CLI --force is preferred.
    datasets: tuple[DatasetDownloadConfig, ...] = ()

    @field_validator("datasets")
    @classmethod
    def _unique_items(
        cls, value: tuple[DatasetDownloadConfig, ...]
    ) -> tuple[DatasetDownloadConfig, ...]:
        names = [item.name for item in value]
        destinations = [str(item.destination.resolve()) for item in value]
        if len(names) != len(set(names)):
            raise ValueError("dataset names must be unique")
        if len(destinations) != len(set(destinations)):
            raise ValueError("dataset destinations must be unique")
        return value


class DatasetDownloadGroup(BaseModel):
    """A declared, ordered group of one-bundle YAML paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    configs: tuple[Path, ...] = Field(min_length=1)


class DatasetDownloadGroups(BaseModel):
    """Configuration-driven dataset download groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    groups: dict[str, DatasetDownloadGroup]

    def paths_for(self, name: str) -> tuple[Path, ...]:
        try:
            return self.groups[name].configs
        except KeyError as error:
            available = ", ".join(sorted(self.groups)) or "<none>"
            raise ConfigError(
                f"Unknown dataset download group {name!r}; "
                f"available groups: {available}"
            ) from error


@dataclass(frozen=True, slots=True)
class DownloadedDataset:
    """Stable machine-readable result for one requested source."""

    name: str
    url: str
    path: Path
    sha256: str
    extracted: bool
    status: Literal["downloaded", "reused", "planned", "conflict", "failed"] = (
        "downloaded"
    )
    diagnostic: str | None = None
    output_sha256: str | None = None


def load_download_config(path: Path) -> DatasetDownloadsConfig:
    """Load one bundle, or the legacy aggregate manifest."""

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


def load_download_groups(path: Path) -> DatasetDownloadGroups:
    """Load the named dataset group manifest."""

    try:
        return DatasetDownloadGroups.model_validate(load_config_layer(path))
    except ValueError as error:
        raise DownloadError(
            f"Invalid dataset group configuration {path}: {error}"
        ) from error


def download_datasets(
    config: DatasetDownloadsConfig, *, dry_run: bool = False, force: bool = False
) -> tuple[DownloadedDataset, ...]:
    """Plan or execute a bundle, continuing after independent item failures."""

    _validate_config(config)
    effective_force = force or config.overwrite
    results: list[DownloadedDataset] = []
    requested = False
    for dataset in config.datasets:
        plan = _inspect(dataset, effective_force)
        if dry_run or plan.status in {"reused", "conflict"} and not effective_force:
            if (
                not dry_run
                and plan.status == "reused"
                and plan.diagnostic is not None
                and plan.diagnostic.startswith("migrated legacy")
            ):
                _write_manifest(
                    dataset,
                    plan.sha256,
                    plan.output_sha256 or "",
                    archive_verified=not plan.diagnostic.startswith(
                        "migrated legacy directory"
                    ),
                )
            results.append(plan)
            continue
        if requested:
            time.sleep(config.polite_delay_seconds)
        requested = True
        try:
            results.append(_download_one(dataset, config, force=effective_force))
        except DownloadError as error:
            results.append(_result(dataset, "failed", str(error)))
    summary = ", ".join(
        f"{status}={sum(r.status == status for r in results)}"
        for status in ("downloaded", "reused", "planned", "conflict", "failed")
    )
    logger.info("Dataset download complete: %s", summary)
    return tuple(results)


def validate_download_selection(
    configs: tuple[DatasetDownloadsConfig, ...],
) -> None:
    """Reject duplicate sources across a resolved single/group operation."""

    datasets = tuple(item for config in configs for item in config.datasets)
    names = [item.name for item in datasets]
    paths = [str(item.destination.resolve()) for item in datasets]
    if len(names) != len(set(names)):
        raise DownloadError(
            "dataset names must be unique across the requested operation"
        )
    if len(paths) != len(set(paths)):
        raise DownloadError(
            "dataset destinations must be unique across the requested operation"
        )


def _validate_config(config: DatasetDownloadsConfig) -> None:
    names = [item.name for item in config.datasets]
    paths = [str(item.destination.resolve()) for item in config.datasets]
    if len(names) != len(set(names)) or len(paths) != len(set(paths)):
        raise DownloadError("dataset names and destinations must be unique")


def _sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".download.json")


def _identity(dataset: DatasetDownloadConfig) -> dict[str, object]:
    return {
        "name": dataset.name,
        "url": dataset.url,
        "destination": str(dataset.destination),
        "extract": dataset.extract,
        "strip_top_level_directory": dataset.strip_top_level_directory,
        "configured_sha256": dataset.sha256,
    }


def _inspect(dataset: DatasetDownloadConfig, force: bool) -> DownloadedDataset:
    target = dataset.destination
    sidecar = _sidecar(target)
    if not target.exists():
        return _result(dataset, "planned", "destination is absent")
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("sidecar is not an object")
        if record.get("version") != PROVENANCE_VERSION:
            if not dataset.extract and record.get("sha256") == _sha256(target):
                return _result(
                    dataset,
                    "reused",
                    "migrated legacy provenance",
                    record,
                    _sha256(target),
                )
            if (
                dataset.extract
                and record.get("name") == dataset.name
                and record.get("url") == dataset.url
            ):
                return _result(
                    dataset,
                    "reused",
                    "migrated legacy directory provenance",
                    record,
                    _tree_fingerprint(target),
                )
            raise ValueError("sidecar version is not trustworthy")
        if record.get("identity") != _identity(dataset):
            raise ValueError("source or extraction configuration changed")
        actual = _tree_fingerprint(target) if dataset.extract else _sha256(target)
        if record.get("output_sha256") != actual:
            raise ValueError("destination content does not match recorded identity")
        return _result(dataset, "reused", None, record, actual)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        remedy = "; rerun with --force to replace it"
        return _result(dataset, "planned" if force else "conflict", f"{error}{remedy}")


def _result(
    dataset: DatasetDownloadConfig,
    status: Literal["downloaded", "reused", "planned", "conflict", "failed"],
    diagnostic: str | None = None,
    record: dict[str, object] | None = None,
    output_sha256: str | None = None,
) -> DownloadedDataset:
    return DownloadedDataset(
        dataset.name,
        dataset.url,
        dataset.destination,
        str(record.get("sha256", "")) if record else "",
        dataset.extract,
        status,
        diagnostic,
        output_sha256,
    )


def _download_one(
    dataset: DatasetDownloadConfig, config: DatasetDownloadsConfig, *, force: bool
) -> DownloadedDataset:
    destination = dataset.destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive = (
        destination.with_name(destination.name + ".download")
        if dataset.extract
        else destination
    )
    temporary = archive.with_name(archive.name + ".part")
    if temporary.exists():
        _remove_path(temporary)
    _retrieve(dataset.url, temporary, config)
    digest = _sha256(temporary)
    if dataset.sha256 is not None and digest.lower() != dataset.sha256.lower():
        _remove_path(temporary)
        raise DownloadError(f"SHA-256 mismatch for {dataset.name}: {digest}")
    staging = (
        destination.with_name(destination.name + ".part")
        if dataset.extract
        else temporary
    )
    try:
        if dataset.extract:
            if staging.exists():
                _remove_path(staging)
            staging.mkdir(parents=True)
            _extract_archive(
                temporary,
                staging,
                strip_top_level_directory=dataset.strip_top_level_directory,
            )
            temporary.unlink()
        _publish(staging, destination, force=force)
        output_id = (
            _tree_fingerprint(destination) if dataset.extract else _sha256(destination)
        )
        _write_manifest(dataset, digest, output_id)
    except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as error:
        if temporary.exists():
            _remove_path(temporary)
        if dataset.extract and staging.exists():
            _remove_path(staging)
        message = (
            f"Unable to extract {dataset.name}: {error}"
            if dataset.extract
            else f"Unable to prepare or publish {dataset.name}: {error}"
        )
        raise DownloadError(message) from error
    return DownloadedDataset(
        dataset.name,
        dataset.url,
        destination,
        digest,
        dataset.extract,
        "downloaded",
        None,
        output_id,
    )


def _publish(staging: Path, destination: Path, *, force: bool) -> None:
    if not destination.exists():
        staging.replace(destination)
        return
    if not force:
        raise DownloadError(
            f"Destination already exists: {destination}; rerun with --force"
        )
    backup = destination.with_name(destination.name + ".backup")
    if backup.exists():
        _remove_path(backup)
    destination.replace(backup)
    try:
        staging.replace(destination)
    except OSError:
        if destination.exists():
            _remove_path(destination)
        backup.replace(destination)
        raise
    _remove_path(backup)


def _write_manifest(
    dataset: DatasetDownloadConfig,
    digest: str,
    output_id: str,
    *,
    archive_verified: bool = True,
) -> None:
    payload = {
        "version": PROVENANCE_VERSION,
        "identity": _identity(dataset),
        "name": dataset.name,
        "url": dataset.url,
        "path": str(dataset.destination),
        "sha256": digest,
        "extracted": dataset.extract,
        "output_sha256": output_id,
        "archive_sha256_verified": archive_verified,
    }
    target = _sidecar(dataset.destination)
    temporary = target.with_name(target.name + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(target)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _retrieve(url: str, destination: Path, config: DatasetDownloadsConfig) -> None:
    last_error: Exception | None = None
    for attempt in range(config.retries + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": config.user_agent, "Accept": "*/*"}
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


def _tree_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(
        path.rglob("*"), key=lambda value: value.relative_to(path).as_posix()
    ):
        if item.is_file():
            digest.update(
                item.relative_to(path).as_posix().encode("utf-8")
                + b"\0"
                + _sha256(item).encode("ascii")
                + b"\n"
            )
    return digest.hexdigest()


def _extract_archive(
    archive: Path, destination: Path, *, strip_top_level_directory: bool = False
) -> None:
    if zipfile.is_zipfile(archive):
        _extract_zip(
            archive, destination, strip_top_level_directory=strip_top_level_directory
        )
    elif tarfile.is_tarfile(archive):
        _extract_tar(
            archive, destination, strip_top_level_directory=strip_top_level_directory
        )
    else:
        raise ValueError("download is not a supported ZIP or TAR archive")


def _extract_zip(
    archive: Path, destination: Path, *, strip_top_level_directory: bool = False
) -> None:
    with zipfile.ZipFile(archive) as source:
        root = _top_level_directory(
            (member.filename for member in source.infolist()),
            strip=strip_top_level_directory,
        )
        for member in source.infolist():
            target = _safe_member(
                destination, _strip_top_level_directory(member.filename, root)
            )
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
    archive: Path, destination: Path, *, strip_top_level_directory: bool = False
) -> None:
    with tarfile.open(archive) as source:
        root = _top_level_directory(
            (member.name for member in source.getmembers()),
            strip=strip_top_level_directory,
        )
        for member in source.getmembers():
            target = _safe_member(
                destination, _strip_top_level_directory(member.name, root)
            )
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
    if root is None:
        return member_name
    path = PurePosixPath(member_name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != root
    ):
        raise ValueError(f"unsafe archive member path: {member_name!r}")
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


def results_to_json(results: tuple[DownloadedDataset, ...]) -> str:
    return (
        json.dumps(
            [
                {
                    "name": item.name,
                    "url": item.url,
                    "path": str(item.path),
                    "sha256": item.sha256,
                    "extracted": item.extracted,
                    "status": item.status,
                    **({"diagnostic": item.diagnostic} if item.diagnostic else {}),
                    **(
                        {"output_sha256": item.output_sha256}
                        if item.output_sha256
                        else {}
                    ),
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
    "DatasetDownloadGroup",
    "DatasetDownloadGroups",
    "DownloadError",
    "DownloadedDataset",
    "download_datasets",
    "load_download_config",
    "load_download_groups",
    "results_to_json",
    "validate_download_selection",
]
