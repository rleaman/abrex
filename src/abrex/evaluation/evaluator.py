"""Application service for deterministic gold/prediction evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from abrex.domain import AbbreviationDefinition, CorpusRecord
from abrex.evaluation.base import (
    DocumentEvaluation,
    EvaluationError,
    EvaluationResult,
    MatchingPolicy,
    Metric,
)


@runtime_checkable
class PredictionRecordLike(Protocol):
    """Minimal prediction-record boundary needed by the evaluator."""

    @property
    def document_id(self) -> str: ...

    @property
    def predictions(self) -> tuple[AbbreviationDefinition, ...]: ...


class Evaluator:
    """Apply one matching policy and an ordered set of metric plugins."""

    def __init__(
        self,
        matching_policy: MatchingPolicy,
        metrics: Iterable[Metric] = (),
        *,
        matching_policy_key: str | None = None,
        matching_policy_version: str | None = None,
    ) -> None:
        if not isinstance(matching_policy, MatchingPolicy):
            raise TypeError("matching_policy must implement MatchingPolicy")
        selected_key = matching_policy_key or matching_policy.identity
        selected_version = matching_policy_version or matching_policy.version
        if not isinstance(selected_key, str) or not selected_key.strip():
            raise ValueError("matching policy identity must not be empty")
        if not isinstance(selected_version, str) or not selected_version.strip():
            raise ValueError("matching policy version must not be empty")
        selected_metrics = tuple(metrics)
        if any(not isinstance(metric, Metric) for metric in selected_metrics):
            raise TypeError("metrics must implement Metric")
        self.matching_policy = matching_policy
        self.metrics = selected_metrics
        self.matching_policy_key = selected_key
        self.matching_policy_version = selected_version

    def evaluate(
        self,
        gold_records: Iterable[CorpusRecord],
        prediction_records: Iterable[PredictionRecordLike],
    ) -> EvaluationResult:
        """Evaluate all documents in the deterministic union of both inputs."""

        gold_by_document = _index_gold_records(gold_records)
        predictions_by_document = _index_prediction_records(prediction_records)
        document_ids = sorted(set(gold_by_document) | set(predictions_by_document))
        documents: list[DocumentEvaluation] = []
        for document_id in document_ids:
            gold = (
                gold_by_document[document_id].gold_annotations
                if document_id in gold_by_document
                else ()
            )
            predictions = predictions_by_document.get(document_id, ())
            documents.append(self.matching_policy.match(document_id, gold, predictions))
        document_results = tuple(documents)
        metric_results = tuple(
            metric.compute(document_results) for metric in self.metrics
        )
        return EvaluationResult(
            self.matching_policy_key,
            self.matching_policy_version,
            document_results,
            metric_results,
        )

    def evaluate_records(
        self,
        gold_records: Iterable[CorpusRecord],
        prediction_records: Iterable[PredictionRecordLike],
    ) -> EvaluationResult:
        """Explicit alias for callers that prefer record-oriented naming."""

        return self.evaluate(gold_records, prediction_records)


EvaluationService = Evaluator


def _index_gold_records(
    records: Iterable[CorpusRecord],
) -> dict[str, CorpusRecord]:
    indexed: dict[str, CorpusRecord] = {}
    for record in records:
        if not isinstance(record, CorpusRecord):
            raise TypeError("gold_records must contain CorpusRecord values")
        document_id = record.document.document_id
        if document_id in indexed:
            raise EvaluationError(f"Duplicate gold document ID: {document_id!r}")
        indexed[document_id] = record
    return indexed


def _index_prediction_records(
    records: Iterable[PredictionRecordLike],
) -> dict[str, tuple[AbbreviationDefinition, ...]]:
    indexed: dict[str, tuple[AbbreviationDefinition, ...]] = {}
    for record in records:
        if not isinstance(record, PredictionRecordLike):
            raise TypeError("prediction_records must contain prediction-record values")
        document_id = record.document_id
        if document_id in indexed:
            raise EvaluationError(f"Duplicate prediction document ID: {document_id!r}")
        if any(
            prediction.document_id != document_id for prediction in record.predictions
        ):
            raise EvaluationError(
                f"Prediction record {document_id!r} contains another document ID"
            )
        indexed[document_id] = record.predictions
    return indexed


__all__ = ["EvaluationService", "Evaluator", "PredictionRecordLike"]
