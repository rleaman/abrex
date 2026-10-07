"""Milestone C protocol-freeze and source-only sampling regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.freeze_milestone_c_protocol import freeze_protocol

from abrex.literature.fresh_sampling import (
    FreshArticleGroup,
    FreshSamplingError,
    SourcePassage,
    assert_prediction_free,
)
from abrex.literature.milestone_c_acquisition import _element_xml
from abrex.literature.milestone_c_sampling import (
    MilestoneCSampleConfig,
    build_milestone_c_packet,
    mapping_keys,
)
from abrex.literature.review_models import ReviewStructure

ROOT = Path(__file__).resolve().parents[2]


def _config(tmp_path: Path) -> MilestoneCSampleConfig:
    return MilestoneCSampleConfig(
        protocol_path="protocol.json",
        protocol_sha256="a" * 64,
        output_dir=str(tmp_path / "work"),
        delivery_dir=str(tmp_path / "delivery"),
        representative_groups=2,
        structural_groups=1,
        exclusion_paths=("prior.json",),
    )


def _group(index: int, *, structural: bool = False) -> FreshArticleGroup:
    pmid = str(10_000_000 + index)
    pmcid = f"PMC{20_000_000 + index}"
    return FreshArticleGroup(
        group_id=pmid,
        pmid=pmid,
        pmcid=pmcid,
        title=f"Article {index}",
        pmc_source_url=f"https://example.test/{pmcid}",
        pubmed_source_url=f"https://example.test/{pmid}",
        pmc_prose=(
            SourcePassage(
                source_ref=f"article/body/sec/p[{index}]",
                heading="Methods",
                source_kind="pmc_prose",
                text=f"Neutral PMC source passage {index} with enough text.",
            ),
        ),
        pubmed_abstract=(
            SourcePassage(
                source_ref="abstract#segment-1",
                heading="Abstract",
                source_kind="pubmed_abstract",
                text=f"Neutral abstract source passage {index} with enough text.",
            ),
        ),
        structured=(
            (
                SourcePassage(
                    source_ref="article/body[1]/table-wrap[1]",
                    heading="Table or list",
                    source_kind="table_or_list",
                    text="SF\nLong form",
                    structures=(
                        ReviewStructure(
                            kind="table",
                            text="",
                            source_path="article/body[1]/table-wrap[1]",
                        ),
                    ),
                ),
            )
            if structural
            else ()
        ),
    )


def test_packet_has_48_style_paired_and_disjoint_structural_contract(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    packet = build_milestone_c_packet(
        (_group(1), _group(2)), (_group(3, structural=True),), config
    )

    assert len(packet.cases) == 5
    assert sum(case.source_kind == "pmc_prose" for case in packet.cases) == 2
    assert sum(case.source_kind == "pubmed_abstract" for case in packet.cases) == 2
    assert sum(case.source_kind == "table_or_list" for case in packet.cases) == 1
    assert len({case.article_group_id for case in packet.cases}) == 3
    assert_prediction_free(packet)


def test_packet_rejects_cross_stratum_group_overlap(tmp_path: Path) -> None:
    config = _config(tmp_path)

    with pytest.raises(FreshSamplingError, match="strata overlap"):
        build_milestone_c_packet(
            (_group(1), _group(2)), (_group(1, structural=True),), config
        )


def test_raw_source_element_is_recovered_by_stable_jats_path() -> None:
    payload = b"""<article><body><sec><p>Text</p><table-wrap id='t1'>
      <table><tr><td>SF</td><td>Long form</td></tr></table>
    </table-wrap></sec></body></article>"""

    xml = _element_xml(payload, "article/body/sec[1]/table-wrap[1]")

    assert "table-wrap" in xml
    assert "Long form" in xml


def test_freeze_records_exact_user_approval_without_mutating_preflight(
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "preflight.json"
    output = tmp_path / "protocol.json"
    prepared = {
        "schema_version": "campaign-2026-10-milestone-c-preflight-v1",
        "status": "draft_pending_protocol_approval_and_sample_freeze",
        "proposed_sample": {"total_article_groups": 72, "total_passages": 120},
        "proposed_success_criteria": {"confirmatory_primary_contrasts": ["a", "b"]},
        "method_dispositions": {"confirmatory_methods": ["a", "b", "c", "d", "e", "f"]},
        "method_inventory": {},
        "fixed_resource_identities": {},
        "reporting_contract": {},
        "exclusions": {},
    }
    preflight.write_text(json.dumps(prepared), encoding="utf-8")

    frozen = freeze_protocol(preflight, output)

    assert frozen["status"] == "approved_and_frozen"
    approval = frozen["approval"]
    assert isinstance(approval, dict)
    assert approval["response"] == "Approve the Milestone C protocol as prepared."
    assert json.loads(preflight.read_text(encoding="utf-8")) == prepared


def test_real_frozen_packet_matches_approved_counts_and_request_plan() -> None:
    evidence = ROOT / "evidence/campaign-2026-10/milestone-c"
    packet = json.loads(
        (evidence / "review-packet-blind-v1.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (evidence / "source-manifest-v1.json").read_text(encoding="utf-8")
    )
    plan = json.loads((evidence / "request-plan-v1.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "complete_source_only_sample_frozen"
    assert manifest["counts"] == {
        "article_groups": 72,
        "attempts": 348,
        "cases": 120,
        "excluded": 276,
        "failed": 0,
        "pmc_prose": 48,
        "pubmed_abstract": 48,
        "representative_groups": 48,
        "structural_groups": 24,
        "table_or_list": 24,
    }
    assert len(packet["cases"]) == 120
    assert not (
        mapping_keys(packet)
        & {"suggestions", "prediction", "candidate", "gold_annotations"}
    )
    assert plan["boundary"]["requests_sent"] == 0
    assert plan["typesafe"]["authorization_request"] == {
        "cost_basis": (
            "conservative token cap at the $0.042/M input-token rate recorded "
            "for the prior Jev development run; provider billing must be checked "
            "before execution because current live pricing could not be retrieved"
        ),
        "maximum_input_tokens": 724000,
        "maximum_network_requests": 65,
        "monetary_cap_usd": 0.05,
        "retries": 0,
    }
    assert plan["luna"]["authorization_request"]["maximum_network_attempts"] == 120
