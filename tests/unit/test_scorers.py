"""Tests for the T015 scorer lifecycle and artifact plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abrex.candidates import (
    Candidate,
    CandidatePipelineConfig,
    create_candidate_pipeline,
)
from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import Document, TextSpan
from abrex.features import (
    FeatureColumn,
    FeatureExtractorMetadata,
    FeatureMatrix,
    FeatureRow,
    FeatureSchema,
    FeatureSetConfig,
    create_feature_set,
)
from abrex.registry import Registry
from abrex.resolvers import create_resolver_executor
from abrex.scorers import (
    SCORERS,
    ScorerArtifactError,
    ScorerConfig,
    ScoringDataset,
    SplitManifest,
    create_scorer_executor,
    derive_child_seed,
    fingerprint_feature_schema,
    load_scorer_artifact,
    materialize_feature_predictions,
    partition_dataset,
    read_split_manifest,
    write_scorer_artifact,
)
from abrex.scorers.base import Scorer


class FakeScorer:
    identity = "fake"
    version = "1"

    def __init__(self, bias: float = 0.0) -> None:
        self.bias = bias
        self.seed: int | None = None
        self.fitted = False

    def fit(
        self,
        train: ScoringDataset,
        *,
        dev: ScoringDataset | None = None,
        seed: int | None = None,
    ) -> None:
        self.seed = seed
        self.fitted = True
        assert train.split == "train"
        assert dev is None or dev.split == "dev"

    def predict(self, features: FeatureMatrix) -> tuple[float, ...]:
        if not self.fitted:
            raise RuntimeError("not fitted")
        return tuple(row.values[0] + self.bias for row in features.rows)

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps({"bias": self.bias, "fitted": self.fitted}), encoding="utf-8"
        )

    def load(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.bias = float(data["bias"])
        self.fitted = bool(data["fitted"])


def _feature_matrix() -> FeatureMatrix:
    candidate = Candidate("doc-1", TextSpan(23, 26), TextSpan(0, 21), "parenthetical")
    schema = FeatureSchema(
        (FeatureColumn("score", "test", "1", "test score"),),
        (FeatureExtractorMetadata("test", "1", ("score",)),),
    )
    return FeatureMatrix(
        schema,
        (FeatureRow("doc-1", 0, candidate, (0.8,)),),
    )


def _registry() -> Registry[Scorer]:
    registry = Registry[Scorer]("test_scorers")
    registry.register("fake", FakeScorer)
    return registry


def test_executor_fit_predict_selection_and_seed() -> None:
    matrix = _feature_matrix()
    config = ScorerConfig(
        scorer=ComponentSpec(type="fake", params={"bias": 0.1}),
        selection=ComponentSpec(type="fixed", params={"value": 0.5}),
        feature_config_fingerprint="features-digest",
    )
    executor = create_scorer_executor(config, scorer_registry=_registry())
    dataset = ScoringDataset("train", matrix, (1.0,))
    executor.fit(dataset, seed=17)
    assert cast(FakeScorer, executor.scorer).seed == derive_child_seed(17, "fake")
    assert executor.predict(matrix) == (0.9,)
    assert executor.score(matrix)[0].score == 0.9
    assert executor.select((0.4, 0.5)) == (False, True)


def test_split_manifest_consumption_is_explicit(tmp_path: Path) -> None:
    matrix = _feature_matrix()
    second = FeatureRow(
        "doc-2", 0, Candidate("doc-2", TextSpan(0, 1), TextSpan(2, 3), "x"), (0.2,)
    )
    matrix = FeatureMatrix(matrix.schema, (matrix.rows[0], second))
    manifest = SplitManifest(train=("doc-1",), dev=("doc-2",))
    datasets = partition_dataset(matrix, (1.0, 0.0), manifest)
    assert datasets.train.features.row_keys == (("doc-1", 0),)
    assert datasets.dev is not None
    assert datasets.dev.labels == (0.0,)

    path = tmp_path / "splits.json"
    path.write_text(json.dumps(manifest.model_dump()), encoding="utf-8")
    assert read_split_manifest(path) == manifest
    with pytest.raises(ValueError, match="absent"):
        partition_dataset(matrix, (1.0, 0.0), SplitManifest(train=("other",)))


def test_model_artifact_round_trip_and_tamper_detection(tmp_path: Path) -> None:
    matrix = _feature_matrix()
    executor = create_scorer_executor(
        ScorerConfig(scorer=ComponentSpec(type="fake", params={})),
        scorer_registry=_registry(),
    )
    executor.fit(ScoringDataset("train", matrix, (1.0,)), seed=3)
    path = tmp_path / "model.json"
    artifact = write_scorer_artifact(
        executor,
        path,
        feature_schema=matrix.schema,
        feature_config_fingerprint="features-digest",
        seed=3,
    )
    assert artifact.feature_schema_fingerprint == fingerprint_feature_schema(
        matrix.schema
    )
    loaded, loaded_artifact = load_scorer_artifact(
        path,
        registry=_registry(),
        expected_feature_schema_fingerprint=artifact.feature_schema_fingerprint,
    )
    assert loaded_artifact == artifact
    assert loaded.predict(matrix) == (0.8,)
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ScorerArtifactError, match="fingerprint"):
        load_scorer_artifact(path, registry=_registry())


def test_materialization_preserves_resolver_contract_and_provenance() -> None:
    matrix = _feature_matrix()
    executor = create_scorer_executor(
        ScorerConfig(
            scorer=ComponentSpec(type="fake", params={}),
            selection=ComponentSpec(type="fixed", params={"value": 0.5}),
            feature_config_fingerprint="features-digest",
        ),
        scorer_registry=_registry(),
    )
    executor.fit(ScoringDataset("train", matrix, (1.0,)))
    document = Document("doc-1", "Tumor necrosis factor (TNF)")
    records = materialize_feature_predictions(
        executor.score(matrix),
        {document.document_id: document},
        executor,
        model_artifact_fingerprint="model-digest",
    )
    prediction = records[0].predictions[0]
    assert prediction.short_form_text == "TNF"
    assert prediction.prediction is not None
    assert prediction.prediction.model_artifact_fingerprint == "model-digest"
    assert prediction.prediction.feature_config_fingerprint == "features-digest"


def test_scoring_configuration_can_be_read_from_resolved_section() -> None:
    resolved = ResolvedConfig.model_validate(
        {
            "scorer": {
                "type": "fake",
                "params": {},
                "selection": {"type": "fixed", "params": {"value": 0.5}},
            }
        }
    )
    config = __import__(
        "abrex.scorers", fromlist=["scorer_config_from_resolved"]
    ).scorer_config_from_resolved(resolved)
    assert config.scorer.type == "fake"
    assert "fake" not in SCORERS


def test_learned_scorer_hosts_the_existing_resolver_contract(tmp_path: Path) -> None:
    if "fake" not in SCORERS:
        SCORERS.register("fake", FakeScorer)
    document = Document("learned-1", "Tumor necrosis factor (TNF)")
    candidate_config = CandidatePipelineConfig.model_validate(
        {"generators": [{"type": "parenthetical", "params": {}}]}
    )
    feature_config = FeatureSetConfig.model_validate(
        {"extractors": [{"type": "length_relationship", "params": {}}]}
    )
    candidates = create_candidate_pipeline(candidate_config).generate(document)
    feature_set = create_feature_set(feature_config)
    matrix = FeatureMatrix(
        feature_set.schema,
        feature_set.extract_record(document, candidates),
    )
    scorer_config = ScorerConfig(
        scorer=ComponentSpec(type="fake", params={}),
        selection=ComponentSpec(type="fixed", params={"value": 0.0}),
        feature_config_fingerprint="features-digest",
    )
    scorer = create_scorer_executor(scorer_config)
    scorer.fit(ScoringDataset("train", matrix, (1.0,) * len(matrix.rows)))
    model_path = tmp_path / "learned-model.json"
    write_scorer_artifact(scorer, model_path, feature_schema=matrix.schema)

    resolver = create_resolver_executor(
        ComponentSpec(
            type="learned_scorer",
            params={
                "candidate_pipeline": candidate_config.model_dump(mode="python"),
                "feature_set": feature_config.model_dump(mode="python"),
                "scorer": scorer_config.model_dump(mode="python"),
                "model_path": str(model_path),
            },
        )
    )
    predictions = tuple(resolver.resolve_document(document).predictions)
    assert predictions
    assert predictions[0].prediction is not None
    assert predictions[0].prediction.model_artifact_fingerprint
