"""Bounded, manifest-first acquisition of PubMed EFetch responses.

The acquisition layer intentionally stops at immutable raw responses.  XML and
BioC parsing belong to the offline readers in the next task; this module does
not turn a mutable search into an implicit scientific corpus.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import load_config_layer

logger = logging.getLogger(__name__)

ACQUISITION_SCHEMA_VERSION = "literature-acquisition-v1"
DEFAULT_NCBI_ENDPOINT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class AcquisitionError(RuntimeError):
    """Raised when a literature acquisition plan is invalid or unrecoverable."""


ResponseTransport = Callable[[str, float, Mapping[str, str]], bytes]


class LiteratureAcquisitionConfig(BaseModel):
    """Validated configuration for a bounded fixed-ID PubMed snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = "ncbi_pubmed_efetch"
    identifiers: tuple[str, ...] = Field(min_length=1)
    output_dir: Path
    manifest_path: Path | None = None
    endpoint: str = DEFAULT_NCBI_ENDPOINT
    database: str = "pubmed"
    response_format: str = "xml"
    batch_size: int = Field(default=20, ge=1, le=200)
    timeout_seconds: float = Field(default=60.0, gt=0, le=3600)
    retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=2.0, ge=0, le=3600)
    rate_limit_delay_seconds: float = Field(default=0.34, ge=0, le=3600)
    user_agent: str = "abrex-literature-acquisition/1.0"
    tool: str = "abrex"
    email: str | None = None
    api_key_env: str | None = None
    estimated_bytes_per_record: int = Field(default=100_000, ge=1)
    license_metadata: str = (
        "NCBI/PubMed terms apply; verify article-level reuse before redistribution."
    )
    intended_use: str = "bounded local parsing and resolver pilot"

    def model_post_init(self, __context: object) -> None:
        """Reject duplicate IDs rather than silently changing the query frame."""

        if any(not identifier.strip() for identifier in self.identifiers):
            raise ValueError("identifiers must contain non-empty values")
        if len(set(self.identifiers)) != len(self.identifiers):
            raise ValueError("identifiers must be unique")
        if not self.endpoint.startswith(("https://", "http://")):
            raise ValueError("endpoint must be an HTTP(S) URL")
        if not self.tool.strip():
            raise ValueError("tool must be non-empty")
        if self.email is not None and not self.email.strip():
            raise ValueError("email must be non-empty when provided")

    @property
    def resolved_manifest_path(self) -> Path:
        """Return the configured manifest path or its deterministic default."""

        return self.manifest_path or self.output_dir / "manifest.json"


