"""Streaming gzip frequency-resource ingestion backed by SQLite."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import load_config_layer

RESOURCE_SCHEMA_VERSION = "frequency-resource-v1"


class FrequencyResourceError(RuntimeError):
    """Raised when a frequency resource cannot be imported or queried."""


class FrequencyResourceConfig(BaseModel):
    """Typed boundary for a local aggregate-frequency resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: Path
    sqlite_path: Path
    adapter: str = "frequency-json-gzip"
    source_label: str = "abbr_frequency_2024"
    normalization: str = "identity"
    count_unit: str = "unknown"
    max_entries: int | None = Field(default=None, ge=1)
    chunk_chars: int = Field(default=64 * 1024, ge=1024, le=4 * 1024 * 1024)
    intended_use: str = "aggregate lexical evidence; not gold or document frequency"

    def model_post_init(self, __context: object) -> None:
        if self.adapter != "frequency-json-gzip":
            raise ValueError(f"unsupported resource adapter: {self.adapter}")
        if self.normalization not in {"identity", "casefold"}:
            raise ValueError("normalization must be identity or casefold")
        if not self.source_label.strip() or not self.count_unit.strip():
            raise ValueError("source_label and count_unit must be non-empty")


@dataclass(frozen=True, slots=True)
class ResourceVariant:
    """One raw and normalized SF/LF aggregate entry."""

    short_form_raw: str
    long_form_raw: str
    short_form_key: str
    long_form_key: str
    count: int
    count_unit: str
    source_label: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ResourceSummary:
    """Reconciled aggregate counts with document frequency left unknown."""

    source_label: str
    source_sha256: str
    variant_count: int
    short_form_key_count: int
    total_count: int
    count_unit: str
    document_count: int | None = None


class ResourceQuery(Protocol):
    """Query contract for downstream lexical evidence consumers."""

    def lookup(self, short_form: str) -> tuple[ResourceVariant, ...]: ...

    def summary(self) -> ResourceSummary: ...

    def document_frequency(self, short_form: str) -> int | None: ...


class FrequencyResource:
    """Read-only SQLite view over one imported aggregate resource."""

    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path

    def lookup(self, short_form: str) -> tuple[ResourceVariant, ...]:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            normalization = connection.execute(
                "SELECT value FROM metadata WHERE key = 'normalization'"
            ).fetchone()
            policy = normalization[0] if normalization else "identity"
            rows = connection.execute(
                "SELECT sf_raw, lf_raw, sf_key, lf_key, count, count_unit, "
                "source_label, source_sha256 "
                "FROM variants WHERE sf_key = ? ORDER BY rowid",
                (_normalize(short_form, policy),),
            ).fetchall()
        finally:
            connection.close()
        return tuple(ResourceVariant(*row) for row in rows)

    def summary(self) -> ResourceSummary:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            row = connection.execute(
                "SELECT source_label, source_sha256, COUNT(*), COUNT(DISTINCT sf_key), "
                "COALESCE(SUM(count), 0), count_unit FROM variants"
            ).fetchone()
        finally:
            connection.close()
        if row is None or row[0] is None:
            raise FrequencyResourceError("resource database has no metadata")
        return ResourceSummary(*row)

    def document_frequency(self, short_form: str) -> int | None:
        del short_form
        return None


def load_frequency_config(path: Path) -> FrequencyResourceConfig:
    """Load the ``frequency_resource`` YAML section."""

    raw = load_config_layer(path)
    section = raw.get("frequency_resource")
    if not isinstance(section, Mapping):
        raise FrequencyResourceError(f"Configuration {path} lacks frequency_resource")
    try:
        return FrequencyResourceConfig.model_validate(section)
    except ValueError as error:
        raise FrequencyResourceError(
            f"Invalid frequency resource config: {error}"
        ) from error


