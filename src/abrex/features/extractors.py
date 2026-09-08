"""Transparent built-in feature extractors.

All built-ins emit numeric indicators/statistics only. Their configuration and
feature names are explicit so a later scorer can inspect the exact inputs it
received without consulting gold annotations.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates import Candidate
from abrex.domain import Document
from abrex.features.base import validate_feature_names
from abrex.resources import FrequencyResource, ResourceVariant

BUILTIN_FEATURE_VERSION = "1"


def _texts(document: Document, candidate: Candidate) -> tuple[str, str]:
    candidate.validate_against(document)
    return (
        document.text_for(candidate.short_form),
        document.text_for(candidate.long_form),
    )


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _indicator(value: bool) -> float:
    return 1.0 if value else 0.0


def _alphanumeric(
    text: str, *, case_sensitive: bool, ignore_non_alphanumeric: bool
) -> str:
    if ignore_non_alphanumeric:
        text = "".join(character for character in text if character.isalnum())
    return text if case_sensitive else text.casefold()


def _lcs_length(left: str, right: str) -> int:
    previous = [0] * (len(right) + 1)
    for left_character in left:
        current = [0]
        for index, right_character in enumerate(right, 1):
            current.append(
                previous[index - 1] + 1
                if left_character == right_character
                else max(previous[index], current[index - 1])
            )
        previous = current
    return previous[-1]


class CharacterAlignmentConfig(BaseModel):
    """Explicit normalization settings for LCS alignment statistics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_sensitive: bool = False
    ignore_non_alphanumeric: bool = True


class CharacterAlignmentFeatureExtractor:
    """Compute deterministic character-overlap statistics using LCS."""

    identity = "character_alignment"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "alignment_lcs_length",
        "alignment_short_coverage",
        "alignment_long_coverage",
        "alignment_length_ratio",
        "alignment_surface_exact",
    )
    feature_descriptions = (
        "Longest common subsequence length after configured character handling.",
        "Aligned-character count divided by normalized short-form length.",
        "Aligned-character count divided by normalized long-form length.",
        "Normalized short-form length divided by normalized long-form length.",
        "Whether the captured short and long strings are exactly equal.",
    )

    def __init__(self, **params: object) -> None:
        self.config = CharacterAlignmentConfig.model_validate(params)

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        short_normalized = _alphanumeric(
            short,
            case_sensitive=self.config.case_sensitive,
            ignore_non_alphanumeric=self.config.ignore_non_alphanumeric,
        )
        long_normalized = _alphanumeric(
            long,
            case_sensitive=self.config.case_sensitive,
            ignore_non_alphanumeric=self.config.ignore_non_alphanumeric,
        )
        aligned = _lcs_length(short_normalized, long_normalized)
        return dict(
            zip(
                self.feature_names,
                (
                    float(aligned),
                    _ratio(aligned, len(short_normalized)),
                    _ratio(aligned, len(long_normalized)),
                    _ratio(len(short_normalized), len(long_normalized)),
                    _indicator(short == long),
                ),
                strict=True,
            )
        )


class TokenCountConfig(BaseModel):
    """Configuration for Unicode word-token counting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    token_pattern: str = Field(default=r"\w+", min_length=1)


class TokenCountFeatureExtractor:
    """Compute token counts and the short/long token-count relationship."""

    identity = "token_counts"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "short_token_count",
        "long_token_count",
        "short_to_long_token_ratio",
        "token_count_difference",
    )
    feature_descriptions = (
        "Number of Unicode word tokens in the short form.",
        "Number of Unicode word tokens in the long form.",
        "Short-form token count divided by long-form token count; zero if undefined.",
        "Short-form token count minus long-form token count.",
    )

    def __init__(self, **params: object) -> None:
        self.config = TokenCountConfig.model_validate(params)

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        pattern = re.compile(self.config.token_pattern, flags=re.UNICODE)
        short_count = len(pattern.findall(short))
        long_count = len(pattern.findall(long))
        return dict(
            zip(
                self.feature_names,
                (
                    float(short_count),
                    float(long_count),
                    _ratio(short_count, long_count),
                    float(short_count - long_count),
                ),
                strict=True,
            )
        )


class CapitalizationConfig(BaseModel):
    """Configuration for capitalization features."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _uppercase_ratio(text: str) -> float:
    cased = [character for character in text if character.isalpha()]
    return _ratio(sum(character.isupper() for character in cased), len(cased))


