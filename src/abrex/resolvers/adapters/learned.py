"""Resolver adapter that hosts a persisted T015 candidate scorer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from abrex.candidates import (
    CandidatePipelineConfig,
    ConfiguredCandidatePipeline,
    create_candidate_pipeline,
)
from abrex.domain import AbbreviationDefinition, Document
from abrex.features import (
    ConfiguredFeatureSet,
    FeatureMatrix,
    FeatureSetConfig,
    create_feature_set,
)
from abrex.resolvers.base import Resolver
from abrex.scorers import (
    ScorerConfig,
    ScorerExecutor,
    create_scorer_executor,
    fingerprint_feature_schema,
    load_scorer_artifact,
    materialize_predictions,
)
from abrex.scorers.registry import SCORERS

LEARNED_SCORER_RESOLVER_VERSION = "1"


class LearnedScorerResolverConfig(BaseModel):
    """YAML parameters for inference from a persisted learned scorer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_pipeline: CandidatePipelineConfig
    feature_set: FeatureSetConfig
    scorer: ScorerConfig
    model_path: str


class LearnedScorerResolver:
    """Generate candidates, score them, and emit ordinary resolver predictions."""

    identity = "learned_scorer"
    version = LEARNED_SCORER_RESOLVER_VERSION

    def __init__(
        self,
        candidate_pipeline: dict[str, Any],
        feature_set: dict[str, Any],
        scorer: dict[str, Any],
        model_path: str,
    ) -> None:
        config = LearnedScorerResolverConfig.model_validate(
            {
                "candidate_pipeline": candidate_pipeline,
                "feature_set": feature_set,
                "scorer": scorer,
                "model_path": model_path,
            }
        )
        self._candidate_pipeline: ConfiguredCandidatePipeline = (
            create_candidate_pipeline(config.candidate_pipeline)
        )
        self._feature_set: ConfiguredFeatureSet = create_feature_set(config.feature_set)
        configured_executor = create_scorer_executor(config.scorer)
        loaded_executor, artifact = load_scorer_artifact(
            Path(config.model_path),
            registry=SCORERS,
            scorer_params=config.scorer.scorer.params,
            expected_feature_schema_fingerprint=fingerprint_feature_schema(
                self._feature_set.schema
            ),
        )
        if config.scorer.scorer.type != artifact.scorer_key:
            raise ValueError(
                "Configured scorer key does not match persisted scorer artifact"
            )
        configured_executor.scorer = loaded_executor.scorer
        configured_executor.scorer_key = loaded_executor.scorer_key
        configured_executor.seed = artifact.seed
        self._executor: ScorerExecutor = configured_executor
        self._model_fingerprint = artifact.model_fingerprint

    def resolve(self, document: Document) -> tuple[AbbreviationDefinition, ...]:
        """Resolve one document through the candidate/feature/scorer boundaries."""

        candidate_record = self._candidate_pipeline.generate(document)
        feature_rows = self._feature_set.extract_record(document, candidate_record)
        feature_matrix = FeatureMatrix(self._feature_set.schema, feature_rows)
        scored = self._executor.score(feature_matrix)
        record = materialize_predictions(
            document,
            scored,
            self._executor,
            model_artifact_fingerprint=self._model_fingerprint,
        )
        return record.predictions


def create_learned_scorer_resolver(
    candidate_pipeline: dict[str, Any],
    feature_set: dict[str, Any],
    scorer: dict[str, Any],
    model_path: str,
) -> Resolver:
    """Factory kept separate so registry construction remains declarative."""

    return LearnedScorerResolver(candidate_pipeline, feature_set, scorer, model_path)


__all__ = [
    "LEARNED_SCORER_RESOLVER_VERSION",
    "LearnedScorerResolver",
    "LearnedScorerResolverConfig",
    "create_learned_scorer_resolver",
]
