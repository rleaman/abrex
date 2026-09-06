"""Matching policies for pairing gold and predicted definitions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict

from abrex.domain import AbbreviationDefinition, TextSpan
from abrex.evaluation.base import DocumentEvaluation, EvaluationError, MatchOutcome

IncompleteHandling = Literal["unscoreable"]


class ExactPairConfig(BaseModel):
    """Explicit policy for incomplete annotations under exact matching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    incomplete_gold: IncompleteHandling = "unscoreable"
    incomplete_prediction: IncompleteHandling = "unscoreable"


class ExactPairMatchingPolicy:
    """Match equal document IDs and equal complete short/long spans exactly.

    Exact matching partitions annotations by the complete pair key. Pairing
    within each partition is a deterministic maximum-cardinality assignment;
    duplicate annotations are retained, so surplus duplicates become explicit
    false positives or false negatives.
    """

    identity = "exact_pair"
    version = "1"

    def __init__(
        self,
        incomplete_gold: IncompleteHandling = "unscoreable",
        incomplete_prediction: IncompleteHandling = "unscoreable",
    ) -> None:
        ExactPairConfig(
            incomplete_gold=incomplete_gold,
            incomplete_prediction=incomplete_prediction,
        )
        self.incomplete_gold = incomplete_gold
        self.incomplete_prediction = incomplete_prediction

    def match(
        self,
        document_id: str,
        gold_annotations: Iterable[AbbreviationDefinition],
        predictions: Iterable[AbbreviationDefinition],
    ) -> DocumentEvaluation:
        """Return order-invariant exact matching outcomes for one document."""

        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        gold = tuple(gold_annotations)
        predicted = tuple(predictions)
        _validate_annotations(document_id, gold, "gold_annotations")
        _validate_annotations(document_id, predicted, "predictions")

        ordered_gold = tuple(sorted(gold, key=_definition_sort_key))
        ordered_predictions = tuple(sorted(predicted, key=_definition_sort_key))
        gold_groups: dict[
            tuple[object, ...], list[tuple[int, AbbreviationDefinition]]
        ] = defaultdict(list)
        prediction_groups: dict[
            tuple[object, ...], list[tuple[int, AbbreviationDefinition]]
        ] = defaultdict(list)
        outcomes: list[MatchOutcome] = []

        for index, annotation in enumerate(ordered_gold):
            key = _pair_key(annotation)
            if key is None:
                outcomes.append(
                    MatchOutcome(
                        document_id,
                        "unscoreable",
                        gold=annotation,
                        gold_index=index,
                    )
                )
            else:
                gold_groups[key].append((index, annotation))
        for index, annotation in enumerate(ordered_predictions):
            key = _pair_key(annotation)
            if key is None:
                outcomes.append(
                    MatchOutcome(
                        document_id,
                        "unscoreable",
                        prediction=annotation,
                        prediction_index=index,
                    )
                )
            else:
                prediction_groups[key].append((index, annotation))

        for key in sorted(set(gold_groups) | set(prediction_groups), key=repr):
            gold_group = gold_groups.get(key, [])
            prediction_group = prediction_groups.get(key, [])
            common = min(len(gold_group), len(prediction_group))
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "tp",
                    gold=gold_group[index][1],
                    prediction=prediction_group[index][1],
                    gold_index=gold_group[index][0],
                    prediction_index=prediction_group[index][0],
                )
                for index in range(common)
            )
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "fn",
                    gold=gold_group[index][1],
                    gold_index=gold_group[index][0],
                )
                for index in range(common, len(gold_group))
            )
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "fp",
                    prediction=prediction_group[index][1],
                    prediction_index=prediction_group[index][0],
                )
                for index in range(common, len(prediction_group))
            )

        ordered_outcomes = tuple(sorted(outcomes, key=_outcome_sort_key))
        return DocumentEvaluation(
            document_id,
            gold_annotations=ordered_gold,
            predictions=ordered_predictions,
            outcomes=ordered_outcomes,
        )


ExactPairPolicy = ExactPairMatchingPolicy


