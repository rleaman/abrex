"""Domain-facing evaluation contracts and immutable result values."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from abrex.domain import AbbreviationDefinition

MatchStatus = Literal["tp", "fp", "fn", "unscoreable"]


class EvaluationError(ValueError):
    """Base class for evaluation construction and execution failures."""


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """One one-to-one matching outcome for a document.

    ``gold_index`` and ``prediction_index`` are canonical sorted positions,
    not positions in a caller's input sequence.  This makes detailed records
    reproducible when the same annotations are supplied in a different order.
    """

    document_id: str
    status: MatchStatus
    gold: AbbreviationDefinition | None = None
    prediction: AbbreviationDefinition | None = None
    gold_index: int | None = None
    prediction_index: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Match document_id must be a non-empty string")
        if self.status not in ("tp", "fp", "fn", "unscoreable"):
            raise ValueError(f"Unsupported match status: {self.status!r}")
        for name, value in (("gold", self.gold), ("prediction", self.prediction)):
            if value is not None and not isinstance(value, AbbreviationDefinition):
                raise TypeError(f"{name} must be an AbbreviationDefinition or None")
        if self.status == "tp" and (self.gold is None or self.prediction is None):
            raise ValueError("A true-positive outcome requires gold and prediction")
        if self.status == "fp" and (self.gold is not None or self.prediction is None):
            raise ValueError("A false-positive outcome requires prediction only")
        if self.status == "fn" and (self.gold is None or self.prediction is not None):
            raise ValueError("A false-negative outcome requires gold only")
        if self.status == "unscoreable" and (
            (self.gold is None) == (self.prediction is None)
        ):
            raise ValueError(
                "An unscoreable outcome requires exactly one annotation value"
            )
        for name, index_value in (
            ("gold_index", self.gold_index),
            ("prediction_index", self.prediction_index),
        ):
            if index_value is not None and (
                isinstance(index_value, bool)
                or not isinstance(index_value, int)
                or index_value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.gold is not None and self.gold.document_id != self.document_id:
            raise EvaluationError("Gold annotation document ID does not match outcome")
        if (
            self.prediction is not None
            and self.prediction.document_id != self.document_id
        ):
            raise EvaluationError("Prediction document ID does not match outcome")

    @property
    def kind(self) -> MatchStatus:
        """Return the outcome category using the short metric names."""

        return self.status

    @property
    def gold_annotation(self) -> AbbreviationDefinition | None:
        """Return the matched or unmatched gold annotation."""

        return self.gold

    @property
    def predicted_annotation(self) -> AbbreviationDefinition | None:
        """Return the matched or unmatched prediction."""

        return self.prediction

    @property
    def is_true_positive(self) -> bool:
        """Return whether this outcome contributes one pair-level TP."""

        return self.status == "tp"


@dataclass(frozen=True, slots=True)
class DocumentEvaluation:
    """All detailed outcomes and source annotations for one document."""

    document_id: str
    gold_annotations: tuple[AbbreviationDefinition, ...] = ()
    predictions: tuple[AbbreviationDefinition, ...] = ()
    outcomes: tuple[MatchOutcome, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Evaluation document_id must be a non-empty string")
        for name, values in (
            ("gold_annotations", self.gold_annotations),
            ("predictions", self.predictions),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, AbbreviationDefinition) for value in values
            ):
                raise TypeError(
                    f"{name} must be a tuple of AbbreviationDefinition values"
                )
            if any(value.document_id != self.document_id for value in values):
                raise EvaluationError(f"{name} contains another document ID")
        if not isinstance(self.outcomes, tuple) or any(
            not isinstance(value, MatchOutcome) for value in self.outcomes
        ):
            raise TypeError("outcomes must be a tuple of MatchOutcome values")
        if any(value.document_id != self.document_id for value in self.outcomes):
            raise EvaluationError("outcomes contain another document ID")

    @property
    def match_records(self) -> tuple[MatchOutcome, ...]:
        """Alias used by reporting consumers."""

        return self.outcomes

    @property
    def true_positives(self) -> int:
        """Return pair-level true-positive count."""

        return sum(outcome.status == "tp" for outcome in self.outcomes)

    @property
    def false_positives(self) -> int:
        """Return pair-level false-positive count."""

        return sum(outcome.status == "fp" for outcome in self.outcomes)

    @property
    def false_negatives(self) -> int:
        """Return pair-level false-negative count."""

        return sum(outcome.status == "fn" for outcome in self.outcomes)

    @property
    def unscoreable(self) -> int:
        """Return annotations explicitly excluded from pair scoring."""

        return sum(outcome.status == "unscoreable" for outcome in self.outcomes)

    @property
    def tp(self) -> int:
        """Short alias for :attr:`true_positives`."""

        return self.true_positives

    @property
    def fp(self) -> int:
        """Short alias for :attr:`false_positives`."""

        return self.false_positives

    @property
    def fn(self) -> int:
        """Short alias for :attr:`false_negatives`."""

        return self.false_negatives


MatchResult = DocumentEvaluation


@dataclass(frozen=True, slots=True)
class MetricResult:
    """Named metric values with stable ordering and JSON-friendly access."""

    name: str
    values: tuple[tuple[str, int | float], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Metric name must not be empty")
        if not isinstance(self.values, tuple):
            raise TypeError("Metric values must be a tuple of name/value pairs")
        keys = [key for key, _ in self.values]
        if len(set(keys)) != len(keys):
            raise ValueError("Metric value names must be unique")
        if any(not isinstance(key, str) or not key.strip() for key in keys):
            raise ValueError("Metric value names must be non-empty strings")
        for key, value in self.values:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"Metric value {key!r} must be numeric")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Metric value {key!r} must be finite")

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-compatible metric mapping."""

        return {"name": self.name, "values": dict(self.values)}

    def value(self, key: str) -> int | float:
        """Return one named value or raise an actionable error."""

        for name, value in self.values:
            if name == key:
                return value
        raise KeyError(f"Metric {self.name!r} has no value {key!r}")

    @property
    def precision(self) -> float:
        """Return pair precision."""

        return float(self.value("precision"))

    @property
    def recall(self) -> float:
        """Return pair recall."""

        return float(self.value("recall"))

    @property
    def f1(self) -> float:
        """Return pair F1."""

        return float(self.value("f1"))

    @property
    def tp(self) -> int:
        """Return aggregate true positives."""

        return int(self.value("tp"))

    @property
    def fp(self) -> int:
        """Return aggregate false positives."""

        return int(self.value("fp"))

    @property
    def fn(self) -> int:
        """Return aggregate false negatives."""

        return int(self.value("fn"))


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Complete deterministic evaluator output."""

    matching_policy: str
    matching_policy_version: str
    documents: tuple[DocumentEvaluation, ...]
    metrics: tuple[MetricResult, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.matching_policy, str)
            or not self.matching_policy.strip()
            or not isinstance(self.matching_policy_version, str)
            or not self.matching_policy_version.strip()
        ):
            raise ValueError("Matching policy identity and version must not be empty")
        if not isinstance(self.documents, tuple) or any(
            not isinstance(value, DocumentEvaluation) for value in self.documents
        ):
            raise TypeError("documents must be a tuple of DocumentEvaluation values")
        if not isinstance(self.metrics, tuple) or any(
            not isinstance(value, MetricResult) for value in self.metrics
        ):
            raise TypeError("metrics must be a tuple of MetricResult values")

    @property
    def document_records(self) -> tuple[DocumentEvaluation, ...]:
        """Alias for consumers that call per-document values records."""

        return self.documents

    @property
    def match_records(self) -> tuple[MatchOutcome, ...]:
        """Flatten detailed outcomes in deterministic document order."""

        return tuple(
            outcome for document in self.documents for outcome in document.outcomes
        )

    def metric(self, name: str) -> MetricResult:
        """Return a named metric result."""

        for metric in self.metrics:
            if metric.name == name:
                return metric
        raise KeyError(f"Evaluation has no metric {name!r}")


@runtime_checkable
class MatchingPolicy(Protocol):
    """Named strategy that pairs annotations for one document."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def match(
        self,
        document_id: str,
        gold_annotations: Iterable[AbbreviationDefinition],
        predictions: Iterable[AbbreviationDefinition],
    ) -> DocumentEvaluation:
        """Return deterministic detailed outcomes for one document."""


@runtime_checkable
class Metric(Protocol):
    """Named strategy that aggregates per-document match outcomes."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def compute(self, documents: Iterable[DocumentEvaluation]) -> MetricResult:
        """Compute one metric without modifying evaluation records."""


__all__ = [
    "DocumentEvaluation",
    "EvaluationError",
    "EvaluationResult",
    "MatchOutcome",
    "MatchResult",
    "MatchStatus",
    "MatchingPolicy",
    "Metric",
    "MetricResult",
]
