"""Comparative resolver analysis with explicit oracle and uncertainty limits."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from abrex.domain import AbbreviationDefinition, CorpusRecord, TextSpan
from abrex.evaluation.base import (
    DocumentEvaluation,
    EvaluationResult,
    MatchingPolicy,
    Metric,
)
from abrex.evaluation.evaluator import Evaluator
from abrex.evaluation.matching import ExactPairMatchingPolicy, ExactSpanMatchingPolicy
from abrex.evaluation.metrics import PairPRFMetric, SpanPRFMetric
from abrex.resolvers.base import PredictionRecord

AnalysisMode = Literal["exact_pair", "exact_span"]


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """Seeded percentile interval over document/article-group resamples."""

    samples: int
    seed: int
    unit: str
    precision_low: float
    precision_high: float
    recall_low: float
    recall_high: float
    f1_low: float
    f1_high: float


@dataclass(frozen=True, slots=True)
class ResolverComparison:
    """One resolver's standalone evaluation and complementary successes."""

    resolver: str
    evaluation: EvaluationResult
    scoreable_gold: int
    correct_keys: frozenset[tuple[object, ...]]
    bootstrap: BootstrapInterval

    def to_dict(self) -> dict[str, object]:
        metric = self.evaluation.metrics[0].to_dict()
        return {
            "resolver": self.resolver,
            "matching_policy": self.evaluation.matching_policy,
            "metric": metric,
            "scoreable_gold": self.scoreable_gold,
            "correct_count": len(self.correct_keys),
            "bootstrap": {
                "samples": self.bootstrap.samples,
                "seed": self.bootstrap.seed,
                "unit": self.bootstrap.unit,
                "precision": [
                    self.bootstrap.precision_low,
                    self.bootstrap.precision_high,
                ],
                "recall": [self.bootstrap.recall_low, self.bootstrap.recall_high],
                "f1": [self.bootstrap.f1_low, self.bootstrap.f1_high],
            },
        }


@dataclass(frozen=True, slots=True)
class ComparativeReport:
    """Comparison results; pair and span reports cannot be merged."""

    mode: AnalysisMode
    resolver_results: tuple[ResolverComparison, ...]
    union_correct_keys: frozenset[tuple[object, ...]]
    unique_correct_keys: tuple[tuple[str, frozenset[tuple[object, ...]]], ...]
    oracle_recall: float
    oracle_denominator: int
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "comparative-analysis-v1",
            "mode": self.mode,
            "resolver_results": [item.to_dict() for item in self.resolver_results],
            "union": {
                "correct_count": len(self.union_correct_keys),
                "oracle_recall": self.oracle_recall,
                "oracle_denominator": self.oracle_denominator,
            },
            "unique_correct": [
                {"resolver": name, "count": len(keys)}
                for name, keys in self.unique_correct_keys
            ],
            "limitations": list(self.limitations),
        }