class ExactSpanConfig(BaseModel):
    """Configuration for independent exact short/long span matching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    include_short: bool = True
    include_long: bool = True


class ExactSpanMatchingPolicy:
    """Match short and long spans independently and exactly.

    This policy is intended for sources such as SDU@AAAI-22 AE whose acronym
    and long-form lists are independent and do not establish pair relations.
    Paired annotations are projected into one single-form annotation per
    populated side; no relationship between the two sides is inferred.
    """

    identity = "exact_span"
    version = "1"

    def __init__(self, include_short: bool = True, include_long: bool = True) -> None:
        config = ExactSpanConfig(include_short=include_short, include_long=include_long)
        if not config.include_short and not config.include_long:
            raise ValueError("At least one independent span kind must be included")
        self.include_short = config.include_short
        self.include_long = config.include_long

    def match(
        self,
        document_id: str,
        gold_annotations: Iterable[AbbreviationDefinition],
        predictions: Iterable[AbbreviationDefinition],
    ) -> DocumentEvaluation:
        """Return deterministic one-to-one matches for each independent span."""

        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        gold = tuple(gold_annotations)
        predicted = tuple(predictions)
        _validate_annotations(document_id, gold, "gold_annotations")
        _validate_annotations(document_id, predicted, "predictions")
        ordered_gold = tuple(
            sorted(
                _project_spans(
                    gold,
                    include_short=self.include_short,
                    include_long=self.include_long,
                ),
                key=_definition_sort_key,
            )
        )
        ordered_predictions = tuple(
            sorted(
                _project_spans(
                    predicted,
                    include_short=self.include_short,
                    include_long=self.include_long,
                ),
                key=_definition_sort_key,
            )
        )
        gold_groups: dict[
            tuple[object, ...], list[tuple[int, AbbreviationDefinition]]
        ] = defaultdict(list)
        prediction_groups: dict[
            tuple[object, ...], list[tuple[int, AbbreviationDefinition]]
        ] = defaultdict(list)
        outcomes: list[MatchOutcome] = []

        for index, annotation in enumerate(ordered_gold):
            key = _span_match_key(annotation)
            if key is None:
                outcomes.append(
                    MatchOutcome(
                        document_id,
                        "unscoreable",
                        gold=annotation,
                        gold_index=index,
                    )
                )
            else:
                gold_groups[key].append((index, annotation))
        for index, annotation in enumerate(ordered_predictions):
            key = _span_match_key(annotation)
            if key is None:
                outcomes.append(
                    MatchOutcome(
                        document_id,
                        "unscoreable",
                        prediction=annotation,
                        prediction_index=index,
                    )
                )
            else:
                prediction_groups[key].append((index, annotation))

        for key in sorted(set(gold_groups) | set(prediction_groups), key=repr):
            gold_group = gold_groups.get(key, [])
            prediction_group = prediction_groups.get(key, [])
            common = min(len(gold_group), len(prediction_group))
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "tp",
                    gold=gold_group[index][1],
                    prediction=prediction_group[index][1],
                    gold_index=gold_group[index][0],
                    prediction_index=prediction_group[index][0],
                )
                for index in range(common)
            )
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "fn",
                    gold=gold_group[index][1],
                    gold_index=gold_group[index][0],
                )
                for index in range(common, len(gold_group))
            )
            outcomes.extend(
                MatchOutcome(
                    document_id,
                    "fp",
                    prediction=prediction_group[index][1],
                    prediction_index=prediction_group[index][0],
                )
                for index in range(common, len(prediction_group))
            )

        return DocumentEvaluation(
            document_id,
            gold_annotations=ordered_gold,
            predictions=ordered_predictions,
            outcomes=tuple(sorted(outcomes, key=_outcome_sort_key)),
        )


ExactSpanPolicy = ExactSpanMatchingPolicy


def _project_spans(
    annotations: tuple[AbbreviationDefinition, ...],
    *,
    include_short: bool,
    include_long: bool,
) -> tuple[AbbreviationDefinition, ...]:
    projected: list[AbbreviationDefinition] = []
    for annotation in annotations:
        if include_short and annotation.short_form is not None:
            projected.append(
                replace(
                    annotation,
                    long_form=None,
                    long_form_text=None,
                )
            )
        if include_long and annotation.long_form is not None:
            projected.append(
                replace(
                    annotation,
                    short_form=None,
                    short_form_text=None,
                )
            )
        if annotation.short_form is None and annotation.long_form is None:
            projected.append(annotation)
    return tuple(projected)


def _span_match_key(
    annotation: AbbreviationDefinition,
) -> tuple[object, ...] | None:
    if annotation.short_form is not None and annotation.long_form is None:
        return (
            annotation.document_id,
            "short",
            _span_key(annotation.short_form),
        )
    if annotation.long_form is not None and annotation.short_form is None:
        return (
            annotation.document_id,
            "long",
            _span_key(annotation.long_form),
        )
    return None


def _validate_annotations(
    document_id: str,
    annotations: tuple[AbbreviationDefinition, ...],
    field_name: str,
) -> None:
    if any(
        not isinstance(annotation, AbbreviationDefinition) for annotation in annotations
    ):
        raise TypeError(f"{field_name} must contain AbbreviationDefinition values")
    if any(annotation.document_id != document_id for annotation in annotations):
        raise EvaluationError(f"{field_name} contains another document ID")


def _pair_key(annotation: AbbreviationDefinition) -> tuple[object, ...] | None:
    if annotation.short_form is None or annotation.long_form is None:
        return None
    return (
        annotation.document_id,
        _span_key(annotation.short_form),
        _span_key(annotation.long_form),
    )


def _span_key(span: TextSpan | None) -> tuple[int, int] | None:
    return None if span is None else (span.start, span.end)


def _definition_sort_key(
    annotation: AbbreviationDefinition,
) -> tuple[object, ...]:
    return (
        annotation.document_id,
        repr(_span_key(annotation.short_form)),
        repr(_span_key(annotation.long_form)),
        repr(annotation.short_form_text),
        repr(annotation.long_form_text),
        repr(annotation.provenance),
        repr(annotation.prediction),
    )


def _outcome_sort_key(outcome: MatchOutcome) -> tuple[object, ...]:
    status_order = {"tp": 0, "fn": 1, "fp": 2, "unscoreable": 3}
    return (
        status_order[outcome.status],
        outcome.gold_index if outcome.gold_index is not None else -1,
        outcome.prediction_index if outcome.prediction_index is not None else -1,
        _definition_sort_key(outcome.gold) if outcome.gold is not None else (),
        _definition_sort_key(outcome.prediction)
        if outcome.prediction is not None
        else (),
    )


__all__ = [
    "ExactPairConfig",
    "ExactPairMatchingPolicy",
    "ExactPairPolicy",
    "IncompleteHandling",
]