class CapitalizationFeatureExtractor:
    """Expose capitalization patterns as numeric indicators and ratios."""

    identity = "capitalization"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "short_all_upper",
        "short_initial_upper",
        "short_all_lower",
        "short_mixed_case",
        "short_uppercase_ratio",
        "long_all_upper",
        "long_initial_upper",
        "long_all_lower",
        "long_mixed_case",
        "long_uppercase_ratio",
    )
    feature_descriptions = (
        "Whether every cased short-form character is uppercase.",
        "Whether the first short-form character is uppercase.",
        "Whether every cased short-form character is lowercase.",
        "Whether the short form contains both uppercase and lowercase letters.",
        "Uppercase short-form letters divided by cased short-form letters.",
        "Whether every cased long-form character is uppercase.",
        "Whether the first long-form character is uppercase.",
        "Whether every cased long-form character is lowercase.",
        "Whether the long form contains both uppercase and lowercase letters.",
        "Uppercase long-form letters divided by cased long-form letters.",
    )

    def __init__(self, **params: object) -> None:
        self.config = CapitalizationConfig.model_validate(params)

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        short_letters = [character for character in short if character.isalpha()]
        long_letters = [character for character in long if character.isalpha()]
        short_has_upper = any(character.isupper() for character in short_letters)
        short_has_lower = any(character.islower() for character in short_letters)
        long_has_upper = any(character.isupper() for character in long_letters)
        long_has_lower = any(character.islower() for character in long_letters)
        values = (
            _indicator(bool(short_letters) and not short_has_lower),
            _indicator(bool(short) and short[0].isupper()),
            _indicator(bool(short_letters) and not short_has_upper),
            _indicator(short_has_upper and short_has_lower),
            _uppercase_ratio(short),
            _indicator(bool(long_letters) and not long_has_lower),
            _indicator(bool(long) and long[0].isupper()),
            _indicator(bool(long_letters) and not long_has_upper),
            _indicator(long_has_upper and long_has_lower),
            _uppercase_ratio(long),
        )
        return dict(zip(self.feature_names, values, strict=True))


class DigitPunctuationFeatureExtractor:
    """Expose digit and non-whitespace punctuation patterns."""

    identity = "digit_punctuation"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "short_digit_count",
        "short_digit_ratio",
        "short_punctuation_count",
        "short_punctuation_ratio",
        "short_has_digit",
        "short_has_punctuation",
        "long_digit_count",
        "long_digit_ratio",
        "long_punctuation_count",
        "long_punctuation_ratio",
        "long_has_digit",
        "long_has_punctuation",
    )
    feature_descriptions = tuple(
        "Digit and punctuation count/ratio indicators for the short and long forms."
        for _ in feature_names
    )

    def __init__(self, **params: object) -> None:
        if params:
            raise ValueError("digit_punctuation does not accept parameters")

    @staticmethod
    def _counts(text: str) -> tuple[int, int]:
        digits = sum(character.isdigit() for character in text)
        punctuation = sum(
            not character.isalnum() and not character.isspace() for character in text
        )
        return digits, punctuation

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        short_digits, short_punctuation = self._counts(short)
        long_digits, long_punctuation = self._counts(long)
        values = (
            float(short_digits),
            _ratio(short_digits, len(short)),
            float(short_punctuation),
            _ratio(short_punctuation, len(short)),
            _indicator(short_digits > 0),
            _indicator(short_punctuation > 0),
            float(long_digits),
            _ratio(long_digits, len(long)),
            float(long_punctuation),
            _ratio(long_punctuation, len(long)),
            _indicator(long_digits > 0),
            _indicator(long_punctuation > 0),
        )
        return dict(zip(self.feature_names, values, strict=True))


class LengthRelationshipFeatureExtractor:
    """Expose character-length relationships without accepting the pair."""

    identity = "length_relationship"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "short_char_length",
        "long_char_length",
        "short_to_long_char_ratio",
        "long_to_short_char_ratio",
        "short_long_length_difference",
        "short_is_shorter",
    )
    feature_descriptions = (
        "Number of characters in the short form.",
        "Number of characters in the long form.",
        "Short-form character length divided by long-form character length.",
        "Long-form character length divided by short-form character length.",
        "Short-form character length minus long-form character length.",
        "Whether the short form has fewer characters than the long form.",
    )

    def __init__(self, **params: object) -> None:
        if params:
            raise ValueError("length_relationship does not accept parameters")

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        short_length, long_length = len(short), len(long)
        values = (
            float(short_length),
            float(long_length),
            _ratio(short_length, long_length),
            _ratio(long_length, short_length),
            float(short_length - long_length),
            _indicator(short_length < long_length),
        )
        return dict(zip(self.feature_names, values, strict=True))


