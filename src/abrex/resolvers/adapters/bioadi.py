"""Typed BioADI resolver adapter over the optional WSL Java runtime."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    TextSpan,
)

BIOADI_ADAPTER_VERSION = "1"
BioADIMappingPolicy = Literal["strict_unique", "ordered_occurrence"]


class BioADIParseError(ValueError):
    """BioADI stdout contains a malformed pair row."""


class BioADIMappingError(ValueError):
    """BioADI labels cannot be mapped to safe canonical offsets."""


class BioADIResolverConfig(BaseModel):
    """Explicit Java, artifact and offset-mapping configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jar_path: Path
    java_path: str = "/home/rleaman/.local/share/abrex/java8/jdk8u504-b01/bin/java"
    jar_sha256: str = Field(min_length=64, max_length=64)
    java_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    timeout_seconds: int = Field(default=30, ge=1)
    heap_mb: int = Field(default=512, ge=128)
    mapping_policy: BioADIMappingPolicy = "ordered_occurrence"


@dataclass(frozen=True, slots=True)
class BioADIPair:
    short_form: str
    long_form: str
    score: float


def parse_bioadi_output(output: str) -> tuple[BioADIPair, ...]:
    """Parse BioADI's human-readable rows while ignoring echoed input lines."""

    if not isinstance(output, str):
        raise TypeError("BioADI output must be a string")
    parsed: list[BioADIPair] = []
    for line_number, line in enumerate(output.splitlines(), start=1):
        if not line[:1].isspace():
            continue
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        fields = [field.strip() for field in stripped.split("|")]
        if len(fields) != 3:
            raise BioADIParseError(f"Malformed BioADI pair at line {line_number}")
        short_form, long_form, raw_score = fields
        if not short_form or not long_form:
            raise BioADIParseError(f"Empty BioADI form at line {line_number}")
        try:
            score = float(raw_score)
        except ValueError as error:
            raise BioADIParseError(
                f"Invalid BioADI score at line {line_number}: {raw_score!r}"
            ) from error
        if not 0 <= score <= 1:
            raise BioADIParseError(f"BioADI score out of range at line {line_number}")
        parsed.append(BioADIPair(short_form, long_form, score))
    return tuple(parsed)


def _occurrences(text: str, value: str) -> tuple[int, ...]:
    positions: list[int] = []
    cursor = 0
    while True:
        position = text.find(value, cursor)
        if position < 0:
            return tuple(positions)
        positions.append(position)
        cursor = position + max(len(value), 1)


def reconstruct_bioadi_predictions(
    document: Document,
    pairs: Iterable[BioADIPair],
    *,
    mapping_policy: BioADIMappingPolicy = "ordered_occurrence",
) -> tuple[AbbreviationDefinition, ...]:
    """Map exact forms only when occurrence cardinality makes the mapping explicit."""

    parsed = tuple(pairs)
    grouped: dict[tuple[str, str], list[BioADIPair]] = defaultdict(list)
    for pair in parsed:
        grouped[(pair.short_form, pair.long_form)].append(pair)
    offsets: dict[tuple[str, str], tuple[tuple[int, int], ...]] = {}
    for key, group in grouped.items():
        short_form, long_form = key
        short_positions = _occurrences(document.text, short_form)
        long_positions = _occurrences(document.text, long_form)
        if mapping_policy == "strict_unique":
            if len(short_positions) != 1 or len(long_positions) != 1:
                raise BioADIMappingError(
                    f"BioADI mapping is not unique for {short_form!r}/{long_form!r} "
                    f"in {document.document_id!r}"
                )
            offsets[key] = ((long_positions[0], short_positions[0]),)
        elif mapping_policy == "ordered_occurrence":
            if len(group) != len(short_positions) or len(group) != len(long_positions):
                raise BioADIMappingError(
                    f"BioADI occurrence count does not reconcile for "
                    f"{short_form!r}/{long_form!r} in {document.document_id!r}: "
                    f"rows={len(group)}, short={len(short_positions)}, "
                    f"long={len(long_positions)}"
                )
            offsets[key] = tuple(zip(long_positions, short_positions, strict=True))
        else:
            raise ValueError(f"Unsupported BioADI mapping policy: {mapping_policy!r}")
        if any(
            long_start + len(long_form) > short_start
            for long_start, short_start in offsets[key]
        ):
            raise BioADIMappingError(
                "BioADI forms are not ordered as long-before-short in "
                f"{document.document_id!r}"
            )
    cursors: dict[tuple[str, str], int] = defaultdict(int)
    predictions: list[AbbreviationDefinition] = []
    for pair in parsed:
        key = (pair.short_form, pair.long_form)
        index = cursors[key]
        try:
            long_start, short_start = offsets[key][index]
        except IndexError as error:
            raise BioADIMappingError(
                f"BioADI mapping has no remaining occurrence for {key!r}"
            ) from error
        cursors[key] += 1
        predictions.append(
            AbbreviationDefinition(
                document_id=document.document_id,
                short_form=TextSpan(short_start, short_start + len(pair.short_form)),
                long_form=TextSpan(long_start, long_start + len(pair.long_form)),
                short_form_text=pair.short_form,
                long_form_text=pair.long_form,
                provenance=AnnotationProvenance(
                    adapter_identity="bioadi",
                    adapter_version=BIOADI_ADAPTER_VERSION,
                    transformation_notes=(
                        f"mapping_policy={mapping_policy}",
                        "source_offsets=not_reported; exact_occurrence_mapping=true",
                    ),
                ),
                prediction=PredictionMetadata(score=pair.score),
            )
        )
    return tuple(predictions)


class BioADIResolver:
    """Execute BioADI's explicit ``aiiaadi.util.Executor`` entry point."""

    identity = "bioadi"
    version = BIOADI_ADAPTER_VERSION

    def __init__(self, **params: object) -> None:
        self.config = BioADIResolverConfig.model_validate(params)

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Run BioADI and return only safely reconstructed canonical predictions."""

        from abrex.infrastructure.bioadi import run_bioadi

        result = run_bioadi(document, self.config)
        if result.timed_out:
            raise RuntimeError(f"BioADI timed out for {document.document_id!r}")
        if result.exit_status != 0:
            raise RuntimeError(
                f"BioADI exited with status {result.exit_status} for "
                f"{document.document_id!r}: {result.stderr.strip()}"
            )
        pairs = parse_bioadi_output(result.stdout)
        return reconstruct_bioadi_predictions(
            document, pairs, mapping_policy=self.config.mapping_policy
        )

    @property
    def cache_identity(self) -> dict[str, str]:
        """Return artifact and mapping identity used by experiment caches."""

        from abrex.infrastructure.bioadi import bioadi_identity

        return bioadi_identity(self.config)


__all__ = [
    "BIOADI_ADAPTER_VERSION",
    "BioADIMappingError",
    "BioADIPair",
    "BioADIParseError",
    "BioADIResolver",
    "BioADIResolverConfig",
    "parse_bioadi_output",
    "reconstruct_bioadi_predictions",
]
