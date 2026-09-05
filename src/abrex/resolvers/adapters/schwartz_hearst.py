"""A deterministic implementation of the Schwartz--Hearst heuristic."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import AbbreviationDefinition, Document, TextSpan

SCHWARTZ_HEARST_VERSION = "1"


class SchwartzHearstResolverConfig(BaseModel):
    """Explicit choices governing candidate selection and character matching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_short_form_length: int = Field(default=2, ge=1)
    max_long_form_words: int | None = Field(default=None, ge=1)
    ignore_non_alphanumeric: bool = True
    case_sensitive: bool = False


class SchwartzHearstResolver:
    """Extract ``long form (SHORT)`` definitions with canonical spans.

    The baseline supports parenthetical short forms after their long forms.
    Reverse-order definitions and nested parentheses are intentionally not
    accepted; those are separate algorithmic variants rather than hidden
    fallback behavior.
    """

    identity = "schwartz_hearst"
    version = SCHWARTZ_HEARST_VERSION
    _parenthetical = re.compile(r"\((?P<short>[A-Za-z][A-Za-z0-9-]*)\)")
    _word = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

    def __init__(self, **params: object) -> None:
        self.config = SchwartzHearstResolverConfig.model_validate(params)

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Return accepted definitions in source order."""

        return self._resolve(document)

    def _resolve(self, document: Document) -> Iterator[AbbreviationDefinition]:
        for match in self._parenthetical.finditer(document.text):
            short_text = match.group("short")
            if len(short_text) < self.config.minimum_short_form_length:
                continue
            long_span = self._find_long_form(document.text, match.start(), short_text)
            if long_span is None:
                continue
            short_span = TextSpan(match.start("short"), match.end("short"))
            yield AbbreviationDefinition(
                document_id=document.document_id,
                short_form=short_span,
                long_form=long_span,
                short_form_text=document.text_for(short_span),
                long_form_text=document.text_for(long_span),
            )

    def _find_long_form(
        self, text: str, short_start: int, short_text: str
    ) -> TextSpan | None:
        prefix = text[:short_start].rstrip()
        words = tuple(self._word.finditer(prefix))
        if not words:
            return None
        max_words = self.config.max_long_form_words
        if max_words is None:
            max_words = 2 * len(short_text) - 1
        candidate_words = words[-max_words:]
        candidate_start = candidate_words[0].start()
        candidate_end = candidate_words[-1].end()
        candidate = text[candidate_start:candidate_end]
        match_indexes = _align_short_form(
            short_text,
            candidate,
            ignore_non_alphanumeric=self.config.ignore_non_alphanumeric,
            case_sensitive=self.config.case_sensitive,
        )
        if match_indexes is None:
            return None
        return TextSpan(candidate_start + match_indexes[0], candidate_end)


def _align_short_form(
    short_form: str,
    long_form: str,
    *,
    ignore_non_alphanumeric: bool,
    case_sensitive: bool,
) -> tuple[int, ...] | None:
    """Return source indexes for a backwards subsequence alignment."""

    long_indexes = _character_indexes(long_form, ignore_non_alphanumeric)
    short_indexes = _character_indexes(short_form, ignore_non_alphanumeric)
    if not short_indexes or len(short_indexes) > len(long_indexes):
        return None
    normalized_long = _normalized_characters(long_form, long_indexes, case_sensitive)
    normalized_short = _normalized_characters(short_form, short_indexes, case_sensitive)
    position = len(normalized_long) - 1
    matched: list[int] = []
    for short_character in reversed(normalized_short):
        while position >= 0 and normalized_long[position] != short_character:
            position -= 1
        if position < 0:
            return None
        matched.append(long_indexes[position])
        position -= 1
    return tuple(reversed(matched))


def _character_indexes(value: str, ignore_non_alphanumeric: bool) -> tuple[int, ...]:
    """Return indexes participating in the configured alignment alphabet."""

    return tuple(
        index
        for index, character in enumerate(value)
        if character.isalnum() or (not ignore_non_alphanumeric and character in "-'")
    )


def _normalized_characters(
    value: str, indexes: tuple[int, ...], case_sensitive: bool
) -> tuple[str, ...]:
    """Normalize selected source characters according to configuration."""

    return tuple(
        value[index] if case_sensitive else value[index].casefold() for index in indexes
    )


__all__ = [
    "SCHWARTZ_HEARST_VERSION",
    "SchwartzHearstResolver",
    "SchwartzHearstResolverConfig",
]
