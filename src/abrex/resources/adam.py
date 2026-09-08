"""Bounded local import of the official ADAM tab-separated tar member."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import load_config_layer
from abrex.resources.frequency import (
    FrequencyResource,
    FrequencyResourceConfig,
    import_frequency_resource,
)

ADAM_ACQUISITION_SCHEMA_VERSION = "adam-acquisition-v1"


class AdamAcquisitionError(RuntimeError):
    """Raised when an ADAM archive or record cannot be reconciled."""


class AdamImportConfig(BaseModel):
    """Typed boundary for importing one official ADAM archive locally."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tar_path: Path
    readme_path: Path | None = None
    manifest_path: Path
    normalized_path: Path
    sqlite_path: Path
    source_label: str = "ADAM"
    count_unit: str = "definition-count"
    max_records: int = Field(default=64, ge=1)

    def model_post_init(self, __context: object) -> None:
        if not self.source_label.strip() or not self.count_unit.strip():
            raise ValueError("source_label and count_unit must be non-empty")


@dataclass(frozen=True, slots=True)
class AdamLongFormVariant:
    """ADAM long-form variant with source-provided count and score."""

    long_form: str
    count: int
    score: float


@dataclass(frozen=True, slots=True)
class AdamRecord:
    """One ADAM row, retaining preferred and morphological variants."""

    preferred_abbreviation: str
    abbreviation_variants: tuple[str, ...]
    long_form_variants: tuple[AdamLongFormVariant, ...]
    phrase_score: float
    definition_count: int


@dataclass(frozen=True, slots=True)
class AdamImportResult:
    """Imported ADAM artifacts and source reconciliation counts."""

    manifest_path: Path
    normalized_path: Path
    sqlite_path: Path
    tar_sha256: str
    readme_sha256: str | None
    parsed_records: int
    imported_records: int
    malformed_records: int
    resource: FrequencyResource

    def to_dict(self) -> dict[str, object]:
        """Return a concise summary without embedding the archive."""

        summary = self.resource.summary()
        return {
            "schema_version": ADAM_ACQUISITION_SCHEMA_VERSION,
            "manifest_path": str(self.manifest_path),
            "normalized_path": str(self.normalized_path),
            "sqlite_path": str(self.sqlite_path),
            "tar_sha256": self.tar_sha256,
            "readme_sha256": self.readme_sha256,
            "parsed_records": self.parsed_records,
            "imported_records": self.imported_records,
            "malformed_records": self.malformed_records,
            "resource_summary": {
                "variant_count": summary.variant_count,
                "short_form_key_count": summary.short_form_key_count,
                "total_count": summary.total_count,
                "count_unit": summary.count_unit,
            },
        }


def parse_adam_line(line: str) -> AdamRecord:
    """Parse one five-column ADAM data row."""

    columns = line.rstrip("\r\n").split("\t")
    if len(columns) != 5:
        raise AdamAcquisitionError("ADAM row must contain five tab-separated columns")
    preferred, raw_abbreviations, raw_long_forms, raw_score, raw_count = columns
    if not preferred.strip():
        raise AdamAcquisitionError("ADAM preferred abbreviation is empty")
    abbreviation_variants = tuple(
        sorted(
            {
                token.rsplit(":", 1)[0]
                for token in raw_abbreviations.split("|")
                if token.strip()
            }
        )
    )
    long_form_variants: list[AdamLongFormVariant] = []
    for token in raw_long_forms.split("|"):
        fields = token.rsplit(":", 2)
        if len(fields) != 3 or not fields[0].strip():
            raise AdamAcquisitionError(
                "ADAM long-form variant must contain text/count/score"
            )
        try:
            count = int(fields[1])
            score = float(fields[2])
        except ValueError as error:
            raise AdamAcquisitionError(
                "ADAM variant count and score must be numeric"
            ) from error
        if count < 0:
            raise AdamAcquisitionError("ADAM variant counts must be non-negative")
        if not 0.0 <= score <= 1.0:
            raise AdamAcquisitionError("ADAM variant scores must be between 0 and 1")
        long_form_variants.append(AdamLongFormVariant(fields[0].strip(), count, score))
    try:
        phrase_score = float(raw_score)
        definition_count = int(raw_count)
    except ValueError as error:
        raise AdamAcquisitionError(
            "ADAM phrase score and count must be numeric"
        ) from error
    if definition_count < 0:
        raise AdamAcquisitionError("ADAM definition counts must be non-negative")
    return AdamRecord(
        preferred.strip(),
        abbreviation_variants,
        tuple(long_form_variants),
        phrase_score,
        definition_count,
    )