@dataclass(frozen=True, slots=True)
class AcquisitionEstimate:
    """Bounded request and storage estimate produced without network access."""

    identifier_count: int
    request_count: int
    estimated_bytes: int
    batch_size: int

    def to_dict(self) -> dict[str, int]:
        return {
            "identifier_count": self.identifier_count,
            "request_count": self.request_count,
            "estimated_bytes": self.estimated_bytes,
            "batch_size": self.batch_size,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    """Acquisition summary and the written manifest location."""

    manifest_path: Path
    summary: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {"manifest_path": str(self.manifest_path), "summary": dict(self.summary)}


def load_acquisition_config(path: Path) -> LiteratureAcquisitionConfig:
    """Load the ``literature_acquisition`` YAML section."""

    raw = load_config_layer(path)
    section = raw.get("literature_acquisition")
    if not isinstance(section, Mapping):
        raise AcquisitionError(
            f"Configuration {path} must contain a literature_acquisition mapping"
        )
    try:
        return LiteratureAcquisitionConfig.model_validate(section)
    except ValueError as error:
        raise AcquisitionError(
            f"Invalid acquisition configuration {path}: {error}"
        ) from error


def estimate_acquisition(config: LiteratureAcquisitionConfig) -> AcquisitionEstimate:
    """Estimate requests and bytes without contacting an external service."""

    request_count = (
        len(config.identifiers) + config.batch_size - 1
    ) // config.batch_size
    return AcquisitionEstimate(
        identifier_count=len(config.identifiers),
        request_count=request_count,
        estimated_bytes=len(config.identifiers) * config.estimated_bytes_per_record,
        batch_size=config.batch_size,
    )


def acquire_pubmed(
    config: LiteratureAcquisitionConfig,
    *,
    transport: ResponseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    retrieved_at: Callable[[], str] | None = None,
) -> AcquisitionResult:
    """Fetch a fixed, bounded PubMed ID list and publish its manifest last.

    Existing response files with the same request fingerprint are reused after
    hash verification.  Each request is written to a task-owned ``.part``
    file before an atomic rename, so an interruption remains recoverable.
    """

    config.output_dir.mkdir(parents=True, exist_ok=True)
    transport = transport or _urlopen_transport
    timestamp = retrieved_at or _utc_now
    entries: list[dict[str, object]] = []
    last_request_at: float | None = None
    for request_index, identifiers in enumerate(
        _batches(config.identifiers, config.batch_size), 1
    ):
        url = _request_url(config, identifiers)
        request_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        target = config.output_dir / f"request-{request_index:04d}-{request_key}.xml"
        relative_target = target.relative_to(config.resolved_manifest_path.parent)
        if target.exists():
            digest, size = _file_digest(target)
            entries.append(
                _entry(
                    request_index,
                    identifiers,
                    relative_target,
                    "reused",
                    digest=digest,
                    byte_count=size,
                )
            )
            continue

        if last_request_at is not None:
            remaining = config.rate_limit_delay_seconds - (clock() - last_request_at)
            if remaining > 0:
                sleep(remaining)
        last_request_at = clock()
        try:
            payload = _retrieve_with_retries(config, url, transport, sleep)
        except urllib.error.HTTPError as error:
            status = "missing" if error.code == 404 else "failed"
            entries.append(
                _entry(
                    request_index,
                    identifiers,
                    relative_target,
                    status,
                    error=f"HTTP {error.code}: {error.reason}",
                )
            )
            continue
        except (OSError, urllib.error.URLError) as error:
            part = target.with_name(target.name + ".part")
            status = "partial" if part.exists() else "failed"
            entries.append(
                _entry(
                    request_index,
                    identifiers,
                    relative_target,
                    status,
                    error=str(error),
                )
            )
            continue

        part = target.with_name(target.name + ".part")
        try:
            part.write_bytes(payload)
            part.replace(target)
        except OSError as error:
            entries.append(
                _entry(
                    request_index,
                    identifiers,
                    relative_target,
                    "partial",
                    error=str(error),
                )
            )
            continue
        digest, size = _file_digest(target)
        entries.append(
            _entry(
                request_index,
                identifiers,
                relative_target,
                "downloaded",
                digest=digest,
                byte_count=size,
            )
        )

    summary = _summary(entries, len(config.identifiers), len(entries))
    manifest = {
        "schema_version": ACQUISITION_SCHEMA_VERSION,
        "source": config.source,
        "endpoint": config.endpoint,
        "retrieved_at": timestamp(),
        "query_snapshot": {
            "database": config.database,
            "response_format": config.response_format,
            "identifiers": list(config.identifiers),
            "batch_size": config.batch_size,
            "request_urls": [
                _request_url(config, batch)
                for batch in _batches(config.identifiers, config.batch_size)
            ],
        },
        "request_policy": {
            "timeout_seconds": config.timeout_seconds,
            "retries": config.retries,
            "retry_delay_seconds": config.retry_delay_seconds,
            "rate_limit_delay_seconds": config.rate_limit_delay_seconds,
            "tool": config.tool,
            "email_configured": config.email is not None,
            "api_key_configured": bool(
                config.api_key_env and os.getenv(config.api_key_env)
            ),
        },
        "access": {
            "license_metadata": config.license_metadata,
            "intended_use": config.intended_use,
        },
        "summary": summary,
        "entries": entries,
    }
    _write_json_atomic(config.resolved_manifest_path, manifest)
    return AcquisitionResult(config.resolved_manifest_path, summary)


def replay_acquisition(manifest_path: Path) -> dict[str, object]:
    """Validate recorded raw files and hashes without network access."""

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AcquisitionError(
            f"Unable to read acquisition manifest: {error}"
        ) from error
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema_version") != ACQUISITION_SCHEMA_VERSION
    ):
        raise AcquisitionError("unsupported or malformed acquisition manifest")
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise AcquisitionError("acquisition manifest entries must be an array")
    checked = 0
    valid = 0
    invalid: list[str] = []
    root = manifest_path.parent.resolve()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise AcquisitionError("acquisition manifest entry must be an object")
        status = raw_entry.get("status")
        if status not in {"downloaded", "reused"}:
            continue
        checked += 1
        relative = raw_entry.get("path")
        expected = raw_entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            invalid.append(str(raw_entry.get("request_index", "unknown")))
            continue
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            invalid.append(str(raw_entry.get("request_index", "unknown")))
            continue
        actual, _ = _file_digest(path)
        if actual != expected:
            invalid.append(str(raw_entry.get("request_index", "unknown")))
        else:
            valid += 1
    return {
        "manifest_path": str(manifest_path),
        "checked": checked,
        "valid": valid,
        "invalid": invalid,
    }


