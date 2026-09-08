"""Registry for feature extractor plugins."""

from __future__ import annotations

from abrex.features.base import FeatureExtractor
from abrex.registry import Registry

EXTRACTORS = Registry[FeatureExtractor]("feature_extractors")
# Descriptive alias for callers that prefer the full extension-point name.
FEATURE_EXTRACTORS = EXTRACTORS


def register_builtin_components() -> None:
    """Register built-in feature extractors exactly once."""

    from abrex.features.extractors import (
        CapitalizationConfig,
        CapitalizationFeatureExtractor,
        CharacterAlignmentConfig,
        CharacterAlignmentFeatureExtractor,
        DigitPunctuationFeatureExtractor,
        LengthRelationshipFeatureExtractor,
        LexicalCueConfig,
        LexicalCueFeatureExtractor,
        LexicalResourceEvidenceConfig,
        LexicalResourceEvidenceFeatureExtractor,
        ParentheticalMetadataConfig,
        ParentheticalMetadataFeatureExtractor,
        PositionDirectionFeatureExtractor,
        TokenCountConfig,
        TokenCountFeatureExtractor,
    )

    registrations = (
        (
            "character_alignment",
            CharacterAlignmentFeatureExtractor,
            CharacterAlignmentConfig,
        ),
        ("token_counts", TokenCountFeatureExtractor, TokenCountConfig),
        ("capitalization", CapitalizationFeatureExtractor, CapitalizationConfig),
        ("digit_punctuation", DigitPunctuationFeatureExtractor, None),
        ("length_relationship", LengthRelationshipFeatureExtractor, None),
        ("position_direction", PositionDirectionFeatureExtractor, None),
        ("lexical_cues", LexicalCueFeatureExtractor, LexicalCueConfig),
        (
            "lexical_resource_evidence",
            LexicalResourceEvidenceFeatureExtractor,
            LexicalResourceEvidenceConfig,
        ),
        (
            "parenthetical_metadata",
            ParentheticalMetadataFeatureExtractor,
            ParentheticalMetadataConfig,
        ),
    )
    for key, factory, config_model in registrations:
        if key not in EXTRACTORS:
            EXTRACTORS.register(key, factory, config_model=config_model)  # type: ignore[arg-type]


register_builtin_components()

__all__ = ["EXTRACTORS", "FEATURE_EXTRACTORS", "register_builtin_components"]
