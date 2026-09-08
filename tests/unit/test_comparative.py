from __future__ import annotations

from abrex.domain import AbbreviationDefinition, CorpusRecord, Document, TextSpan
from abrex.evaluation import compare_resolvers
from abrex.resolvers import PredictionRecord


def _gold(
    document_id: str,
    text: str,
    sf: tuple[int, int],
    lf: tuple[int, int],
) -> CorpusRecord:
    return CorpusRecord(
        Document(document_id, text),
        (
            AbbreviationDefinition(
                document_id,
                short_form=TextSpan(*sf),
                long_form=TextSpan(*lf),
                short_form_text=text[sf[0] : sf[1]],
                long_form_text=text[lf[0] : lf[1]],
            ),
        ),
    )


def _prediction(
    document_id: str, sf: tuple[int, int], lf: tuple[int, int]
) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        document_id,
        short_form=TextSpan(*sf),
        long_form=TextSpan(*lf),
    )


def test_comparison_reports_union_and_unique_correct_pairs() -> None:
    gold = (
        _gold("a", "long one (A)", (10, 11), (0, 8)),
        _gold("b", "long two (B)", (10, 11), (0, 8)),
    )
    first = (
        PredictionRecord("a", (_prediction("a", (10, 11), (0, 8)),)),
        PredictionRecord("b", ()),
    )
    second = (
        PredictionRecord("a", ()),
        PredictionRecord("b", (_prediction("b", (10, 11), (0, 8)),)),
    )

    report = compare_resolvers(
        gold,
        {"first": first, "second": second},
        bootstrap_samples=20,
        seed=4,
    )

    assert report.oracle_recall == 1.0
    assert len(report.union_correct_keys) == 2
    assert [len(keys) for _, keys in report.unique_correct_keys] == [1, 1]
    assert report.resolver_results[0].bootstrap == report.resolver_results[0].bootstrap


def test_comparison_bootstrap_is_seeded_and_pair_metrics_are_not_pooled() -> None:
    gold = (_gold("a", "long one (A)", (10, 11), (0, 8)),)
    prediction = (PredictionRecord("a", ()),)

    first = compare_resolvers(gold, {"r": prediction}, bootstrap_samples=10, seed=7)
    second = compare_resolvers(gold, {"r": prediction}, bootstrap_samples=10, seed=7)

    assert first.to_dict() == second.to_dict()
    assert first.mode == "exact_pair"
    assert "Pair and span metrics" in first.limitations[2]
