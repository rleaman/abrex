"""The optional external Ab3P baseline and its format-independent parser."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.domain import AbbreviationDefinition, Document, PredictionMetadata, TextSpan

AB3P_ADAPTER_VERSION = "1"


class Ab3PParseError(ValueError):
    """Ab3P output is malformed or cannot be interpreted safely."""


class Ab3PMappingError(ValueError):
    """An Ab3P pair cannot be mapped unambiguously to canonical offsets."""


@dataclass(frozen=True, slots=True)
class ParsedAbbreviation:
    """One pair captured from Ab3P's ``sf|lf|precision`` output."""

    short_form: str
    long_form: str
    precision: float


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


def _occurrences(text: str, needle: str) -> tuple[int, ...]:
    return tuple(match.start() for match in re.finditer(re.escape(needle), text))


class Ab3PCacheConfig(BaseModel):
    """Portable cache settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    read: bool = True
    write: bool = False


class Ab3PResolverConfig(BaseModel):
    """Typed YAML parameters for the Ab3P resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = "cache_only"
    executable: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)
    cache: Ab3PCacheConfig | None = None
    installation_label: str | None = None

    @model_validator(mode="after")
    def validate_backend(self) -> Ab3PResolverConfig:
        if self.backend not in ("cache_only", "subprocess", "cache_then_subprocess"):
            raise ValueError(f"Unsupported Ab3P backend: {self.backend!r}")
        if (
            self.backend in ("subprocess", "cache_then_subprocess")
            and not self.executable
        ):
            raise ValueError(f"Ab3P backend {self.backend!r} requires executable")
        if (
            self.backend in ("cache_only", "cache_then_subprocess")
            and self.cache is None
        ):
            raise ValueError(f"Ab3P backend {self.backend!r} requires cache settings")
        return self


__all__ = [
    "AB3P_ADAPTER_VERSION",
    "Ab3PCacheConfig",
    "Ab3PMappingError",
    "Ab3PParseError",
    "Ab3PResolverConfig",
    "ParsedAbbreviation",
    "build_ab3p_input",
    "parse_ab3p_output",
    "reconstruct_predictions",
]
