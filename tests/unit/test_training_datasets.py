from typing import cast

from abrex.candidates import (
    Candidate,
    CandidateArtifact,
    CandidateGeneratorMetadata,
    CandidateRecord,
)
from abrex.domain import AbbreviationDefinition, CorpusRecord, Document, TextSpan
from abrex.features import (
    CharacterAlignmentFeatureExtractor,
    ConfiguredFeatureSet,
    FeatureExtractor,
)
from abrex.scorers import (
    LabelConstructionConfig,
    SplitManifest,
    materialize_training_dataset,
)


def test_partial_gold_and_explicit_silver() -> None:
    document = Document("d1", "tumor necrosis factor (TNF); unknown (UX)")
    true_candidate = Candidate("d1", TextSpan(23, 26), TextSpan(0, 21), "test")
    unknown_candidate = Candidate("d1", TextSpan(37, 39), TextSpan(28, 35), "test")
    artifact = CandidateArtifact(
        CandidateGeneratorMetadata((("test", "1"),)),
        (CandidateRecord("d1", (true_candidate, unknown_candidate)),),
    )
    record = CorpusRecord(
        document,
        (
            AbbreviationDefinition(
                "d1", true_candidate.short_form, true_candidate.long_form
            ),
        ),
    )
    feature_set = ConfiguredFeatureSet(
        (cast(FeatureExtractor, CharacterAlignmentFeatureExtractor()),)
    )
    manifest = SplitManifest(train=("d1",))
    gold_only = materialize_training_dataset(
        artifact, {"d1": document}, {"d1": record}, feature_set, manifest
    )
    assert len(gold_only.labels) == 1
    silver = materialize_training_dataset(
        artifact,
        {"d1": document},
        {"d1": record},
        feature_set,
        manifest,
        config=LabelConstructionConfig(include_silver=True),
        silver_labels={
            ("d1", unknown_candidate.short_form, unknown_candidate.long_form): (
                0.0,
                ("review-1",),
            )
        },
    )
    assert [label.origin for label in silver.labels] == ["gold", "silver"]
    assert silver.labels[1].value == 0.0
    assert silver.labels[1].evidence_ids == ("review-1",)
