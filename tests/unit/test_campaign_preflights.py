"""Regression tests for the campaign's machine-checked pre-freeze evidence."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_direct_extraction_readout import build_readout
from scripts.build_milestone_c_preflight import build_preflight


def test_milestone_c_preflight_excludes_exposed_groups_and_pins_methods(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preflight.json"

    report = build_preflight(output)

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["status"] == "draft_pending_protocol_approval_and_sample_freeze"
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
    assert gate["state"] == "evaluated_failed"
    assert gate["decision"] == "do_not_advance_unchanged_prompt_to_milestone_c"
    contrasts = criteria["confirmatory_primary_contrasts"]
    assert isinstance(contrasts, list)
    assert contrasts == ["complete CLP V5.1 versus Schwartz-Hearst"]
    dispositions = report["method_dispositions"]
    assert isinstance(dispositions, dict)
    direct = dispositions["direct_extraction"]
    assert isinstance(direct, dict)
    assert direct["advance_unchanged"] is False
    pre_freeze_dependencies = report["pre_freeze_dependencies"]
    assert isinstance(pre_freeze_dependencies, list)
    assert len(pre_freeze_dependencies) == 1
    post_freeze_dependencies = report["post_freeze_external_dependencies"]
    assert isinstance(post_freeze_dependencies, list)
    assert len(post_freeze_dependencies) == 2
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


def test_direct_extraction_readout_keeps_failures_out_of_primary_scoring(
    tmp_path: Path,
) -> None:
    output = tmp_path / "readout.json"
    markdown = tmp_path / "readout.md"

    report = build_readout(
        corpus_path=Path(
            "evidence/campaign-2026-10/milestone-b/t062-development.jsonl"
        ),
        prediction_path=Path(
            "evidence/campaign-2026-10/milestone-b/"
            "direct-extraction-predictions-v1.jsonl"
        ),
        cache_path=Path(
            "evidence/campaign-2026-10/milestone-b/direct-extraction-cache.jsonl"
        ),
        preflight_path=Path(
            "evidence/campaign-2026-10/milestone-b/direct-extraction-preflight-v1.json"
        ),
        output_path=output,
        markdown_path=markdown,
    )

    assert json.loads(output.read_text(encoding="utf-8")) == report
    execution = report["execution"]
    assert isinstance(execution, dict)
    assert execution["successful_documents"] == 11
    assert execution["failed_documents"] == 9
    strict = report["strict_exact"]
    assert isinstance(strict, dict)
    subset = strict["successful_subset"]
    assert isinstance(subset, dict)
    assert subset["true_positives"] == 13
    assert subset["false_positives"] == 1
    assert subset["false_negatives"] == 13
    assert subset["f1"] == 0.65
    assert strict["candidate_omitted_relations_recovered"] == 1
    grounding = report["grounding"]
    assert isinstance(grounding, dict)
    assert grounding["unsupported_outputs"] == 15
    gate = report["advancement_gate"]
    assert isinstance(gate, dict)
    assert gate["all_passed"] is False
    assert gate["decision"] == "do_not_advance_unchanged_prompt_to_milestone_c"
    usage = report["usage"]
    assert isinstance(usage, dict)
    assert usage["total_cost_upper_bound_usd"] == 0.0471974
    assert "failed documents" in markdown.read_text(encoding="utf-8")
