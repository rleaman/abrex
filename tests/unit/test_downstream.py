from abrex.literature import compare_downstream_entities


def test_downstream_comparison_reports_introduced_and_false_entities() -> None:
    result = compare_downstream_entities(
        ("gene-a", "gene-b"), ("gene-a",), ("gene-a", "gene-c")
    )
    assert result.baseline_count == 1
    assert result.propagated_count == 2
    assert result.introduced_entity_ids == ("gene-c",)
    assert result.removed_entity_ids == ()
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.false_expansions == 1


def test_downstream_comparison_without_gold_leaves_quality_unclaimed() -> None:
    result = compare_downstream_entities(None, (), ("entity",))
    assert result.precision is None
    assert result.recall is None
    assert result.false_expansions == 0
