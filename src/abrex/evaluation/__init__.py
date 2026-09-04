"""Registry-driven exact evaluation and pair-level metrics."""

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
    PredictionRecordLike,
)
from abrex.evaluation.matching import (
    ExactPairConfig,
    ExactPairMatchingPolicy,
    ExactPairPolicy,
    IncompleteHandling,
)
from abrex.evaluation.metrics import (
    MetricError,
    PairPRF,
    PairPRFConfig,
    PairPRFMetric,
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
    "PredictionRecordLike",
    "ZeroDivisionHandling",
    "create_evaluator",
    "evaluation_config_from_resolved",
    "register_builtin_components",
]
