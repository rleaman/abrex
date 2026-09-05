"""Deterministic, format-neutral projections used by reporters."""

from __future__ import annotations

from collections import Counter
from typing import Any

from abrex.evaluation import DocumentEvaluation, MatchOutcome
from abrex.reporting.base import ReportContext


def span_dict(span: Any) -> dict[str, int] | None:
    return None if span is None else {"start": span.start, "end": span.end}


def definition_dict(annotation: Any) -> dict[str, object] | None:
    if annotation is None:
        return None
    return {
        "document_id": annotation.document_id,
        "short_form": span_dict(annotation.short_form),
        "long_form": span_dict(annotation.long_form),
        "short_form_text": annotation.short_form_text,
        "long_form_text": annotation.long_form_text,
    }


def outcome_dict(outcome: MatchOutcome) -> dict[str, object]:
    return {
        "document_id": outcome.document_id,
        "status": outcome.status,
        "gold_index": outcome.gold_index,
        "prediction_index": outcome.prediction_index,
        "gold": definition_dict(outcome.gold),
        "prediction": definition_dict(outcome.prediction),
    }


def outcome_rows(context: ReportContext) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for document in context.evaluation.documents:
        for outcome in document.outcomes:
            row = outcome_dict(outcome)
            for dimension in context.dimensions:
                value = dimension.classify(outcome.document_id, outcome)
                if value is not None:
                    row[f"stratum:{dimension.identity}"] = value
            rows.append(row)
    return tuple(rows)


def strata(context: ReportContext) -> dict[str, dict[str, dict[str, int]]]:
    result: dict[str, dict[str, dict[str, int]]] = {}
    for dimension in context.dimensions:
        counts: Counter[tuple[str, str]] = Counter()
        for document in context.evaluation.documents:
            for outcome in document.outcomes:
                value = dimension.classify(document.document_id, outcome)
                if value is not None:
                    counts[(value, outcome.status)] += 1
        result[dimension.identity] = {
            value: {
                status: counts[(value, status)]
                for status in ("tp", "fp", "fn", "unscoreable")
            }
            for value in sorted({key[0] for key in counts})
        }
    return result


def metadata_dict(context: ReportContext) -> dict[str, object]:
    return {
        "matching_policy": {
            "key": context.evaluation.matching_policy,
            "version": context.evaluation.matching_policy_version,
        },
        "run": dict(context.metadata),
        "configuration": dict(context.configuration),
    }


def metric_dicts(context: ReportContext) -> list[dict[str, object]]:
    return [metric.to_dict() for metric in context.evaluation.metrics]


def document_count_by_status(document: DocumentEvaluation) -> dict[str, int]:
    return {
        status: sum(outcome.status == status for outcome in document.outcomes)
        for status in ("tp", "fp", "fn", "unscoreable")
    }