def _iter_adam_rows(stream: TextIO) -> Iterator[str]:
    for line in stream:
        if line.strip() and not line.lstrip().startswith("#"):
            yield line


def _normalized_mapping(records: Iterator[AdamRecord]) -> dict[str, dict[str, int]]:
    mapping: dict[str, dict[str, int]] = {}
    for record in records:
        target = mapping.setdefault(record.preferred_abbreviation, {})
        for variant in record.long_form_variants:
            target[variant.long_form] = target.get(variant.long_form, 0) + variant.count
    return dict(sorted(mapping.items()))


def load_adam_config(path: Path) -> AdamImportConfig:
    """Load the ``adam_import`` YAML section."""

    try:
        raw = load_config_layer(path)
        section = raw.get("adam_import")
        if not isinstance(section, Mapping):
            raise AdamAcquisitionError(
                "configuration must contain an 'adam_import' mapping"
            )
        return AdamImportConfig.model_validate(section)
    except AdamAcquisitionError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise AdamAcquisitionError(f"invalid ADAM configuration: {error}") from error


def import_adam(config: AdamImportConfig) -> AdamImportResult:
    """Import a bounded ADAM prefix and reconcile the complete local row stream."""

    if not config.tar_path.is_file():
        raise AdamAcquisitionError(f"ADAM archive does not exist: {config.tar_path}")
    tar_sha256 = _file_sha256(config.tar_path)
    readme_sha256 = (
        _file_sha256(config.readme_path)
        if config.readme_path and config.readme_path.is_file()
        else None
    )
    imported: list[AdamRecord] = []
    parsed_records = 0
    malformed_records = 0
    try:
        with tarfile.open(config.tar_path, mode="r:") as archive:
            try:
                member = archive.extractfile("adam_database")
            except KeyError as error:
                raise AdamAcquisitionError(
                    "ADAM archive lacks adam_database member"
                ) from error
            if member is None:
                raise AdamAcquisitionError("ADAM archive lacks adam_database member")
            text = io.TextIOWrapper(member, encoding="utf-8")
            try:
                for line in _iter_adam_rows(text):
                    try:
                        record = parse_adam_line(line)
                    except AdamAcquisitionError:
                        malformed_records += 1
                        continue
                    parsed_records += 1
                    if len(imported) < config.max_records:
                        imported.append(record)
            finally:
                text.detach()
    except (OSError, tarfile.TarError, UnicodeError) as error:
        raise AdamAcquisitionError(f"unable to read ADAM archive: {error}") from error
    if not imported:
        raise AdamAcquisitionError("ADAM archive yielded no valid records")
    config.normalized_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.normalized_path.with_name(config.normalized_path.name + ".part")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump(
            _normalized_mapping(iter(imported)),
            stream,
            ensure_ascii=False,
            sort_keys=True,
        )
    if config.normalized_path.exists():
        config.normalized_path.unlink()
    temporary.replace(config.normalized_path)
    resource = import_frequency_resource(
        FrequencyResourceConfig(
            source_path=config.normalized_path,
            sqlite_path=config.sqlite_path,
            source_label=config.source_label,
            count_unit=config.count_unit,
        )
    )
    manifest = {
        "schema_version": ADAM_ACQUISITION_SCHEMA_VERSION,
        "source_path": str(config.tar_path),
        "readme_path": str(config.readme_path) if config.readme_path else None,
        "tar_sha256": tar_sha256,
        "readme_sha256": readme_sha256,
        "archive_member": "adam_database",
        "parsed_records": parsed_records,
        "imported_records": len(imported),
        "malformed_records": malformed_records,
        "max_records": config.max_records,
        "source_label": config.source_label,
        "count_unit": config.count_unit,
        "normalization": "identity; preferred abbreviation retained",
        "variant_semantics": (
            "ADAM abbreviation and long-form variants retained; long-form counts "
            "are variant counts"
        ),
        "terms": (
            "README states non-commercial/no-redistribution and also names GPL; "
            "legal review required"
        ),
        "lineage": "ADAM generated from the 2006 MEDLINE baseline",
        "normalized_path": str(config.normalized_path),
        "sqlite_path": str(config.sqlite_path),
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
    return AdamImportResult(
        config.manifest_path,
        config.normalized_path,
        config.sqlite_path,
        tar_sha256,
        readme_sha256,
        parsed_records,
        len(imported),
        malformed_records,
        resource,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ADAM_ACQUISITION_SCHEMA_VERSION",
    "AdamAcquisitionError",
    "AdamImportConfig",
    "AdamImportResult",
    "AdamLongFormVariant",
    "AdamRecord",
    "import_adam",
    "load_adam_config",
    "parse_adam_line",
]
