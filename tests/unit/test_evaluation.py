"""Unit and contract tests for exact evaluation and pair-level metrics."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

import pytest
from pydantic import ValidationError

from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import AbbreviationDefinition, CorpusRecord, Document, TextSpan
from abrex.evaluation import (
    MATCHING_POLICIES,
    METRICS,
    DocumentEvaluation,
    EvaluationConfig,
    EvaluationError,
    EvaluationResult,
    Evaluator,
    ExactPairMatchingPolicy,
    MatchingPolicy,
    MatchOutcome,
    Metric,
    MetricError,
    MetricResult,
    PairPRFMetric,
    PredictionRecordLike,
    create_evaluator,
    evaluation_config_from_resolved,
)
from abrex.registry import Registry
from abrex.resolvers import PredictionRecord


def annotation(
    document_id: str,
    short: tuple[int, int] | None,
    long: tuple[int, int] | None,
) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        document_id,
        TextSpan(*short) if short is not None else None,
        TextSpan(*long) if long is not None else None,
    )


def test_exact_pair_matches_only_complete_exact_spans_and_is_order_invariant() -> None:
    policy = ExactPairMatchingPolicy()
    gold = (
        annotation("doc", (0, 3), (4, 10)),
        annotation("doc", (20, 23), (24, 30)),
        annotation("doc", (40, 43), (44, 50)),
    )
    predictions = (
        annotation("doc", (20, 23), (24, 30)),
        annotation("doc", (0, 3), (4, 11)),
        annotation("doc", (60, 63), (64, 70)),
        annotation("doc", (40, 43), (44, 50)),
    )

    result = policy.match("doc", reversed(gold), reversed(predictions))
    assert (
        result.gold_annotations == tuple(sorted(gold, key=repr))
        or len(result.gold_annotations) == 3
    )
    assert result.tp == 2
    assert result.fp == 2
    assert result.fn == 1
    assert [outcome.status for outcome in result.outcomes] == [
        "tp",
        "tp",
        "fn",
        "fp",
        "fp",
    ]
    assert all(outcome.document_id == "doc" for outcome in result.outcomes)

    same = policy.match("doc", gold, predictions)
    assert result == same
    assert result.outcomes[0].gold_annotation == result.outcomes[0].gold
    assert result.outcomes[0].predicted_annotation == result.outcomes[0].prediction


def test_exact_pair_retains_duplicate_predictions_and_gold_assignments() -> None:
    policy = ExactPairMatchingPolicy()
    pair = annotation("doc", (0, 2), (3, 8))
    extra_gold = annotation("doc", (10, 12), (13, 18))

    duplicate_predictions = policy.match("doc", (pair,), (pair, pair))
    assert duplicate_predictions.tp == 1
    assert duplicate_predictions.fp == 1
    assert duplicate_predictions.fn == 0
    assert [outcome.status for outcome in duplicate_predictions.outcomes] == [
        "tp",
        "fp",
    ]

    duplicate_gold = policy.match("doc", (pair, pair), (pair,))
    assert duplicate_gold.tp == 1
    assert duplicate_gold.fn == 1
    assert duplicate_gold.fp == 0

    multi = policy.match("doc", (pair, extra_gold), (extra_gold, pair))
    assert multi.tp == 2
    assert (
        multi.outcomes
        == policy.match("doc", (extra_gold, pair), (pair, extra_gold)).outcomes
    )


def test_exact_pair_handles_empty_repeated_text_and_crossing_spans() -> None:
    policy = ExactPairMatchingPolicy()
    empty = policy.match("empty", (), ())
    assert empty.outcomes == ()

    repeated_left = annotation("doc", (0, 2), (3, 8))
    repeated_right = annotation("doc", (20, 22), (23, 28))
    crossing = annotation("doc", (0, 2), (23, 28))
    result = policy.match(
        "doc", (repeated_left, repeated_right), (crossing, repeated_right)
    )
    assert result.tp == 1
    assert result.fp == 1
    assert result.fn == 1


def test_incomplete_annotations_are_explicitly_unscoreable() -> None:
    policy = ExactPairMatchingPolicy()
    incomplete_gold = annotation("doc", None, (0, 3))
    incomplete_prediction = annotation("doc", (4, 5), None)
    result = policy.match("doc", (incomplete_gold,), (incomplete_prediction,))
    assert result.unscoreable == 2
    assert result.tp == result.fp == result.fn == 0
    assert any(outcome.gold is not None for outcome in result.outcomes)
    assert any(outcome.prediction is not None for outcome in result.outcomes)


def test_exact_pair_rejects_bad_inputs_and_config_is_explicit() -> None:
    policy = ExactPairMatchingPolicy()
    with pytest.raises(ValueError, match="document_id"):
        policy.match(" ", (), ())
    with pytest.raises(TypeError, match="gold_annotations"):
        policy.match("doc", (cast(Any, object()),), ())
    with pytest.raises(EvaluationError, match="another document"):
        policy.match("doc", (annotation("other", (0, 1), (1, 2)),), ())
    with pytest.raises(TypeError, match="predictions"):
        policy.match("doc", (), (cast(Any, object()),))
    with pytest.raises(ValidationError):
        ExactPairMatchingPolicy(cast(Any, "raise"))


def test_match_outcome_and_document_evaluation_invariants_and_aliases() -> None:
    gold = annotation("doc", (0, 1), (1, 2))
    pred = annotation("doc", (0, 1), (1, 2))
    tp = MatchOutcome("doc", "tp", gold, pred, 0, 0)
    assert tp.is_true_positive
    assert tp.kind == "tp"
    with pytest.raises(EvaluationError, match="Prediction document ID"):
        MatchOutcome("doc", "fp", prediction=annotation("other", (0, 1), (1, 2)))
    with pytest.raises(ValueError, match="document_id"):
        MatchOutcome(" ", "tp", gold, pred)
    with pytest.raises(ValueError, match="status"):
        MatchOutcome("doc", cast(Any, "bad"), gold, pred)
    for status, values, match in (
        ("tp", (None, pred), "true-positive"),
        ("fp", (gold, pred), "false-positive"),
        ("fn", (gold, pred), "false-negative"),
        ("unscoreable", (gold, pred), "exactly one"),
    ):
        with pytest.raises(ValueError, match=match):
            MatchOutcome("doc", cast(Any, status), values[0], values[1])
    with pytest.raises(ValueError, match="gold_index"):
        MatchOutcome("doc", "tp", gold, pred, -1, 0)
    with pytest.raises(EvaluationError, match="document ID"):
        MatchOutcome("doc", "tp", annotation("other", (0, 1), (1, 2)), pred)
    with pytest.raises(TypeError, match="gold"):
        MatchOutcome("doc", "fp", cast(Any, object()), pred)

    document = DocumentEvaluation("doc", (gold,), (pred,), (tp,))
    assert document.match_records == (tp,)
    assert document.document_id == "doc"
    assert document.tp == document.true_positives == 1
    assert document.fp == document.fn == document.unscoreable == 0
    with pytest.raises(TypeError, match="gold_annotations"):
        DocumentEvaluation("doc", cast(Any, [gold]), (), ())
    with pytest.raises(EvaluationError, match="another document"):
        DocumentEvaluation("doc", (annotation("other", (0, 1), (1, 2)),), (), ())
    with pytest.raises(ValueError, match="document_id"):
        DocumentEvaluation(" ")
    with pytest.raises(TypeError, match="outcomes"):
        DocumentEvaluation("doc", (), (), cast(Any, [tp]))
    other_outcome = MatchOutcome("other", "fn", annotation("other", (0, 1), (1, 2)))
    with pytest.raises(EvaluationError, match="outcomes"):
        DocumentEvaluation("doc", (), (), (other_outcome,))


def test_pair_prf_micro_metric_and_zero_denominator_behavior() -> None:
    gold = annotation("doc", (0, 1), (1, 2))
    pred = annotation("doc", (0, 1), (1, 2))
    documents = (
        DocumentEvaluation(
            "doc",
            (gold,),
            (pred,),
            (MatchOutcome("doc", "tp", gold, pred),),
        ),
        DocumentEvaluation(
            "other",
            (gold := annotation("other", (0, 1), (1, 2)),),
            (),
            (MatchOutcome("other", "fn", gold),),
        ),
        DocumentEvaluation(
            "third",
            (),
            (pred := annotation("third", (0, 1), (1, 2)),),
            (MatchOutcome("third", "fp", prediction=pred),),
        ),
    )
    metric = PairPRFMetric()
    result = metric.compute(reversed(documents))
    assert result.name == "pair_prf"
    assert result.tp == 1 and result.fp == 1 and result.fn == 1
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.f1 == pytest.approx(0.5)
    assert result.to_dict()["values"]["f1"] == pytest.approx(0.5)  # type: ignore[index]
    assert result.value("tp") == 1
    with pytest.raises(KeyError, match="missing"):
        result.value("missing")
    with pytest.raises(TypeError, match="DocumentEvaluation"):
        metric.compute((cast(Any, object()),))

    empty = metric.compute(())
    assert empty.precision == empty.recall == empty.f1 == 0.0
    with pytest.raises(MetricError, match="denominator"):
        PairPRFMetric(zero_division="raise").compute(())
    with pytest.raises(ValidationError):
        PairPRFMetric(cast(Any, "macro"))


def test_metric_result_and_evaluation_result_validate_and_lookup() -> None:
    with pytest.raises(ValueError, match="Metric name"):
        MetricResult(" ", ())
    with pytest.raises(ValueError, match="unique"):
        MetricResult("x", (("a", 1), ("a", 2)))
    with pytest.raises(TypeError, match="Metric values"):
        MetricResult("x", cast(Any, [("a", 1)]))
    with pytest.raises(ValueError, match="non-empty"):
        MetricResult("x", (("", 1),))
    with pytest.raises(TypeError, match="numeric"):
        MetricResult("x", (("a", cast(Any, True)),))
    with pytest.raises(ValueError, match="finite"):
        MetricResult("x", (("a", float("inf")),))

    document = DocumentEvaluation("doc")
    metric = MetricResult(
        "pair_prf",
        (
            ("tp", 0),
            ("fp", 0),
            ("fn", 0),
            ("precision", 0.0),
            ("recall", 0.0),
            ("f1", 0.0),
        ),
    )
    result = EvaluationResult("exact_pair", "1", (document,), (metric,))
    assert result.document_records == (document,)
    assert result.match_records == ()
    assert result.metric("pair_prf") == metric
    with pytest.raises(KeyError, match="missing"):
        result.metric("missing")
    with pytest.raises(ValueError, match="identity"):
        EvaluationResult(" ", "1", (), ())
    with pytest.raises(TypeError, match="DocumentEvaluation"):
        EvaluationResult("x", "1", cast(Any, (object(),)), ())
    with pytest.raises(TypeError, match="MetricResult"):
        EvaluationResult("x", "1", (), cast(Any, [metric]))


class ToyPolicy:
    identity = "toy_policy"
    version = "1"

    def match(
        self,
        document_id: str,
        gold_annotations: Iterable[AbbreviationDefinition],
        predictions: Iterable[AbbreviationDefinition],
    ) -> DocumentEvaluation:
        return DocumentEvaluation(
            document_id, tuple(gold_annotations), tuple(predictions), ()
        )


class CountingMetric:
    identity = "counting"
    version = "1"

    def compute(self, documents: Iterable[DocumentEvaluation]) -> MetricResult:
        return MetricResult("counting", (("documents", len(tuple(documents))),))


def test_evaluator_is_order_invariant_and_handles_documents_on_one_side() -> None:
    document = Document("doc", "text")
    gold = CorpusRecord(document, (annotation("doc", (0, 1), (1, 2)),))
    pred = PredictionRecord("other", (annotation("other", (0, 1), (1, 2)),))
    evaluator = Evaluator(ExactPairMatchingPolicy(), (PairPRFMetric(),))
    result = evaluator.evaluate((gold,), (pred,))
    assert [record.document_id for record in result.documents] == ["doc", "other"]
    assert result.metric("pair_prf").tp == 0
    assert result.metric("pair_prf").fp == 1
    assert result.metric("pair_prf").fn == 1
    assert result == evaluator.evaluate_records((gold,), (pred,))

    reversed_result = evaluator.evaluate((gold,), tuple(reversed((pred,))))
    assert result == reversed_result


def test_evaluator_rejects_bad_inputs_and_supports_structural_records() -> None:
    gold = CorpusRecord(Document("doc", "text"))
    evaluator = Evaluator(ExactPairMatchingPolicy())
    with pytest.raises(TypeError, match="gold_records"):
        evaluator.evaluate((cast(Any, object()),), ())
    with pytest.raises(TypeError, match="prediction-record"):
        evaluator.evaluate((gold,), (cast(Any, object()),))
    with pytest.raises(EvaluationError, match="Duplicate gold"):
        evaluator.evaluate((gold, gold), ())
    pred = PredictionRecord("doc", (annotation("other", (0, 1), (1, 2)),))
    with pytest.raises(EvaluationError, match="another document"):
        evaluator.evaluate((gold,), (pred,))
    with pytest.raises(EvaluationError, match="Duplicate prediction"):
        evaluator.evaluate((gold,), (PredictionRecord("doc"), PredictionRecord("doc")))
    with pytest.raises(TypeError, match="matching_policy"):
        Evaluator(cast(Any, object()))
    with pytest.raises(TypeError, match="metrics"):
        Evaluator(ExactPairMatchingPolicy(), (cast(Any, object()),))
    with pytest.raises(ValueError, match="identity"):
        Evaluator(ToyPolicy(), matching_policy_key=" ")
    with pytest.raises(ValueError, match="version"):
        Evaluator(ToyPolicy(), matching_policy_version=" ")

    structural: PredictionRecordLike = PredictionRecord("doc")
    assert structural.document_id == "doc"


def test_yaml_composition_uses_builtin_and_injected_registries() -> None:
    direct = EvaluationConfig.model_validate(
        {"matching": {"type": "exact_pair"}, "metrics": [{"type": "pair_prf"}]}
    )
    assert (
        evaluation_config_from_resolved(
            ResolvedConfig.model_validate(
                {"matching": {"type": "exact_pair"}, "metrics": [{"type": "pair_prf"}]}
            )
        )
        == direct
    )
    nested = evaluation_config_from_resolved(
        ResolvedConfig.model_validate(
            {"evaluation": {"matching": {"type": "exact_pair"}}}
        )
    )
    assert nested.metrics == (ComponentSpec(type="pair_prf"),)
    assert create_evaluator(direct).matching_policy.identity == "exact_pair"
    assert MATCHING_POLICIES.keys() == ("exact_pair",)
    assert METRICS.keys() == ("pair_prf",)
    with pytest.raises(ValueError, match="does not contain matching"):
        evaluation_config_from_resolved(ResolvedConfig.model_validate({}))
    with pytest.raises(ValueError, match="section must be a mapping"):
        evaluation_config_from_resolved(
            ResolvedConfig.model_validate({"evaluation": "bad"})
        )
    with pytest.raises(TypeError, match="metrics"):
        evaluation_config_from_resolved(
            ResolvedConfig.model_validate(
                {"matching": {"type": "exact_pair"}, "metrics": {}}
            )
        )
    with pytest.raises(TypeError, match="ResolvedConfig"):
        evaluation_config_from_resolved(cast(Any, object()))
    with pytest.raises(TypeError, match="EvaluationConfig"):
        create_evaluator(cast(Any, object()))

    matching = Registry[MatchingPolicy]("local-matching")
    metrics = Registry[Metric]("local-metrics")
    matching.register("toy_policy", ToyPolicy)
    metrics.register("counting", CountingMetric)
    custom = create_evaluator(
        EvaluationConfig(
            matching=ComponentSpec(type="toy_policy"),
            metrics=(ComponentSpec(type="counting"),),
        ),
        matching_registry=matching,
        metric_registry=metrics,
    )
    result = custom.evaluate((CorpusRecord(Document("doc", "text")),), ())
    assert result.matching_policy == "toy_policy"
    assert result.metric("counting").value("documents") == 1


def test_registry_protocols_are_structural_and_builtins_are_typed() -> None:
    assert isinstance(ExactPairMatchingPolicy(), MatchingPolicy)
    assert isinstance(PairPRFMetric(), Metric)
    assert isinstance(PredictionRecord("doc"), PredictionRecordLike)
