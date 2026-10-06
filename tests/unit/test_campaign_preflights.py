"""Regression tests for the campaign's machine-checked pre-freeze evidence."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_milestone_c_preflight import build_preflight


def test_milestone_c_preflight_excludes_exposed_groups_and_pins_methods(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preflight.json"

    report = build_preflight(output)

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["status"] == ("draft_pending_milestone_b_result_and_protocol_freeze")
    exclusions = report["exclusions"]
    assert isinstance(exclusions, dict)
    assert exclusions["pmid_count"] == 238
    assert exclusions["pmcid_count"] == 83
    excluded_pmids = set(exclusions["pmids"])
    assert {
        "19909526",
        "32671034",
        "36538532",
        "41458304",
        "41599235",
        "42145581",
        "42245833",
        "42543246",
    } <= excluded_pmids
    methods = report["method_inventory"]
    assert isinstance(methods, dict)
    assert set(methods) == {
        "ab3p_native_offsets",
        "schwartz_hearst",
        "plodv2_pairing",
        "complete_clp_v5_1_worker",
        "jev_candidate_judge",
        "direct_extraction",
    }
    assert all(
        isinstance(value, dict) and len(str(value["sha256"])) == 64
        for value in methods.values()
    )
    identities = report["fixed_resource_identities"]
    assert isinstance(identities, dict)
    assert identities["direct_extraction_resolver_version"] == "2"
    assert identities["direct_model_route"] == (
        "azure_openai:${AZURE_OPENAI_DEPLOYMENT}"
    )
    sample = report["proposed_sample"]
    assert isinstance(sample, dict)
    assert sample["total_article_groups"] == 72
    assert sample["total_passages"] == 120
    criteria = report["proposed_success_criteria"]
    assert isinstance(criteria, dict)
    assert criteria["state"] == "proposal_not_frozen"
    gate = criteria["milestone_b_unchanged_prompt_gate"]
    assert isinstance(gate, dict)
    assert gate["minimum_candidate_omitted_relations_recovered"] == 7
    assert gate["maximum_actual_cost_usd"] == 0.05
    contrasts = criteria["confirmatory_primary_contrasts"]
    assert isinstance(contrasts, list)
    assert len(contrasts) == 2
    runtime = report["runtime_boundary"]
    assert isinstance(runtime, dict)
    active_host = runtime["active_host_preflight"]
    assert isinstance(active_host, dict)
    assert active_host["status"] == "active_host_runtime_unavailable"
    assert active_host["exit_code"] == 1
    assert len(str(active_host["sha256"])) == 64
    reviewer = report["review_interface_readiness"]
    assert isinstance(reviewer, dict)
    assert reviewer["status"] == "passed"
    assert len(str(reviewer["sha256"])) == 64
    checks = reviewer["checks"]
    assert isinstance(checks, dict)
    assert checks and all(checks.values())