def write_comparative_report(path: Path, report: ComparativeReport) -> str:
    """Write a deterministic JSON evidence report and return its SHA-256."""

    serialized = (
        json.dumps(
            report.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    )
    path.write_text(serialized, encoding="utf-8", newline="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compare_resolvers(
    gold_records: Sequence[CorpusRecord],
    predictions: Mapping[str, Sequence[PredictionRecord]],
    *,
    mode: AnalysisMode = "exact_pair",
    group_by_document: Mapping[str, str] | None = None,
    bootstrap_samples: int = 1000,
    seed: int = 0,
) -> ComparativeReport:
    """Compare resolvers on one document universe under one metric contract.

    ``predictions`` must contain a complete successful record for every gold
    document. Execution failures are rejected by :class:`Evaluator`; they are
    never silently interpreted as empty output. The oracle is gold-assisted and
    is reported only as attainable union recall.
    """

    if not predictions:
        raise ValueError("At least one resolver prediction set is required")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    policy, metric = _plugins(mode)
    groups = _groups(gold_records, group_by_document)
    results: list[ResolverComparison] = []
    for name in sorted(predictions):
        evaluation = Evaluator(policy, (metric,)).evaluate(
            gold_records, predictions[name]
        )
        correct = _correct_keys(evaluation.documents, mode)
        scoreable = _scoreable_gold(evaluation.documents, mode)
        results.append(
            ResolverComparison(
                name,
                evaluation,
                scoreable,
                frozenset(correct),
                _bootstrap(
                    evaluation.documents,
                    groups,
                    mode,
                    bootstrap_samples,
                    _resolver_seed(seed, name),
                ),
            )
        )
    union = frozenset().union(*(item.correct_keys for item in results))
    unique = tuple(
        (
            item.resolver,
            frozenset(
                key
                for key in item.correct_keys
                if not any(
                    key in other.correct_keys
                    for other in results
                    if other.resolver != item.resolver
                )
            ),
        )
        for item in results
    )
    denominator = _scoreable_gold(results[0].evaluation.documents, mode)
    limitations = (
        "Gold-assisted union recall is an oracle analysis, not a deployable "
        "resolver score.",
        "Results are valid only for the supplied document universe and "
        "matching policy.",
        "Pair and span metrics must be reported in separate analyses and are "
        "never pooled.",
    )
    return ComparativeReport(
        mode,
        tuple(results),
        union,
        unique,
        len(union) / denominator if denominator else 0.0,
        denominator,
        limitations,
    )


def _plugins(mode: AnalysisMode) -> tuple[MatchingPolicy, Metric]:
    if mode == "exact_pair":
        return ExactPairMatchingPolicy(), PairPRFMetric()
    if mode == "exact_span":
        return ExactSpanMatchingPolicy(), SpanPRFMetric()
    raise ValueError(f"Unsupported comparative analysis mode: {mode!r}")


def _correct_keys(
    documents: Sequence[DocumentEvaluation], mode: AnalysisMode
) -> set[tuple[object, ...]]:
    keys: set[tuple[object, ...]] = set()
    for document in documents:
        for outcome in document.outcomes:
            if outcome.status != "tp":
                continue
            annotation = outcome.gold
            if annotation is None:
                continue
            if mode == "exact_pair":
                if (
                    annotation.short_form is not None
                    and annotation.long_form is not None
                ):
                    keys.add(_occurrence_key(_pair_key(annotation), outcome.gold_index))
            else:
                if annotation.short_form is not None:
                    keys.add(
                        _occurrence_key(
                            (
                                annotation.document_id,
                                "short",
                                _span_key(annotation.short_form),
                            ),
                            outcome.gold_index,
                        )
                    )
                if annotation.long_form is not None:
                    keys.add(
                        _occurrence_key(
                            (
                                annotation.document_id,
                                "long",
                                _span_key(annotation.long_form),
                            ),
                            outcome.gold_index,
                        )
                    )
    return keys


def _scoreable_gold(documents: Sequence[DocumentEvaluation], mode: AnalysisMode) -> int:
    if mode == "exact_pair":
        return sum(
            1
            for document in documents
            for annotation in document.gold_annotations
            if annotation.short_form is not None and annotation.long_form is not None
        )
    return sum(
        sum(
            annotation.short_form is not None
            for annotation in document.gold_annotations
        )
        + sum(
            annotation.long_form is not None for annotation in document.gold_annotations
        )
        for document in documents
    )


def _pair_key(annotation: AbbreviationDefinition) -> tuple[object, ...]:
    if annotation.short_form is None or annotation.long_form is None:
        raise ValueError("Pair key requires complete spans")
    return (
        annotation.document_id,
        _span_key(annotation.short_form),
        _span_key(annotation.long_form),
    )


def _span_key(span: TextSpan) -> tuple[int, int]:
    return span.start, span.end


def _occurrence_key(
    key: tuple[object, ...], occurrence: int | None
) -> tuple[object, ...]:
    return key + (occurrence,)


def _groups(
    gold_records: Sequence[CorpusRecord], group_by_document: Mapping[str, str] | None
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for record in gold_records:
        document_id = record.document.document_id
        group = (
            group_by_document.get(document_id, document_id)
            if group_by_document
            else document_id
        )
        grouped.setdefault(group, []).append(document_id)
    return {key: tuple(sorted(value)) for key, value in sorted(grouped.items())}


def _bootstrap(
    documents: Sequence[DocumentEvaluation],
    groups: Mapping[str, tuple[str, ...]],
    mode: AnalysisMode,
    samples: int,
    seed: int,
) -> BootstrapInterval:
    by_id = {document.document_id: document for document in documents}
    rng = random.Random(seed)
    names = tuple(groups)
    values: list[tuple[float, float, float]] = []
    for _ in range(samples):
        selected = [
            by_id[document_id]
            for group in rng.choices(names, k=len(names))
            for document_id in groups[group]
        ]
        tp = sum(_counts(document, mode)[0] for document in selected)
        fp = sum(_counts(document, mode)[1] for document in selected)
        fn = sum(_counts(document, mode)[2] for document in selected)
        values.append(
            (_ratio(tp, tp + fp), _ratio(tp, tp + fn), _ratio(2 * tp, 2 * tp + fp + fn))
        )
    return BootstrapInterval(
        samples,
        seed,
        "article_group",
        _percentile(values, 0),
        _percentile(values, 1),
        _percentile(values, 2),
        _percentile(values, 3),
        _percentile(values, 4),
        _percentile(values, 5),
    )


def _counts(document: DocumentEvaluation, mode: AnalysisMode) -> tuple[int, int, int]:
    if mode == "exact_pair":
        return document.tp, document.fp, document.fn
    # Exact-span evaluation stores projected outcomes in the same fields.
    return document.tp, document.fp, document.fn


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _percentile(values: Sequence[tuple[float, float, float]], index: int) -> float:
    ordered = sorted(value[index // 2] for value in values)
    position = 0.025 if index % 2 == 0 else 0.975
    offset = min(len(ordered) - 1, int(position * (len(ordered) - 1)))
    return ordered[offset]


def _resolver_seed(seed: int, resolver: str) -> int:
    digest = hashlib.sha256(f"{seed}:{resolver}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


__all__ = [
    "BootstrapInterval",
    "ComparativeReport",
    "ResolverComparison",
    "compare_resolvers",
    "write_comparative_report",
]
