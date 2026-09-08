"""The optional external Ab3P baseline and its format-independent parser."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    TextSpan,
)

AB3P_ADAPTER_VERSION = "3"
AB3P_WRAPPER_VERSION = "2"
AB3P_OFFSET_SCHEMA_VERSION = "ab3p-offsets-v1"
Ab3POutputFormat = Literal["text", "offset_jsonl"]


class Ab3PParseError(ValueError):
    """Ab3P output is malformed or cannot be interpreted safely."""


class Ab3PMappingError(ValueError):
    """An Ab3P pair cannot be mapped unambiguously to canonical offsets."""


@dataclass(frozen=True, slots=True)
class ParsedAbbreviation:
    """One pair captured from an Ab3P frontend.

    The optional fields are populated only by the native offset frontend.
    Legacy text-only parsing deliberately leaves them unset so callers cannot
    accidentally treat guessed offsets as native evidence.
    """

    short_form: str
    long_form: str
    precision: float
    line_index: int | None = None
    line_start_byte: int | None = None
    line_byte_length: int | None = None
    sf_offset: int | None = None
    lf_offset: int | None = None
    strategy: str | None = None


def build_ab3p_input(document: Document) -> str:
    """Return the exact UTF-8 text payload supplied to Ab3P.

    Ab3P consumes a text file one line at a time.  ABREX deliberately makes no
    text normalization; the canonical document text is the payload verbatim.
    """

    if not isinstance(document, Document):
        raise TypeError("document must be a Document")
    return document.text


def parse_ab3p_output(output: str) -> tuple[ParsedAbbreviation, ...]:
    """Parse captured Ab3P stdout without invoking or consulting infrastructure."""

    if not isinstance(output, str):
        raise TypeError("output must be a string")
    parsed: list[ParsedAbbreviation] = []
    for line_number, line in enumerate(output.splitlines(), start=1):
        if not line[:1].isspace():
            continue  # The first line is Ab3P's echoed input.
        fields = line.strip().split("|")
        if len(fields) != 3:
            if line.strip():
                raise Ab3PParseError(f"Malformed Ab3P pair at line {line_number}")
            continue
        short_form, long_form, raw_precision = (field.strip() for field in fields)
        if not short_form or not long_form:
            raise Ab3PParseError(f"Empty Ab3P form at line {line_number}")
        try:
            precision = float(raw_precision)
        except ValueError as error:
            raise Ab3PParseError(
                f"Invalid Ab3P precision at line {line_number}: {raw_precision!r}"
            ) from error
        if not 0 <= precision <= 1:
            raise Ab3PParseError(f"Ab3P precision out of range at line {line_number}")
        parsed.append(ParsedAbbreviation(short_form, long_form, precision))
    return tuple(parsed)


def parse_ab3p_offset_output(output: str) -> tuple[ParsedAbbreviation, ...]:
    """Parse versioned JSONL emitted by the native offset frontend."""

    if not isinstance(output, str):
        raise TypeError("output must be a string")
    parsed: list[ParsedAbbreviation] = []
    for line_number, line in enumerate(output.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise Ab3PParseError(
                f"Malformed native Ab3P JSON at line {line_number}: {error.msg}"
            ) from error
        if not isinstance(raw, dict):
            raise Ab3PParseError(
                f"Native Ab3P record at line {line_number} must be an object"
            )
        if raw.get("schema_version") != AB3P_OFFSET_SCHEMA_VERSION:
            raise Ab3PParseError(
                f"Unsupported native Ab3P schema at line {line_number}: "
                f"{raw.get('schema_version')!r}"
            )
        try:
            short_form = _native_string(raw, "short_form")
            long_form = _native_string(raw, "long_form")
            precision = _native_number(raw, "precision")
            line_index = _native_nonnegative_int(raw, "line_index")
            line_start_byte = _native_nonnegative_int(raw, "line_start_byte")
            line_byte_length = _native_nonnegative_int(raw, "line_byte_length")
            sf_offset = _native_nonnegative_int(raw, "sf_offset")
            lf_offset = _native_nonnegative_int(raw, "lf_offset")
            strategy = _native_optional_string(raw, "strategy")
        except (KeyError, TypeError, ValueError) as error:
            raise Ab3PParseError(
                f"Invalid native Ab3P record at line {line_number}: {error}"
            ) from error
        if not short_form or not long_form:
            raise Ab3PParseError(f"Empty native Ab3P form at line {line_number}")
        if not math.isfinite(precision) or not 0 <= precision <= 1:
            raise Ab3PParseError(
                f"Native Ab3P precision out of range at line {line_number}"
            )
        parsed.append(
            ParsedAbbreviation(
                short_form=short_form,
                long_form=long_form,
                precision=precision,
                line_index=line_index,
                line_start_byte=line_start_byte,
                line_byte_length=line_byte_length,
                sf_offset=sf_offset,
                lf_offset=lf_offset,
                strategy=strategy,
            )
        )
    return tuple(parsed)


def reconstruct_predictions(
    document: Document, parsed: Iterable[ParsedAbbreviation]
) -> tuple[AbbreviationDefinition, ...]:
    """Map parsed forms to canonical spans, rejecting unjustified ambiguity."""

    predictions: list[AbbreviationDefinition] = []
    for pair in parsed:
        short_positions = _occurrences(document.text, pair.short_form)
        long_positions = _occurrences(document.text, pair.long_form)
        candidates = [
            (long_start, short_start)
            for long_start in long_positions
            for short_start in short_positions
            if long_start + len(pair.long_form) <= short_start
        ]
        if len(candidates) != 1:
            reason = "not found" if not candidates else "ambiguous"
            raise Ab3PMappingError(
                f"Unable to reconstruct {pair.short_form!r}/{pair.long_form!r} "
                f"in {document.document_id!r}: {reason}"
            )
        long_start, short_start = candidates[0]
        predictions.append(
            AbbreviationDefinition(
                document_id=document.document_id,
                short_form=TextSpan(short_start, short_start + len(pair.short_form)),
                long_form=TextSpan(long_start, long_start + len(pair.long_form)),
                short_form_text=pair.short_form,
                long_form_text=pair.long_form,
                prediction=PredictionMetadata(score=pair.precision),
            )
        )
    return tuple(predictions)


def reconstruct_offset_predictions(
    document: Document, parsed: Iterable[ParsedAbbreviation]
) -> tuple[AbbreviationDefinition, ...]:
    """Map verified Ab3P byte offsets to canonical Python character spans.

    Ab3P's native offsets are byte offsets into the exact UTF-8 bytes of the
    individual ``getline`` line.  This function rejects stale line identity,
    non-boundary UTF-8 offsets, out-of-range coordinates, and any result whose
    canonical slice is not exactly the reported form.  It never searches for
    another occurrence of either form.
    """

    lines = document.text.split("\n")
    line_starts: list[int] = []
    line_char_starts: list[int] = []
    byte_position = 0
    char_position = 0
    for line in lines:
        line_starts.append(byte_position)
        line_char_starts.append(char_position)
        byte_position += len(line.encode("utf-8")) + 1
        char_position += len(line) + 1

    predictions: list[AbbreviationDefinition] = []
    for pair in parsed:
        native_fields = (
            pair.line_index,
            pair.line_start_byte,
            pair.line_byte_length,
            pair.sf_offset,
            pair.lf_offset,
        )
        if any(value is None for value in native_fields):
            raise Ab3PMappingError(
                f"Native offsets are missing for {pair.short_form!r}/"
                f"{pair.long_form!r} in {document.document_id!r}"
            )
        assert pair.line_index is not None
        assert pair.line_start_byte is not None
        assert pair.line_byte_length is not None
        assert pair.sf_offset is not None
        assert pair.lf_offset is not None
        if pair.line_index >= len(lines):
            raise Ab3PMappingError(
                f"Native Ab3P line index {pair.line_index} is outside "
                f"{document.document_id!r}"
            )
        line = lines[pair.line_index]
        line_bytes = line.encode("utf-8")
        expected_start = line_starts[pair.line_index]
        if pair.line_start_byte != expected_start:
            raise Ab3PMappingError(
                f"Native Ab3P line origin mismatch for line {pair.line_index}: "
                f"reported {pair.line_start_byte}, expected {expected_start}"
            )
        if pair.line_byte_length != len(line_bytes):
            raise Ab3PMappingError(
                f"Native Ab3P line byte length mismatch for line {pair.line_index}: "
                f"reported {pair.line_byte_length}, expected {len(line_bytes)}"
            )
        expected_char_start = line_char_starts[pair.line_index]
        short_span = _native_byte_span(
            line,
            pair.sf_offset,
            len(pair.short_form.encode("utf-8")),
            form="short",
        )
        long_span = _native_byte_span(
            line,
            pair.lf_offset,
            len(pair.long_form.encode("utf-8")),
            form="long",
        )
        if line[short_span.start : short_span.end] != pair.short_form:
            raise Ab3PMappingError(
                f"Native Ab3P short offset for {pair.short_form!r} does not "
                f"slice to the reported form in line {pair.line_index}"
            )
        if line[long_span.start : long_span.end] != pair.long_form:
            raise Ab3PMappingError(
                f"Native Ab3P long offset for {pair.long_form!r} does not "
                f"slice to the reported form in line {pair.line_index}"
            )
        notes = [
            f"native_ab3p_line_index={pair.line_index}",
            f"native_ab3p_line_start_byte={pair.line_start_byte}",
            f"native_ab3p_sf_offset={pair.sf_offset}",
            f"native_ab3p_lf_offset={pair.lf_offset}",
        ]
        if pair.strategy is not None:
            notes.append(f"native_ab3p_strategy={pair.strategy}")
        predictions.append(
            AbbreviationDefinition(
                document_id=document.document_id,
                short_form=TextSpan(
                    expected_char_start + short_span.start,
                    expected_char_start + short_span.end,
                ),
                long_form=TextSpan(
                    expected_char_start + long_span.start,
                    expected_char_start + long_span.end,
                ),
                short_form_text=pair.short_form,
                long_form_text=pair.long_form,
                provenance=AnnotationProvenance(
                    adapter_identity="ab3p-native-offsets",
                    adapter_version=AB3P_ADAPTER_VERSION,
                    transformation_notes=tuple(notes),
                ),
                prediction=PredictionMetadata(score=pair.precision),
            )
        )
    return tuple(predictions)


def _native_byte_span(
    line: str, start_byte: int, length_bytes: int, *, form: str
) -> TextSpan:
    if start_byte < 0 or length_bytes < 0:
        raise Ab3PMappingError(
            f"Native Ab3P {form} offset must be non-negative: "
            f"[{start_byte}, {start_byte + length_bytes})"
        )
    line_bytes = line.encode("utf-8")
    end_byte = start_byte + length_bytes
    if end_byte > len(line_bytes):
        raise Ab3PMappingError(
            f"Native Ab3P {form} offset [{start_byte}, {end_byte}) exceeds "
            f"line byte length {len(line_bytes)}"
        )
    try:
        start = len(line_bytes[:start_byte].decode("utf-8"))
        end = len(line_bytes[:end_byte].decode("utf-8"))
    except UnicodeDecodeError as error:
        raise Ab3PMappingError(
            f"Native Ab3P {form} offset is not on a UTF-8 boundary: "
            f"[{start_byte}, {end_byte})"
        ) from error
    return TextSpan(start, end)


def _native_string(data: dict[str, object], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _native_optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{key} must be a string or null")
    return value


def _native_nonnegative_int(data: dict[str, object], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _native_number(data: dict[str, object], key: str) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{key} must be a number")
    return float(value)


def _occurrences(text: str, needle: str) -> tuple[int, ...]:
    return tuple(match.start() for match in re.finditer(re.escape(needle), text))


class Ab3PCacheConfig(BaseModel):
    """Portable cache settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    read: bool = True
    write: bool = False


