"""Application service for deterministic gold/prediction evaluation."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


@runtime_checkable
class PredictionRecordLike(Protocol):
    """Minimal prediction-record boundary needed by the evaluator."""

    @property
    def document_id(self) -> str: ...

    @property
    def predictions(self) -> tuple[AbbreviationDefinition, ...]: ...


@runtime_checkable
class PredictionBatchLike(Protocol):
    """Minimal batch/artifact boundary accepted by the evaluator."""

    @property
    def records(self) -> tuple[PredictionRecordLike, ...]: ...


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
        prediction_records: Iterable[PredictionRecordLike] | PredictionBatchLike,
        *,
        expected_dataset_fingerprint: str | None = None,
    ) -> EvaluationResult:
        """Evaluate exactly the gold document set.

        A successful empty prediction set is represented by a prediction record
        whose ``predictions`` tuple is empty.  Omitting that record is a coverage
        error, as is supplying a record for an unknown document.  Batch and
        artifact objects are accepted through their ``records`` attribute so
        execution and dataset-identity metadata cannot be accidentally dropped.
        """

        logger.info("Starting evaluation with %s", self.matching_policy_key)
        gold_by_document = _index_gold_records(gold_records)
        source, source_fingerprint, execution_errors = _prediction_source(
            prediction_records
        )
        if expected_dataset_fingerprint is not None:
            if source_fingerprint is None:
                raise EvaluationError(
                    "Prediction source does not identify a canonical dataset "
                    "fingerprint"
                )
            if source_fingerprint != expected_dataset_fingerprint:
                raise EvaluationError(
                    "Prediction artifact dataset fingerprint does not match the "
                    "expected canonical dataset fingerprint"
                )
        if execution_errors:
            raise EvaluationError(
                "Prediction source contains resolver execution failures; "
                "an execution failure is not a legitimate empty prediction set"
            )
        predictions_by_document = _index_prediction_records(source)
        missing = sorted(set(gold_by_document) - set(predictions_by_document))
        unknown = sorted(set(predictions_by_document) - set(gold_by_document))
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append(f"missing prediction records for {missing!r}")
            if unknown:
                details.append(f"unknown prediction document IDs {unknown!r}")
            raise EvaluationError(
                "Prediction document coverage mismatch: " + "; ".join(details)
            )
        document_ids = sorted(gold_by_document)
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
        result = EvaluationResult(
            self.matching_policy_key,
            self.matching_policy_version,
            document_results,
            metric_results,
        )
        logger.info("Evaluation complete: %d documents", len(document_results))
        return result

    def evaluate_records(
        self,
        gold_records: Iterable[CorpusRecord],
        prediction_records: Iterable[PredictionRecordLike] | PredictionBatchLike,
        *,
        expected_dataset_fingerprint: str | None = None,
    ) -> EvaluationResult:
        """Explicit alias for callers that prefer record-oriented naming."""

        return self.evaluate(
            gold_records,
            prediction_records,
            expected_dataset_fingerprint=expected_dataset_fingerprint,
        )


def _prediction_source(
    source: Iterable[PredictionRecordLike] | PredictionBatchLike,
) -> tuple[Iterable[PredictionRecordLike], str | None, bool]:
    """Extract records while retaining optional batch/artifact metadata."""

    if isinstance(source, PredictionBatchLike):
        records = source.records
        fingerprint = getattr(source, "dataset_fingerprint", None)
        execution_errors = bool(getattr(source, "execution_errors", ()))
        return records, fingerprint, execution_errors
    return source, None, False


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
        diagnostics = getattr(record, "diagnostics", ())
        if any(
            getattr(diagnostic, "code", None) == "RESOLVER_EXECUTION_FAILED"
            for diagnostic in diagnostics
        ):
            raise EvaluationError(
                f"Prediction record {document_id!r} reports a resolver execution "
                "failure; it cannot be scored as an empty prediction set"
            )
        indexed[document_id] = record.predictions
    return indexed


__all__ = [
    "EvaluationService",
    "Evaluator",
    "PredictionBatchLike",
    "PredictionRecordLike",
]