def import_frequency_resource(config: FrequencyResourceConfig) -> FrequencyResource:
    """Stream a gzip JSON object into a fresh SQLite database."""

    if not config.source_path.is_file():
        raise FrequencyResourceError(
            f"source file does not exist: {config.source_path}"
        )
    source_sha256 = _file_sha256(config.source_path)
    config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.sqlite_path.with_name(config.sqlite_path.name + ".part")
    if temporary.exists():
        temporary.unlink()
    try:
        connection = sqlite3.connect(temporary)
        try:
            _create_schema(connection, config, source_sha256)
            entries = 0
            with gzip.open(config.source_path, "rt", encoding="utf-8") as stream:
                for short_form, long_form, count in _iter_frequency_entries(
                    stream, config.chunk_chars
                ):
                    connection.execute(
                        "INSERT INTO variants VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            short_form,
                            long_form,
                            _normalize(short_form, config.normalization),
                            _normalize(long_form, config.normalization),
                            count,
                            config.count_unit,
                            config.source_label,
                            source_sha256,
                        ),
                    )
                    entries += 1
                    if config.max_entries is not None and entries >= config.max_entries:
                        break
            connection.commit()
        finally:
            connection.close()
        temporary.replace(config.sqlite_path)
    except (
        OSError,
        EOFError,
        json.JSONDecodeError,
        sqlite3.Error,
        ValueError,
    ) as error:
        raise FrequencyResourceError(
            f"unable to import frequency resource: {error}"
        ) from error
    return FrequencyResource(config.sqlite_path)


def _iter_frequency_entries(
    stream: TextIO, chunk_chars: int
) -> Iterator[tuple[str, str, int]]:
    reader = _JsonStream(stream, chunk_chars)
    reader.expect("{")
    if reader.peek("}"):
        reader.expect("}")
        return
    while True:
        short_form = reader.value()
        if not isinstance(short_form, str):
            raise ValueError("short-form key must be a string")
        reader.expect(":")
        reader.expect("{")
        if not reader.peek("}"):
            while True:
                long_form = reader.value()
                if not isinstance(long_form, str):
                    raise ValueError("long-form key must be a string")
                reader.expect(":")
                count = reader.value()
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    raise ValueError("frequency count must be a non-negative integer")
                yield short_form, long_form, count
                if reader.peek(","):
                    reader.expect(",")
                    continue
                reader.expect("}")
                break
        else:
            reader.expect("}")
        if reader.peek(","):
            reader.expect(",")
            continue
        reader.expect("}")
        break


class _JsonStream:
    def __init__(self, stream: TextIO, chunk_chars: int) -> None:
        self.stream = stream
        self.chunk_chars = chunk_chars
        self.buffer = ""
        self.position = 0
        self.decoder = json.JSONDecoder()

    def _fill(self) -> None:
        chunk = self.stream.read(self.chunk_chars)
        if chunk:
            self.buffer += chunk

    def _skip(self) -> None:
        while True:
            while (
                self.position < len(self.buffer)
                and self.buffer[self.position].isspace()
            ):
                self.position += 1
            if self.position < len(self.buffer) or not self.stream.readable():
                return
            self._fill()

    def peek(self, value: str) -> bool:
        self._skip()
        while self.position + len(value) > len(self.buffer):
            before = len(self.buffer)
            self._fill()
            if len(self.buffer) == before:
                break
        return self.buffer[self.position : self.position + len(value)] == value

    def expect(self, value: str) -> None:
        if not self.peek(value):
            raise ValueError(f"expected {value!r} at character {self.position}")
        self.position += len(value)
        self._compact()

    def value(self) -> object:
        self._skip()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                before = len(self.buffer)
                self._fill()
                if len(self.buffer) == before:
                    raise
            else:
                self.position = end
                self._compact()
                return value

    def _compact(self) -> None:
        if self.position >= self.chunk_chars:
            self.buffer = self.buffer[self.position :]
            self.position = 0


def _create_schema(
    connection: sqlite3.Connection, config: FrequencyResourceConfig, source_sha256: str
) -> None:
    connection.execute(
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE variants (sf_raw TEXT, lf_raw TEXT, sf_key TEXT, lf_key TEXT, "
        "count INTEGER, "
        "count_unit TEXT, source_label TEXT, source_sha256 TEXT)"
    )
    metadata = {
        "schema_version": RESOURCE_SCHEMA_VERSION,
        "source_label": config.source_label,
        "source_sha256": source_sha256,
        "normalization": config.normalization,
        "count_unit": config.count_unit,
        "intended_use": config.intended_use,
    }
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())


def _normalize(value: str, policy: str) -> str:
    return value.casefold() if policy == "casefold" else value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "FrequencyResource",
    "FrequencyResourceConfig",
    "FrequencyResourceError",
    "ResourceQuery",
    "ResourceSummary",
    "ResourceVariant",
    "import_frequency_resource",
    "load_frequency_config",
]
