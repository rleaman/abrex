from pathlib import Path

import pytest

from abrex.candidates import Candidate
from abrex.config import ComponentSpec
from abrex.domain import TextSpan
from abrex.features import (
    FeatureColumn,
    FeatureExtractorMetadata,
    FeatureMatrix,
    FeatureRow,
    FeatureSchema,
)
from abrex.scorers import (
    SCORERS,
    LogisticRegressionScorer,
    ScoringDataset,
    fingerprint_feature_schema,
    load_scorer_artifact,
    write_scorer_artifact,
)
from abrex.scorers.config import ScorerConfig, create_scorer_executor


def _matrix() -> FeatureMatrix:
    schema = FeatureSchema(
        (FeatureColumn("signal", "test", "1", "separating signal"),),
        (FeatureExtractorMetadata("test", "1", ("signal",)),),
    )
    rows = tuple(
        FeatureRow(
            "d1",
            index,
            Candidate("d1", TextSpan(index, index + 1), TextSpan(2, 3), "test"),
            (value,),
        )
        for index, value in enumerate((-2.0, -1.0, 1.0, 2.0))
    )
    return FeatureMatrix(schema, rows)


def test_logistic_regression_is_deterministic_and_rejects_schema_changes() -> None:
    matrix = _matrix()
    dataset = ScoringDataset("train", matrix, (0.0, 0.0, 1.0, 1.0))
    first = LogisticRegressionScorer(max_iter=300, learning_rate=0.2)
    second = LogisticRegressionScorer(max_iter=300, learning_rate=0.2)
    first.fit(dataset, seed=1)
    second.fit(dataset, seed=999)
    assert first.predict(matrix) == second.predict(matrix)
    changed = FeatureSchema(
        (FeatureColumn("other", "test", "1", "other"),),
        (FeatureExtractorMetadata("test", "1", ("other",)),),
    )
    with pytest.raises(ValueError, match="schema"):
        first.predict(FeatureMatrix(changed, matrix.rows))


def test_logistic_scorer_save_load_round_trip(tmp_path: Path) -> None:
    matrix = _matrix()
    executor = create_scorer_executor(
        ScorerConfig(
            scorer=ComponentSpec(type="logistic_regression", params={}),
            selection=ComponentSpec(type="fixed", params={"value": 0.5}),
        )
    )
    executor.fit(ScoringDataset("train", matrix, (0.0, 0.0, 1.0, 1.0)), seed=7)
    path = tmp_path / "logistic.json"
    artifact = write_scorer_artifact(executor, path, feature_schema=matrix.schema)
    loaded, loaded_artifact = load_scorer_artifact(
        path,
        registry=SCORERS,
        expected_feature_schema_fingerprint=fingerprint_feature_schema(matrix.schema),
    )
    assert artifact == loaded_artifact
    assert loaded.predict(matrix) == executor.predict(matrix)
