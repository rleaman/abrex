"""T065 deterministic source-only sampling contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.literature.fresh_sampling import (
    FreshArticleGroup,
    FreshSamplingError,
    FrozenFreshConfig,
    SourcePassage,
    assert_prediction_free,
    build_fresh_packet,
    load_exclusion_ledger,
    segment_prose,
)


def _config(tmp_path: Path, **changes: object) -> FrozenFreshConfig:
    values: dict[str, object] = {
        "protocol_path": "protocol.json",
        "protocol_sha256": "a" * 64,
        "output_dir": str(tmp_path),
        "delivery_dir": str(tmp_path / "delivery"),
        "article_groups": 2,
        "pmc_prose_passages": 3,
        "pubmed_abstract_passages": 3,
        "table_or_list_sections": 2,
        "maximum_items_per_group": 4,
        "exclusion_paths": ("prior.json",),
    }
    values.update(changes)
    return FrozenFreshConfig.model_validate(values)


def _passage(prefix: str, index: int, kind: str) -> SourcePassage:
    return SourcePassage(
        source_ref=f"{prefix}-{index}",
        heading=f"Heading {index}",
        source_kind=kind,
        text=(
            f"Source-only passage {prefix} number {index}; prediction and confidence "
            "are ordinary source words here."
        ),
    )


def _group(index: int) -> FreshArticleGroup:
    return FreshArticleGroup(
        group_id=str(10_000_000 + index),
        pmid=str(10_000_000 + index),
        pmcid=f"PMC{20_000_000 + index}",
        title=f"Article {index}",
        pmc_source_url=f"https://example.test/PMC{index}",
        pubmed_source_url=f"https://example.test/{index}",
        pmc_prose=tuple(_passage("pmc", item, "pmc_prose") for item in range(4)),
        pubmed_abstract=tuple(
            _passage("abstract", item, "pubmed_abstract") for item in range(4)
        ),
        structured=tuple(_passage("table", item, "table_or_list") for item in range(2)),
    )


def test_build_fresh_packet_is_deterministic_and_balanced(tmp_path: Path) -> None:
    config = _config(tmp_path)
    groups = (_group(1), _group(2))

    first = build_fresh_packet(groups, config)
    second = build_fresh_packet(groups, config)

    assert first == second
    assert len(first.cases) == 8
    assert {case.article_group_id for case in first.cases} == {
        "10000001",
        "10000002",
    }
    assert sum(case.source_kind == "pmc_prose" for case in first.cases) == 3
    assert sum(case.source_kind == "pubmed_abstract" for case in first.cases) == 3
    assert sum(case.source_kind == "table_or_list" for case in first.cases) == 2
    assert_prediction_free(first)


def test_build_fresh_packet_reports_source_shortage(tmp_path: Path) -> None:
    config = _config(tmp_path)
    group = _group(1).model_copy(update={"structured": ()})

    with pytest.raises(FreshSamplingError, match="structured candidates; needs 1"):
        build_fresh_packet((group, _group(2)), config)


def test_exclusion_ledger_covers_linked_and_discovery_ids(tmp_path: Path) -> None:
    manifest = tmp_path / "prior.json"
    manifest.write_text(
        json.dumps(
            {
                "attempts": [
                    {"arm": "pmc_cc_by", "identifier": "PMC123456"},
                    {"arm": "pubmed_abstract", "identifier": "23456789"},
                ],
                "records": [
                    {
                        "pmid": "34567890",
                        "pmcid": "PMC7654321",
                        "article_group_id": "34567890",
                    }
                ],
                "identifiers": ["45678901"],
            }
        ),
        encoding="utf-8",
    )

    ledger = load_exclusion_ledger((manifest,))

    assert ledger.excludes(pmcid="pmc123456")
    assert ledger.excludes(pmid="23456789")
    assert ledger.excludes(pmid="34567890", pmcid="PMC999999")
    assert ledger.excludes(pmid="45678901")
    assert not ledger.excludes(pmid="56789012", pmcid="PMC999999")
    assert ledger.source_hashes[manifest.as_posix()]


def test_segment_prose_uses_source_boundaries_and_length_only() -> None:
    text = " ".join(
        (
            "First sentence has enough source material for a passage.",
            "Second sentence supplies more neutral source material.",
            "Third sentence closes the deterministic source segment.",
        )
    )

    passages = segment_prose(
        text,
        source_ref="abstract",
        heading="Abstract",
        source_kind="pubmed_abstract",
        minimum_chars=40,
        target_chars=115,
        maximum_chars=120,
    )

    assert len(passages) == 2
    assert passages[0].text.startswith("First sentence")
    assert passages[1].text.endswith("source segment.")


def test_config_rejects_unfilled_group_slots(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fill every article-group slot"):
        _config(tmp_path, pubmed_abstract_passages=2)
