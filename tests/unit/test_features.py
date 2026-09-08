"""Tests for the T014 feature contracts, built-ins, and matrix composition."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

import pytest

from abrex.candidates import (
    Candidate,
    CandidateArtifact,
    CandidateGeneratorMetadata,
    CandidateRecord,
)
from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import Document, TextSpan
from abrex.features import (
    EXTRACTORS,
    FEATURE_EXTRACTORS,
    FEATURE_SCHEMA_VERSION,
    CapitalizationFeatureExtractor,
    CharacterAlignmentFeatureExtractor,
    ConfiguredFeatureSet,
    DigitPunctuationFeatureExtractor,
    FeatureColumn,
    FeatureExtractor,
    FeatureExtractorMetadata,
    FeatureMatrix,
    FeatureRow,
    FeatureSchema,
    FeatureSetConfig,
    LengthRelationshipFeatureExtractor,
    LexicalCueFeatureExtractor,
    ParentheticalMetadataFeatureExtractor,
    PositionDirectionFeatureExtractor,
    TokenCountFeatureExtractor,
    create_feature_set,
    feature_set_config_from_resolved,
)


def make_candidate(
    document: Document,
    short_text: str,
    long_text: str,
    *,
    construction: str = "parenthetical_after_long_form",
    short_start: int | None = None,
    long_start: int | None = None,
) -> Candidate:
    actual_short_start = (
        document.text.index(short_text) if short_start is None else short_start
    )
    actual_long_start = (
        document.text.index(long_text) if long_start is None else long_start
    )
    return Candidate(
        document.document_id,
        TextSpan(actual_short_start, actual_short_start + len(short_text)),
        TextSpan(actual_long_start, actual_long_start + len(long_text)),
        construction,
    )


def test_builtins_are_registered_and_emit_declared_numeric_features() -> None:
    assert FEATURE_EXTRACTORS is EXTRACTORS
    assert EXTRACTORS.keys() == (
        "capitalization",
        "character_alignment",
        "digit_punctuation",
        "length_relationship",
        "lexical_cues",
        "lexical_resource_evidence",
        "parenthetical_metadata",
        "position_direction",
        "token_counts",
    )
    document = Document("d1", "Alpha-beta 2 is defined as AB2 (AB2).")
    candidate = make_candidate(document, "AB2", "Alpha-beta 2")
    extractors = (
        CharacterAlignmentFeatureExtractor(),
        TokenCountFeatureExtractor(),
        CapitalizationFeatureExtractor(),
        DigitPunctuationFeatureExtractor(),
        LengthRelationshipFeatureExtractor(),
        PositionDirectionFeatureExtractor(),
        LexicalCueFeatureExtractor(cues=("defined as",)),
        ParentheticalMetadataFeatureExtractor(),
    )
    for extractor in extractors:
        values = extractor.extract(document, candidate)
        assert tuple(values) == extractor.feature_names
        assert all(isinstance(value, float) for value in values.values())
    assert (
        CharacterAlignmentFeatureExtractor().extract(document, candidate)[
            "alignment_lcs_length"
        ]
        == 3.0
    )
    assert LexicalCueFeatureExtractor(cues=("defined as",)).extract(
        document, candidate
    ) == {"lexical_cue_defined_as": 1.0}


def test_feature_set_is_configurable_and_matrix_order_is_deterministic() -> None:
    config = FeatureSetConfig(
        extractors=(
            ComponentSpec(type="length_relationship"),
            ComponentSpec(type="position_direction"),
        )
    )
    feature_set = create_feature_set(config)
    first = Document("b", "long (L)")
    second = Document("a", "longer (LL)")
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("parenthetical", "1"),)),
        (
            CandidateRecord("b", (make_candidate(first, "L", "long"),)),
            CandidateRecord("a", (make_candidate(second, "LL", "longer"),)),
        ),
    )
    matrix = feature_set.extract_artifact(artifact, {"a": second, "b": first})
    assert matrix.schema.version == FEATURE_SCHEMA_VERSION
    assert matrix.schema.column_names == matrix.schema.feature_names
    assert matrix.schema.feature_names == (
        "short_char_length",
        "long_char_length",
        "short_to_long_char_ratio",
        "long_to_short_char_ratio",
        "short_long_length_difference",
        "short_is_shorter",
        "short_precedes_long",
        "long_precedes_short",
        "short_start_fraction",
        "long_start_fraction",
        "short_center_fraction",
        "long_center_fraction",
        "form_gap_characters",
    )
    assert matrix.row_keys == (("a", 0), ("b", 0))
    assert matrix.shape == (2, 13)
    assert (
        matrix.matrix
        == feature_set.transform(artifact, {"a": second, "b": first}).matrix
    )
    schema_dict = matrix.schema.as_dict()
    assert isinstance(schema_dict["columns"], list)
    assert isinstance(schema_dict["columns"][0], dict)
    assert schema_dict["columns"][0]["dtype"] == "float"


def test_feature_set_config_can_be_read_from_resolved_yaml_shape() -> None:
    resolved = ResolvedConfig.model_validate(
        {
            "features": {
                "extractors": [
                    {"type": "character_alignment", "params": {"case_sensitive": True}}
                ]
            }
        }
    )
    config = feature_set_config_from_resolved(resolved)
    assert config.extractors[0].type == "character_alignment"
    assert create_feature_set(config).schema.extractors[0].version == "1"
    with pytest.raises(ValueError, match="features section"):
        feature_set_config_from_resolved(ResolvedConfig.model_validate({}))


def test_feature_extractors_handle_empty_forms_and_explicit_options() -> None:
    document = Document("empty", "")
    candidate = Candidate("empty", TextSpan(0, 0), TextSpan(0, 0), "other")
    feature_set = ConfiguredFeatureSet(
        cast(
            tuple[FeatureExtractor, ...],
            (
                CharacterAlignmentFeatureExtractor(
                    case_sensitive=True, ignore_non_alphanumeric=False
                ),
                TokenCountFeatureExtractor(token_pattern="[A-Z]+"),
                CapitalizationFeatureExtractor(),
                DigitPunctuationFeatureExtractor(),
                LengthRelationshipFeatureExtractor(),
                PositionDirectionFeatureExtractor(),
                LexicalCueFeatureExtractor(cues=("defined as",), context_characters=0),
                ParentheticalMetadataFeatureExtractor(construction_labels=("custom",)),
            ),
        )
    )
    values = feature_set.extract(document, candidate)
    assert len(values) == len(feature_set.schema.columns)
    assert values[0:5] == (0.0, 0.0, 0.0, 0.0, 1.0)
    assert feature_set.extract_candidates(document, ()) == ()


def test_parenthetical_metadata_and_reverse_position() -> None:
    document = Document("d1", "(AB) means Alpha Beta")
    candidate = make_candidate(
        document,
        "AB",
        "Alpha Beta",
        construction="parenthetical_before_long_form",
    )
    parenthetical = ParentheticalMetadataFeatureExtractor().extract(document, candidate)
    assert parenthetical["construction_parenthetical_before_long_form"] == 1.0
    assert parenthetical["construction_is_parenthetical"] == 1.0
    assert parenthetical["short_form_is_parenthesized"] == 1.0
    assert parenthetical["long_form_is_parenthesized"] == 0.0
    position = PositionDirectionFeatureExtractor().extract(document, candidate)
    assert position["long_precedes_short"] == 0.0
    assert position["short_precedes_long"] == 1.0


def test_feature_schema_and_rows_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        FeatureColumn("", "x", "1", "description")
    with pytest.raises(ValueError, match="column names"):
        FeatureColumn("Bad-name", "x", "1", "description")
    with pytest.raises(ValueError, match="metadata identity"):
        FeatureExtractorMetadata("", "1", ("x",))
    with pytest.raises(ValueError, match="feature names"):
        FeatureExtractorMetadata("x", "1", ())
    column = FeatureColumn("x", "extractor", "1", "description")
    metadata = FeatureExtractorMetadata("extractor", "1", ("x",))
    with pytest.raises(ValueError, match="Unsupported"):
        FeatureSchema((column,), (metadata,), version="features-v0")
    with pytest.raises(ValueError, match="requires columns"):
        FeatureSchema((), (metadata,))
    with pytest.raises(ValueError, match="requires columns"):
        FeatureSchema((column,), ())
    with pytest.raises(ValueError, match="disagree"):
        FeatureSchema(
            (column,), (FeatureExtractorMetadata("extractor", "1", ("other",)),)
        )
    with pytest.raises(ValueError, match="unique"):
        FeatureSchema((column, column), (metadata,))
    document = Document("d1", "x")
    candidate = make_candidate(document, "x", "x")
    with pytest.raises(TypeError, match="numeric"):
        FeatureRow("d1", 0, candidate, (True,))
    with pytest.raises(ValueError, match="document_id"):
        FeatureRow("", 0, candidate, (1.0,))
    with pytest.raises(TypeError, match="candidate_index"):
        FeatureRow("d1", True, candidate, (1.0,))
    with pytest.raises(ValueError, match="IDs"):
        FeatureRow(
            "d1", 0, Candidate("other", TextSpan(0, 0), TextSpan(0, 0), "x"), (1.0,)
        )
    with pytest.raises(ValueError, match="non-negative"):
        FeatureRow("d1", -1, candidate, (1.0,))
    row = FeatureRow("d1", 0, candidate, ())
    with pytest.raises(ValueError, match="schema width"):
        FeatureMatrix(FeatureSchema((column,), (metadata,)), (row,))
    with pytest.raises(TypeError, match="rows"):
        FeatureMatrix(FeatureSchema((column,), (metadata,)), [row])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty feature names"):
        from abrex.features.base import validate_feature_names

        validate_feature_names(())
    with pytest.raises(ValueError, match="unique"):
        validate_feature_names(("x", "x"))


def test_feature_set_rejects_missing_documents_and_mismatched_records() -> None:
    feature_set = ConfiguredFeatureSet(
        cast(tuple[FeatureExtractor, ...], (LengthRelationshipFeatureExtractor(),))
    )
    document = Document("d1", "long (L)")
    candidate = make_candidate(document, "L", "long")
    record = CandidateRecord("other")
    with pytest.raises(ValueError, match="record document ID"):
        feature_set.extract_record(document, record)
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("parenthetical", "1"),)),
        (CandidateRecord("d1", (candidate,)),),
    )
    with pytest.raises(ValueError, match="No canonical document"):
        feature_set.extract_artifact(artifact, {})


def test_custom_extractor_configuration_is_injected_and_validated() -> None:
    class CustomExtractor:
        identity = "custom"
        version = "1"
        feature_names = ("custom_value",)
        feature_descriptions = ("A custom value.",)

        def extract(
            self, document: Document, candidate: Candidate
        ) -> Mapping[str, float]:
            candidate.validate_against(document)
            return {"custom_value": 2.5}

    from abrex.registry import Registry

    registry: Registry[FeatureExtractor] = Registry("local_features")
    registry.register("custom", cast(Callable[..., FeatureExtractor], CustomExtractor))
    feature_set = create_feature_set(
        FeatureSetConfig(extractors=(ComponentSpec(type="custom"),)),
        registry=registry,
    )
    document = Document("d1", "long (L)")
    assert feature_set.extract(document, make_candidate(document, "L", "long")) == (
        2.5,
    )


def test_extractor_parameter_and_slug_validation() -> None:
    with pytest.raises(ValueError, match="does not accept"):
        DigitPunctuationFeatureExtractor(extra=True)
    with pytest.raises(ValueError, match="does not accept"):
        LengthRelationshipFeatureExtractor(extra=True)
    with pytest.raises(ValueError, match="does not accept"):
        PositionDirectionFeatureExtractor(extra=True)
    with pytest.raises(ValueError, match="CapitalizationConfig|extra"):
        CapitalizationFeatureExtractor(extra=True)
    with pytest.raises(ValueError, match="Lexical cues must not be empty"):
        LexicalCueFeatureExtractor(cues=("",))
    with pytest.raises(ValueError, match="unique feature names"):
        LexicalCueFeatureExtractor(cues=("a-b", "a b"))
    numeric = LexicalCueFeatureExtractor(cues=("123 cue",))
    assert numeric.feature_names == ("lexical_cue_cue_123_cue",)
    symbolic = LexicalCueFeatureExtractor(cues=("!!!",))
    assert symbolic.feature_names == ("lexical_cue_cue_0",)
    with pytest.raises(ValueError, match="Construction labels must not be empty"):
        ParentheticalMetadataFeatureExtractor(construction_labels=("",))
    with pytest.raises(ValueError, match="unique feature names"):
        ParentheticalMetadataFeatureExtractor(construction_labels=("a-b", "a b"))


def test_feature_set_contract_rejects_bad_plugins_and_values() -> None:
    class BadExtractor:
        identity = "bad"
        version = "1"
        feature_names = ("bad_value",)
        feature_descriptions = ("Bad value.",)

        def __init__(self, values: Mapping[str, object]) -> None:
            self.values = values

        def extract(
            self, document: Document, candidate: Candidate
        ) -> Mapping[str, object]:
            return self.values

    def configured(values: Mapping[str, object]) -> ConfiguredFeatureSet:
        return ConfiguredFeatureSet(
            cast(tuple[FeatureExtractor, ...], (BadExtractor(values),))
        )

    document = Document("d1", "long (L)")
    candidate = make_candidate(document, "L", "long")
    with pytest.raises(ValueError, match="invalid feature schema"):
        configured({"other": 1}).extract(document, candidate)
    with pytest.raises(TypeError, match="must be numeric"):
        configured({"bad_value": True}).extract(document, candidate)
    with pytest.raises(ValueError, match="must be finite"):
        configured({"bad_value": float("nan")}).extract(document, candidate)

    class EmptyNames:
        identity = "empty_names"
        version = "1"
        feature_names = ()
        feature_descriptions = ()

    class EmptyDescription:
        identity = "empty_description"
        version = "1"
        feature_names = ("empty_description",)
        feature_descriptions = ("",)

    class DuplicateNames:
        identity = "duplicate_names"
        version = "1"
        feature_names = ("same", "same")
        feature_descriptions = ("one", "two")

    for plugin, message in (
        (EmptyNames(), "feature names"),
        (EmptyDescription(), "describe every"),
        (DuplicateNames(), "unique"),
    ):
        with pytest.raises(ValueError, match=message):
            ConfiguredFeatureSet(cast(tuple[FeatureExtractor, ...], (plugin,)))
    with pytest.raises(ValueError, match="requires at least one"):
        ConfiguredFeatureSet(())


def test_feature_set_rejects_invalid_extractor_identity_or_version() -> None:
    class EmptyIdentity:
        identity = ""
        version = "1"
        feature_names = ("value",)
        feature_descriptions = ("value",)

        def extract(
            self, document: Document, candidate: Candidate
        ) -> Mapping[str, float]:
            return {"value": 1.0}

    class EmptyVersion(EmptyIdentity):
        identity = "versioned"
        version = ""

    for plugin, message in ((EmptyIdentity(), "identity"), (EmptyVersion(), "version")):
        with pytest.raises(ValueError, match=message):
            ConfiguredFeatureSet(cast(tuple[FeatureExtractor, ...], (plugin,)))

    class FirstExtractor(EmptyIdentity):
        identity = "first"
        version = "1"

    class DuplicateAcrossExtractors(EmptyIdentity):
        identity = "second"
        version = "1"

    with pytest.raises(ValueError, match="unique"):
        ConfiguredFeatureSet(
            cast(
                tuple[FeatureExtractor, ...],
                (FirstExtractor(), DuplicateAcrossExtractors()),
            )
        )