class PositionDirectionFeatureExtractor:
    """Expose canonical span positions and ordering/distance indicators."""

    identity = "position_direction"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "short_precedes_long",
        "long_precedes_short",
        "short_start_fraction",
        "long_start_fraction",
        "short_center_fraction",
        "long_center_fraction",
        "form_gap_characters",
    )
    feature_descriptions = (
        "Whether the short-form span starts no later than the long-form span.",
        "Whether the long-form span starts before the short-form span.",
        "Short-form start offset divided by document length; zero for empty text.",
        "Long-form start offset divided by document length; zero for empty text.",
        "Short-form midpoint divided by document length; zero for empty text.",
        "Long-form midpoint divided by document length; zero for empty text.",
        "Non-overlapping character distance between the two spans.",
    )

    def __init__(self, **params: object) -> None:
        if params:
            raise ValueError("position_direction does not accept parameters")

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        _texts(document, candidate)
        short, long = candidate.short_form, candidate.long_form
        document_length = len(document.text)
        gap = max(short.start, long.start) - min(short.end, long.end)
        values = (
            _indicator(short.start <= long.start),
            _indicator(long.start < short.start),
            _ratio(short.start, document_length),
            _ratio(long.start, document_length),
            _ratio((short.start + short.end) / 2, document_length),
            _ratio((long.start + long.end) / 2, document_length),
            float(max(0, gap)),
        )
        return dict(zip(self.feature_names, values, strict=True))


class LexicalCueConfig(BaseModel):
    """Cues and local context used by the lexical-cue indicator extractor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cues: tuple[str, ...] = (
        "abbreviated as",
        "also known as",
        "defined as",
    )
    context_characters: int = Field(default=80, ge=0)
    case_sensitive: bool = False

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if any(not cue.strip() for cue in self.cues):
            raise ValueError("Lexical cues must not be empty")


def _slug(value: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not slug:
        slug = f"cue_{index}"
    if slug[0].isdigit():
        slug = f"cue_{slug}"
    return slug


class LexicalCueFeatureExtractor:
    """Emit one indicator per configured cue in a local candidate context."""

    identity = "lexical_cues"
    version = BUILTIN_FEATURE_VERSION

    def __init__(self, **params: object) -> None:
        self.config = LexicalCueConfig.model_validate(params)
        slugs = tuple(_slug(cue, index) for index, cue in enumerate(self.config.cues))
        if len(set(slugs)) != len(slugs):
            raise ValueError("Lexical cues must map to unique feature names")
        self.feature_names = validate_feature_names(
            f"lexical_cue_{slug}" for slug in slugs
        )
        self.feature_descriptions = tuple(
            f"Whether configured lexical cue {cue!r} occurs in local candidate context."
            for cue in self.config.cues
        )

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        _texts(document, candidate)
        start = max(
            0,
            min(candidate.short_form.start, candidate.long_form.start)
            - self.config.context_characters,
        )
        end = min(
            len(document.text),
            max(candidate.short_form.end, candidate.long_form.end)
            + self.config.context_characters,
        )
        context = document.text[start:end]
        if not self.config.case_sensitive:
            context = context.casefold()
        values = tuple(
            _indicator(
                (cue if self.config.case_sensitive else cue.casefold()) in context
            )
            for cue in self.config.cues
        )
        return dict(zip(self.feature_names, values, strict=True))


class LexicalResourceEvidenceConfig(BaseModel):
    """Aggregate resource inputs for local, gold-independent evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_paths: tuple[Path, ...] = Field(min_length=1)
    context_characters: int = Field(default=80, ge=0)


class LexicalResourceEvidenceFeatureExtractor:
    """Expose resource evidence separately from structural candidate cues."""

    identity = "lexical_resource_evidence"
    version = BUILTIN_FEATURE_VERSION
    feature_names = (
        "resource_variant_count",
        "resource_source_count",
        "resource_source_agreement",
        "resource_ambiguity_count",
        "resource_observed_count",
        "resource_local_pair_match",
        "resource_contextual_short_count",
    )
    feature_descriptions = (
        "Number of raw resource variants for the candidate short form.",
        "Number of distinct resource source label and hash identities.",
        "Whether more than one distinct resource source identity supports the "
        "short form.",
        "Number of distinct long-form keys among resource variants.",
        "Aggregate resource count across variants; its unit remains source-defined.",
        "Whether the candidate's exact local short/long pair matches a resource "
        "variant.",
        "Number of exact short-form occurrences in the configured local context "
        "window.",
    )

    def __init__(self, **params: object) -> None:
        self.config = LexicalResourceEvidenceConfig.model_validate(params)
        self.resources = tuple(
            FrequencyResource(path) for path in self.config.resource_paths
        )

    @property
    def cache_identity(self) -> str:
        """Return a content-aware identity for reproducible feature reuse."""

        sources = ",".join(
            f"{summary.source_label}:{summary.source_sha256}"
            for summary in (resource.summary() for resource in self.resources)
        )
        return (
            f"{self.identity}:{self.version}:{self.config.context_characters}:{sources}"
        )

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        short, long = _texts(document, candidate)
        variants = tuple(
            variant for resource in self.resources for variant in resource.lookup(short)
        )
        identities = {(item.source_label, item.source_sha256) for item in variants}
        long_keys = {item.long_form_key for item in variants}
        pair_match = any(_variant_matches_long(item, long) for item in variants)
        start = max(0, candidate.long_form.start - self.config.context_characters)
        end = min(
            len(document.text), candidate.long_form.end + self.config.context_characters
        )
        contextual_short_count = sum(
            len(_occurrences(document.text[start:end], item.short_form_raw))
            for item in variants
        )
        return dict(
            zip(
                self.feature_names,
                (
                    float(len(variants)),
                    float(len(identities)),
                    _indicator(len(identities) > 1),
                    float(len(long_keys)),
                    float(sum(item.count for item in variants)),
                    _indicator(pair_match),
                    float(contextual_short_count),
                ),
                strict=True,
            )
        )


