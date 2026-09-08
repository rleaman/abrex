"""Bounded acquisition and source-specific parsing for the ALLIE REST API."""

from __future__ import annotations

import gzip
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import load_config_layer
from abrex.resources.frequency import (
    FrequencyResource,
    FrequencyResourceConfig,
    import_frequency_resource,
)

ALLIE_ACQUISITION_SCHEMA_VERSION = "allie-acquisition-v1"
AllieTransport = Callable[[str, float, Mapping[str, str]], bytes]


class AllieAcquisitionError(RuntimeError):
    """Raised when an ALLIE response cannot be acquired or reconciled."""


class AllieAcquisitionConfig(BaseModel):
    """Typed boundary for a bounded official ALLIE REST query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    keywords: tuple[str, ...] = Field(min_length=1)
    output_dir: Path
    manifest_path: Path
    normalized_path: Path
    sqlite_path: Path
    endpoint: str = "https://allie.dbcls.jp/rest/getPairsByAbbr"
    terms_url: str = "https://allie.dbcls.jp/en"
    source_label: str = "ALLIE"
    count_unit: str = "pair-appearance-count"
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    retries: int = Field(default=2, ge=0, le=5)
    max_pairs: int | None = Field(default=None, ge=1)

    def model_post_init(self, __context: object) -> None:
        if not self.keywords or any(not keyword.strip() for keyword in self.keywords):
            raise ValueError("keywords must contain non-empty values")
        if len(set(self.keywords)) != len(self.keywords):
            raise ValueError("keywords must be unique")
        if not self.endpoint.startswith("https://"):
            raise ValueError("ALLIE endpoint must use HTTPS")
        if not self.source_label.strip() or not self.count_unit.strip():
            raise ValueError("source_label and count_unit must be non-empty")


@dataclass(frozen=True, slots=True)
class AlliePair:
    """One source-provided ALLIE pair and its appearance count."""

    pair_id: int
    abbreviation: str
    long_form: str
    appearance_count: int


@dataclass(frozen=True, slots=True)
class AllieAcquisitionResult:
    """Reconciled raw, normalized and T028 query artifacts."""

    manifest_path: Path
    raw_path: Path
    normalized_path: Path
    sqlite_path: Path
    raw_sha256: str
    normalized_sha256: str
    pairs: tuple[AlliePair, ...]
    resource: FrequencyResource

    def to_dict(self) -> dict[str, object]:
        """Return a stable acquisition summary without embedding raw XML."""

        summary = self.resource.summary()
        return {
            "schema_version": ALLIE_ACQUISITION_SCHEMA_VERSION,
            "manifest_path": str(self.manifest_path),
            "raw_path": str(self.raw_path),
            "normalized_path": str(self.normalized_path),
            "sqlite_path": str(self.sqlite_path),
            "raw_sha256": self.raw_sha256,
            "normalized_sha256": self.normalized_sha256,
            "pair_count": len(self.pairs),
            "resource_summary": {
                "variant_count": summary.variant_count,
                "short_form_key_count": summary.short_form_key_count,
                "total_count": summary.total_count,
                "count_unit": summary.count_unit,
            },
        }


def parse_allie_xml(
    payload: bytes, max_pairs: int | None = None
) -> tuple[AlliePair, ...]:
    """Parse ALLIE XML while preserving IDs, variants and appearance counts."""

    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, UnicodeError) as error:
        raise AllieAcquisitionError(f"invalid ALLIE XML: {error}") from error
    pairs: list[AlliePair] = []
    seen_ids: set[int] = set()
    for item in root.findall(".//item"):
        pair_id = _xml_int(item, "pair_id")
        abbreviation = _xml_text(item, "abbreviation")
        long_form = _xml_text(item, "long_form")
        appearance_count = _xml_int(item, "pair_number")
        if pair_id in seen_ids:
            raise AllieAcquisitionError(f"duplicate ALLIE pair_id: {pair_id}")
        seen_ids.add(pair_id)
        if appearance_count < 0:
            raise AllieAcquisitionError("ALLIE appearance counts must be non-negative")
        pairs.append(AlliePair(pair_id, abbreviation, long_form, appearance_count))
        if max_pairs is not None and len(pairs) >= max_pairs:
            break
    if not pairs:
        raise AllieAcquisitionError("ALLIE response contains no pair items")
    return tuple(pairs)


def _xml_text(item: ET.Element, name: str) -> str:
    value = item.findtext(name)
    if value is None or not value.strip():
        raise AllieAcquisitionError(f"ALLIE item lacks non-empty {name}")
    return value.strip()


def _xml_int(item: ET.Element, name: str) -> int:
    value = _xml_text(item, name)
    try:
        return int(value)
    except ValueError as error:
        raise AllieAcquisitionError(f"ALLIE {name} must be an integer") from error


def _transport(url: str, timeout: float, headers: Mapping[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return cast(bytes, response.read())
    except (urllib.error.URLError, OSError) as error:
        raise AllieAcquisitionError(f"ALLIE request failed: {error}") from error


def _normalized_mapping(pairs: tuple[AlliePair, ...]) -> dict[str, dict[str, int]]:
    mapping: dict[str, dict[str, int]] = {}
    for pair in pairs:
        mapping.setdefault(pair.abbreviation, {})[pair.long_form] = (
            pair.appearance_count
        )
    return dict(sorted(mapping.items()))


def load_allie_config(path: Path) -> AllieAcquisitionConfig:
    """Load the ``allie_acquisition`` YAML section."""

    try:
        raw = load_config_layer(path)
        section = raw.get("allie_acquisition")
        if not isinstance(section, Mapping):
            raise AllieAcquisitionError(
                "configuration must contain an 'allie_acquisition' mapping"
            )
        return AllieAcquisitionConfig.model_validate(section)
    except AllieAcquisitionError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise AllieAcquisitionError(f"invalid ALLIE configuration: {error}") from error


def acquire_allie(
    config: AllieAcquisitionConfig,
    transport: AllieTransport | None = None,
) -> AllieAcquisitionResult:
    """Acquire one bounded ALLIE query and import it through T028."""

    request_url = (
        config.endpoint
        + "?"
        + urllib.parse.urlencode([("keywords", keyword) for keyword in config.keywords])
    )
    request_hash = hashlib.sha256(request_url.encode()).hexdigest()[:16]
    raw_path = config.output_dir / f"allie-{request_hash}.xml"
    config.output_dir.mkdir(parents=True, exist_ok=True)
    fetch = transport or _transport
    payload: bytes | None = None
    last_error: Exception | None = None
    for attempt in range(config.retries + 1):
        try:
            if raw_path.is_file():
                payload = raw_path.read_bytes()
            else:
                payload = fetch(
                    request_url,
                    config.timeout_seconds,
                    {"Accept": "application/xml", "User-Agent": "abrex/0.1"},
                )
                temporary = raw_path.with_name(raw_path.name + ".part")
                temporary.write_bytes(payload)
                temporary.replace(raw_path)
            break
        except (AllieAcquisitionError, OSError) as error:
            last_error = error
            if attempt == config.retries:
                break
    if payload is None:
        raise AllieAcquisitionError(f"unable to acquire ALLIE response: {last_error}")
    raw_sha256 = hashlib.sha256(payload).hexdigest()
    pairs = parse_allie_xml(payload, config.max_pairs)
    normalized = _normalized_mapping(pairs)
    temporary_normalized = config.normalized_path.with_name(
        config.normalized_path.name + ".part"
    )
    config.normalized_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(temporary_normalized, "wt", encoding="utf-8") as stream:
        json.dump(normalized, stream, ensure_ascii=False, sort_keys=True)
    if config.normalized_path.exists():
        config.normalized_path.unlink()
    temporary_normalized.replace(config.normalized_path)
    normalized_sha256 = _file_sha256(config.normalized_path)
    resource = import_frequency_resource(
        FrequencyResourceConfig(
            source_path=config.normalized_path,
            sqlite_path=config.sqlite_path,
            source_label=config.source_label,
            count_unit=config.count_unit,
            normalization="identity",
        )
    )
    manifest = {
        "schema_version": ALLIE_ACQUISITION_SCHEMA_VERSION,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "endpoint": config.endpoint,
        "keywords": list(config.keywords),
        "request_url": request_url,
        "raw_path": str(raw_path),
        "raw_sha256": raw_sha256,
        "normalized_path": str(config.normalized_path),
        "normalized_sha256": normalized_sha256,
        "sqlite_path": str(config.sqlite_path),
        "source_label": config.source_label,
        "count_unit": config.count_unit,
        "terms_url": config.terms_url,
        "rights_status": "official_terms_reference; redistribution_not_assumed",
        "extraction_method": "official_allie_rest_xml_to_t028_frequency_json_gzip",
        "lineage": (
            "ALLIE uses ALICE extraction; this is one source family, not an "
            "independent teacher"
        ),
        "pairs": [
            {
                "pair_id": pair.pair_id,
                "abbreviation": pair.abbreviation,
                "long_form": pair.long_form,
                "appearance_count": pair.appearance_count,
            }
            for pair in pairs
        ],
        "resource_summary": {
            "source_label": resource.summary().source_label,
            "source_sha256": resource.summary().source_sha256,
            "variant_count": resource.summary().variant_count,
            "short_form_key_count": resource.summary().short_form_key_count,
            "total_count": resource.summary().total_count,
            "count_unit": resource.summary().count_unit,
        },
    }
    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    config.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return AllieAcquisitionResult(
        config.manifest_path,
        raw_path,
        config.normalized_path,
        config.sqlite_path,
        raw_sha256,
        normalized_sha256,
        pairs,
        resource,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ALLIE_ACQUISITION_SCHEMA_VERSION",
    "AllieAcquisitionConfig",
    "AllieAcquisitionError",
    "AllieAcquisitionResult",
    "AlliePair",
    "acquire_allie",
    "load_allie_config",
    "parse_allie_xml",
]
