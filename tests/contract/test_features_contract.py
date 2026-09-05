"""Reusable contract coverage for built-in feature extractor plugins."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from abrex.candidates import Candidate
from abrex.domain import Document, TextSpan
from abrex.features import (
    CapitalizationFeatureExtractor,
    CharacterAlignmentFeatureExtractor,
    DigitPunctuationFeatureExtractor,
    FeatureExtractor,
    LengthRelationshipFeatureExtractor,
    LexicalCueFeatureExtractor,
    ParentheticalMetadataFeatureExtractor,
    PositionDirectionFeatureExtractor,
    TokenCountFeatureExtractor,
)


def test_extractor_contract_is_named_numeric_and_document_local() -> None:
    factories: tuple[Callable[[], object], ...] = (
        CharacterAlignmentFeatureExtractor,
        TokenCountFeatureExtractor,
        CapitalizationFeatureExtractor,
        DigitPunctuationFeatureExtractor,
        LengthRelationshipFeatureExtractor,
        PositionDirectionFeatureExtractor,
        LexicalCueFeatureExtractor,
        ParentheticalMetadataFeatureExtractor,
    )
    for factory in factories:
        document = Document("contract", "Alpha Beta (AB)")
        candidate = Candidate(
            "contract",
            TextSpan(12, 14),
            TextSpan(0, 10),
            "parenthetical_after_long_form",
        )
        extractor = cast(FeatureExtractor, factory())
        names = extractor.feature_names
        descriptions = extractor.feature_descriptions
        values = extractor.extract(document, candidate)
        assert names
        assert len(names) == len(descriptions) == len(values)
        assert tuple(values) == tuple(names)
        assert all(isinstance(value, float) for value in values.values())