def _variant_matches_long(variant: ResourceVariant, long_form: str) -> bool:
    return (
        variant.long_form_raw == long_form
        or variant.long_form_key == long_form.casefold()
    )


def _occurrences(text: str, value: str) -> tuple[tuple[int, int], ...]:
    if not value:
        return ()
    return tuple(
        (match.start(), match.end()) for match in re.finditer(re.escape(value), text)
    )


class ParentheticalMetadataConfig(BaseModel):
    """Construction labels to expose as one-hot metadata columns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    construction_labels: tuple[str, ...] = (
        "parenthetical_after_long_form",
        "parenthetical_before_long_form",
    )


class ParentheticalMetadataFeatureExtractor:
    """Expose construction labels and directly observable parenthesis metadata."""

    identity = "parenthetical_metadata"
    version = BUILTIN_FEATURE_VERSION

    def __init__(self, **params: object) -> None:
        self.config = ParentheticalMetadataConfig.model_validate(params)
        if any(not label.strip() for label in self.config.construction_labels):
            raise ValueError("Construction labels must not be empty")
        slugs = tuple(
            _slug(label, index)
            for index, label in enumerate(self.config.construction_labels)
        )
        if len(set(slugs)) != len(slugs):
            raise ValueError("Construction labels must map to unique feature names")
        self._construction_names = tuple(f"construction_{slug}" for slug in slugs)
        self.feature_names = validate_feature_names(
            (
                *self._construction_names,
                "construction_is_parenthetical",
                "construction_other",
                "short_form_is_parenthesized",
                "long_form_is_parenthesized",
            )
        )
        self.feature_descriptions = tuple(
            f"Whether the candidate construction equals configured label {label!r}."
            for label in self.config.construction_labels
        ) + (
            "Whether the construction label begins with 'parenthetical'.",
            "Whether no configured construction label matched.",
            "Whether the short-form span is immediately enclosed by parentheses.",
            "Whether the long-form span is immediately enclosed by parentheses.",
        )

    def extract(self, document: Document, candidate: Candidate) -> Mapping[str, float]:
        _texts(document, candidate)
        matched = tuple(
            candidate.construction == label for label in self.config.construction_labels
        )
        short_parenthesized = (
            candidate.short_form.start > 0
            and candidate.short_form.end < len(document.text)
            and document.text[candidate.short_form.start - 1] == "("
            and document.text[candidate.short_form.end] == ")"
        )
        long_parenthesized = (
            candidate.long_form.start > 0
            and candidate.long_form.end < len(document.text)
            and document.text[candidate.long_form.start - 1] == "("
            and document.text[candidate.long_form.end] == ")"
        )
        values = tuple(_indicator(value) for value in matched) + (
            _indicator(candidate.construction.startswith("parenthetical")),
            _indicator(not any(matched)),
            _indicator(short_parenthesized),
            _indicator(long_parenthesized),
        )
        return dict(zip(self.feature_names, values, strict=True))


__all__ = [
    "BUILTIN_FEATURE_VERSION",
    "CapitalizationConfig",
    "CapitalizationFeatureExtractor",
    "CharacterAlignmentConfig",
    "CharacterAlignmentFeatureExtractor",
    "DigitPunctuationFeatureExtractor",
    "LengthRelationshipFeatureExtractor",
    "LexicalCueConfig",
    "LexicalCueFeatureExtractor",
    "LexicalResourceEvidenceConfig",
    "LexicalResourceEvidenceFeatureExtractor",
    "ParentheticalMetadataConfig",
    "ParentheticalMetadataFeatureExtractor",
    "PositionDirectionFeatureExtractor",
    "TokenCountConfig",
    "TokenCountFeatureExtractor",
]
