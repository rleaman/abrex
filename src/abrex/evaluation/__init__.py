"""Registry-driven exact evaluation and pair/span-level metrics."""

from abrex.evaluation.base import (
    DocumentEvaluation,
    EvaluationError,
    EvaluationResult,
    MatchingPolicy,
    MatchOutcome,
    MatchResult,
    MatchStatus,
    Metric,
    MetricResult,
)
from abrex.evaluation.config import (
    EvaluationConfig,
    create_evaluator,
    evaluation_config_from_resolved,
)
from abrex.evaluation.evaluator import (
    EvaluationService,
    Evaluator,
    PredictionBatchLike,
    PredictionRecordLike,
)
from abrex.evaluation.matching import (
    ExactPairConfig,
    ExactPairMatchingPolicy,
    ExactPairPolicy,
    ExactSpanConfig,
    ExactSpanMatchingPolicy,
    ExactSpanPolicy,
    IncompleteHandling,
)
from abrex.evaluation.metrics import (
    MetricError,
    PairPRF,
    PairPRFConfig,
    PairPRFMetric,
    SpanPRF,
    SpanPRFConfig,
    SpanPRFMetric,
    ZeroDivisionHandling,
)
from abrex.evaluation.registry import (
    MATCHING_POLICIES,
    METRICS,
    register_builtin_components,
)

__all__ = [
    "DocumentEvaluation",
    "EvaluationConfig",
    "EvaluationError",
    "EvaluationResult",
    "EvaluationService",
    "ExactPairConfig",
    "ExactPairMatchingPolicy",
    "ExactPairPolicy",
    "ExactSpanConfig",
    "ExactSpanMatchingPolicy",
    "ExactSpanPolicy",
    "Evaluator",
    "IncompleteHandling",
    "MATCHING_POLICIES",
    "METRICS",
    "MatchOutcome",
    "MatchResult",
    "MatchStatus",
    "MatchingPolicy",
    "Metric",
    "MetricError",
    "MetricResult",
    "PairPRF",
    "PairPRFConfig",
    "PairPRFMetric",
    "SpanPRF",
    "SpanPRFConfig",
    "SpanPRFMetric",
    "PredictionBatchLike",
    "PredictionRecordLike",
    "ZeroDivisionHandling",
    "create_evaluator",
    "evaluation_config_from_resolved",
    "register_builtin_components",
]