class Ab3PInstallationConfig(BaseModel):
    """T018 installation manifest and paths for the supplied Ab3P build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: str = Field(min_length=1)
    root: str | None = None
    executable: str = Field(default="identify_abbr", min_length=1)
    resource_directory: str = Field(default="WordData", min_length=1)


class Ab3PResolverConfig(BaseModel):
    """Typed YAML parameters for the Ab3P resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = "cache_only"
    output_format: Ab3POutputFormat = "text"
    executable: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)
    cache: Ab3PCacheConfig | None = None
    installation: Ab3PInstallationConfig | None = None
    installation_label: str | None = None
    executable_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")

    @model_validator(mode="after")
    def validate_backend(self) -> Ab3PResolverConfig:
        if self.backend not in ("cache_only", "subprocess", "cache_then_subprocess"):
            raise ValueError(f"Unsupported Ab3P backend: {self.backend!r}")
        if (
            self.backend in ("subprocess", "cache_then_subprocess")
            and not self.executable
            and self.installation is None
        ):
            raise ValueError(f"Ab3P backend {self.backend!r} requires executable")
        if (
            self.backend in ("cache_only", "cache_then_subprocess")
            and self.cache is None
        ):
            raise ValueError(f"Ab3P backend {self.backend!r} requires cache settings")
        if self.backend == "cache_only" and not (
            self.installation or self.executable_sha256
        ):
            raise ValueError(
                "Ab3P cache_only requires a T018 installation manifest or "
                "executable_sha256; installation_label alone is not cache identity"
            )
        if self.output_format not in ("text", "offset_jsonl"):
            raise ValueError(f"Unsupported Ab3P output format: {self.output_format!r}")
        return self


__all__ = [
    "AB3P_ADAPTER_VERSION",
    "AB3P_OFFSET_SCHEMA_VERSION",
    "AB3P_WRAPPER_VERSION",
    "Ab3PCacheConfig",
    "Ab3PInstallationConfig",
    "Ab3PMappingError",
    "Ab3PParseError",
    "Ab3PResolverConfig",
    "ParsedAbbreviation",
    "Ab3POutputFormat",
    "build_ab3p_input",
    "parse_ab3p_output",
    "parse_ab3p_offset_output",
    "reconstruct_offset_predictions",
    "reconstruct_predictions",
]