def _retrieve_with_retries(
    config: LiteratureAcquisitionConfig,
    url: str,
    transport: ResponseTransport,
    sleep: Callable[[float], None],
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(config.retries + 1):
        try:
            return transport(url, config.timeout_seconds, _headers(config))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise
            last_error = error
        except (OSError, urllib.error.URLError) as error:
            last_error = error
        if attempt < config.retries:
            sleep(config.retry_delay_seconds * (2**attempt))
    assert last_error is not None
    raise last_error


def _urlopen_transport(
    url: str, timeout_seconds: float, headers: Mapping[str, str]
) -> bytes:
    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return cast(bytes, response.read())


def _headers(config: LiteratureAcquisitionConfig) -> dict[str, str]:
    return {"User-Agent": config.user_agent, "Accept": "application/xml,text/xml,*/*"}


def _request_url(
    config: LiteratureAcquisitionConfig, identifiers: tuple[str, ...]
) -> str:
    params: dict[str, str] = {
        "db": config.database,
        "id": ",".join(identifiers),
        "retmode": config.response_format,
    }
    if config.tool:
        params["tool"] = config.tool
    if config.email:
        params["email"] = config.email
    if config.api_key_env:
        api_key = os.getenv(config.api_key_env)
        if api_key:
            params["api_key"] = api_key
    separator = "&" if "?" in config.endpoint else "?"
    return config.endpoint + separator + urllib.parse.urlencode(params)


def _batches(
    identifiers: tuple[str, ...], batch_size: int
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        identifiers[index : index + batch_size]
        for index in range(0, len(identifiers), batch_size)
    )


def _entry(
    request_index: int,
    identifiers: tuple[str, ...],
    path: Path,
    status: str,
    *,
    digest: str | None = None,
    byte_count: int | None = None,
    error: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "request_index": request_index,
        "identifiers": list(identifiers),
        "path": path.as_posix(),
        "status": status,
    }
    if digest is not None:
        entry["sha256"] = digest
    if byte_count is not None:
        entry["bytes"] = byte_count
    if error is not None:
        entry["error"] = error
    return entry


def _summary(
    entries: list[dict[str, object]], identifier_count: int, request_count: int
) -> dict[str, int]:
    counts = {
        "downloaded": 0,
        "reused": 0,
        "missing": 0,
        "failed": 0,
        "partial": 0,
    }
    for entry in entries:
        status = entry.get("status")
        if isinstance(status, str) and status in counts:
            counts[status] += 1
    counts.update(
        {
            "identifiers_requested": identifier_count,
            "requests": request_count,
            "requests_successful": counts["downloaded"] + counts["reused"],
        }
    )
    return counts


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _write_json_atomic(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "ACQUISITION_SCHEMA_VERSION",
    "AcquisitionError",
    "AcquisitionEstimate",
    "AcquisitionResult",
    "LiteratureAcquisitionConfig",
    "acquire_pubmed",
    "estimate_acquisition",
    "load_acquisition_config",
    "replay_acquisition",
]
