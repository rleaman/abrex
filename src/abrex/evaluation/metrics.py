"""Metric plugins for evaluation results."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from abrex.evaluation.base import DocumentEvaluation, MetricResult

ZeroDivisionHandling = Literal["zero", "raise"]


class PairPRFConfig(BaseModel):
    """Configuration for micro pair-level precision, recall, and F1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    averaging: Literal["micro"] = "micro"
    zero_division: ZeroDivisionHandling = "zero"


class MetricError(ValueError):
    """Raised when a metric cannot be computed under its explicit policy."""


class PairPRFMetric:
    """Compute micro pair-level TP/FP/FN, precision, recall, and F1.

    With the default ``zero_division='zero'``, an undefined precision, recall,
    or F1 is reported as ``0.0``.  ``'raise'`` is available when a caller
    wants an empty denominator to fail loudly instead.
    """

    identity = "pair_prf"
    version = "1"

    def __init__(
        self,
        averaging: Literal["micro"] = "micro",
        zero_division: ZeroDivisionHandling = "zero",
    ) -> None:
        PairPRFConfig(averaging=averaging, zero_division=zero_division)
        self.averaging = averaging
        self.zero_division = zero_division

    def compute(self, documents: Iterable[DocumentEvaluation]) -> MetricResult:
        """Aggregate pair outcomes across documents using micro averaging."""

        records = tuple(documents)
        if any(not isinstance(document, DocumentEvaluation) for document in records):
            raise TypeError("documents must contain DocumentEvaluation values")
        tp = sum(document.true_positives for document in records)
        fp = sum(document.false_positives for document in records)
        fn = sum(document.false_negatives for document in records)
        precision = self._safe_ratio(tp, tp + fp, "precision")
        recall = self._safe_ratio(tp, tp + fn, "recall")
        f1 = self._safe_ratio(2 * tp, 2 * tp + fp + fn, "f1")
        return MetricResult(
            self.identity,
            (
                ("tp", tp),
                ("fp", fp),
                ("fn", fn),
                ("precision", precision),
                ("recall", recall),
                ("f1", f1),
            ),
        )

    def _safe_ratio(self, numerator: int, denominator: int, name: str) -> float:
        if denominator == 0:
            if self.zero_division == "raise":
                raise MetricError(f"Cannot compute {name}: its denominator is zero")
            return 0.0
        return numerator / denominator


PairPRF = PairPRFMetric


__all__ = [
    "MetricError",
    "PairPRF",
    "PairPRFConfig",
    "PairPRFMetric",
    "ZeroDivisionHandling",
]
