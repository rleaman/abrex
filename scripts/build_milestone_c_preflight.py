"""Build the auditable pre-freeze inventory for campaign Milestone C."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.literature.fresh_sampling import load_exclusion_ledger
from abrex.resolvers.direct_extraction import DIRECT_EXTRACTION_VERSION

EXCLUSION_PATHS = (
    Path("docs/artifacts/T025-pubmed-pilot-report.json"),
    Path("evidence/T052/T051-pilot-manifest.json"),
    Path("evidence/T060/review-packet-split-v2.json"),
    Path("evidence/T062/development-ledger-v1.json"),
    Path("resources/clp/abbr-v5-validation-v1.jsonl"),
    Path("evidence/T065/source-manifest-v1.json"),
    Path("evidence/T067/fresh-eligibility-ledger-v1.json"),
)

METHOD_PATHS = {
    "ab3p_native_offsets": Path("configs/experiments/T060-ab3p-linux.yaml"),
    "schwartz_hearst": Path("configs/experiments/T067-schwartz-hearst.yaml"),
    "plodv2_pairing": Path("configs/experiments/T067-plodv2-linux.yaml"),
    "complete_clp_v5_1_worker": Path("scripts/run_clp_worker_v2.py"),
    "jev_candidate_judge": Path("configs/experiments/T060-jev-split-v2.yaml"),
    "direct_extraction": Path(
        "configs/experiments/campaign-2026-10-direct-extraction.yaml"
    ),
}

RUNTIME_PREFLIGHT_PATH = Path(
    "evidence/campaign-2026-10/milestone-c/runtime-preflight-v1.json"
)
BLIND_REVIEWER_QA_PATH = Path(
    "evidence/campaign-2026-10/milestone-c/blind-reviewer-qa-v1.json"
)


def build_preflight(
    output_path: Path,
    *,
    t067_report_path: Path = Path(
        "docs/artifacts/T067-fresh-evaluation-readout-v1.json"
    ),
) -> dict[str, object]:
    """Build current exclusions, method pins, and the proposed sampling burden."""

    ledger = load_exclusion_ledger(EXCLUSION_PATHS)
    t067 = _object(t067_report_path)
    runtime_preflight = _object(RUNTIME_PREFLIGHT_PATH)
    blind_reviewer_qa = _object(BLIND_REVIEWER_QA_PATH)
    dataset = _mapping(t067.get("dataset"), "T067 dataset")
    group_analysis = _mapping(t067.get("article_group_analysis"), "T067 group analysis")
    proposed_representative_groups = 48
    proposed_structure_groups = 24
    representative_passages = proposed_representative_groups * 2
    structure_passages = proposed_structure_groups
    total_passages = representative_passages + structure_passages
    report: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-preflight-v1",
        "status": "draft_pending_milestone_b_result_and_protocol_freeze",
        "evidence_boundary": {
            "t067_is_development_after_reveal": True,
            "t067_status": t067.get("status"),
            "t067_recommendation": t067.get("recommendation"),
            "t067_dataset": dict(dataset),
            "t067_group_uncertainty": group_analysis.get("uncertainty_statement"),
            "reason_new_sample_required": (
                "T067 has eight exposed article groups and method gains concentrated "
                "by group; it cannot be reused for confirmation."
            ),
        },
        "exclusions": {
            "pmids": list(ledger.pmids),
            "pmcids": list(ledger.pmcids),
            "pmid_count": len(ledger.pmids),
            "pmcid_count": len(ledger.pmcids),
            "source_hashes": ledger.source_hashes,
            "linked_identity_rule": (
                "exclude a group when either its PMID or PMCID is present"
            ),
            "known_clp_overlap_excluded": True,
            "unknown_dictionary_or_training_overlap": (
                "retain as a limitation; do not infer absence"
            ),
        },
        "method_inventory": {
            name: {
                "path": path.as_posix(),
                "sha256": _file_sha(path),
            }
            for name, path in METHOD_PATHS.items()
        },
        "fixed_resource_identities": {
            "clp_source_commit": ("323fd4f51aa3c5b54ed30f37dd297b00b49e277e"),
            "clp_source_archive": {
                "path": "resources/clp/clp-v5.1-source.zip",
                "sha256": _file_sha(Path("resources/clp/clp-v5.1-source.zip")),
            },
            "plod_checkpoint_sha256": (
                "3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277"
            ),
            "jev_model": "jev-1.13.0",
            "direct_model_route": "gpt-6-luna",
            "direct_extraction_resolver_version": DIRECT_EXTRACTION_VERSION,
        },
        "proposed_sample": {
            "state": "proposal_not_frozen",
            "seed": 20261006,
            "representative": {
                "article_groups": proposed_representative_groups,
                "passages_per_group": 2,
                "passages": representative_passages,
                "mix": {
                    "pmc_prose": proposed_representative_groups,
                    "pubmed_abstract": proposed_representative_groups,
                },
                "selection": (
                    "source-only seeded sampling without detector, abbreviation-token, "
                    "or prediction enrichment"
                ),
                "worst_case_wilson_95_half_width_for_group_proportion": (
                    _wilson_half_width(proposed_representative_groups)
                ),
                "interpretation": (
                    "primary deployment-oriented component; group bootstrap is the "
                    "uncertainty unit"
                ),
            },
            "structural_challenge": {
                "article_groups": proposed_structure_groups,
                "passages_per_group": 1,
                "passages": structure_passages,
                "selection": (
                    "disjoint source-only groups with explicit ABBR section or "
                    "table/list structure; retain ordered passages and raw table XML"
                ),
                "worst_case_wilson_95_half_width_for_group_proportion": (
                    _wilson_half_width(proposed_structure_groups)
                ),
                "interpretation": (
                    "enriched capability challenge reported separately and never "
                    "pooled into a population estimate"
                ),
            },
            "total_article_groups": (
                proposed_representative_groups + proposed_structure_groups
            ),
            "total_passages": total_passages,
            "estimated_primary_review_hours": {"low": 8, "high": 12},
            "review_plan": (
                "prediction-blind primary annotation of every passage; independent "
                "second review of all positives, all uncertain/diagnostic relations, "
                "and a seeded 10% of negative passages before adjudication"
            ),
        },
        "proposed_success_criteria": {
            "state": "proposal_not_frozen",
            "milestone_b_unchanged_prompt_gate": {
                "candidate_omitted_gold_relations": 14,
                "minimum_candidate_omitted_relations_recovered": 7,
                "minimum_exact_precision": 0.65,
                "maximum_request_failure_fraction": 0.05,
                "maximum_invalid_grounded_output_fraction": 0.10,
                "maximum_actual_cost_usd": 0.05,
                "single_run_rule": (
                    "run the frozen prompt once; do not tune or rerun to cross the gate"
                ),
                "interpretation": (
                    "advance the unchanged prompt only if every threshold passes; "
                    "otherwise retain and report the negative development result"
                ),
            },
            "confirmatory_primary_endpoint": (
                "strict exact-pair F1 on the representative component"
            ),
            "confirmatory_primary_contrasts": [
                "direct extraction versus Jev candidate judging",
                "complete CLP V5.1 versus Schwartz-Hearst",
            ],
            "superiority_rule": {
                "minimum_absolute_f1_gain": 0.05,
                "inference": (
                    "paired seeded article-group bootstrap; two-sided primary "
                    "contrast p-values controlled by Holm at familywise alpha 0.05"
                ),
                "required": (
                    "both the practical gain and multiplicity-controlled statistical "
                    "criterion must pass"
                ),
            },
            "operational_guardrails": {
                "maximum_representative_request_failure_fraction": 0.05,
                "all_dropped_or_repaired_outputs_diagnosed": True,
                "all_frozen_request_token_and_cost_limits_respected": True,
            },
            "structural_challenge_rule": (
                "descriptive capability evidence only; never used for the "
                "representative superiority decision"
            ),
            "negative_result_rule": (
                "failure to satisfy a criterion is reported as not established; "
                "do not redraw, retune, or substitute an exploratory endpoint"
            ),
        },
        "reporting_contract": {
            "primary_matching": "strict half-open exact SF/LF occurrence pair",
            "secondary_matching": [
                "endpoint-only diagnostics",
                "normalized CLP-native string view",
                "discontinuous evidence outside exact-pair scoring",
            ],
            "strata": [
                "representative_pmc_prose",
                "representative_pubmed_abstract",
                "structural_challenge",
            ],
            "uncertainty": (
                "seeded article-group bootstrap; report group concentration and "
                "runtime failures"
            ),
            "no_pooling_rule": (
                "structural challenge results must not be pooled into the "
                "representative population estimate"
            ),
            "negative_result_rule": (
                "run and report every frozen method; never resample until a win"
            ),
        },
        "pre_freeze_dependencies": [
            "complete the 20-document direct-extraction development run",
            (
                "classify its errors and decide whether its frozen prompt "
                "advances unchanged"
            ),
            "authorize bounded OpenAI and TypeSafe scientific-data requests",
            (
                "freeze a source-structure sidecar carrying ordered passages and "
                "raw table XML"
            ),
            "approve the final review burden and success thresholds",
        ],
        "review_interface_readiness": {
            "artifact": BLIND_REVIEWER_QA_PATH.as_posix(),
            "sha256": _sha256(BLIND_REVIEWER_QA_PATH),
            "status": blind_reviewer_qa.get("status"),
            "browser": blind_reviewer_qa.get("browser"),
            "checks": blind_reviewer_qa.get("checks"),
            "scope": (
                "disposable source-only packet; repeat browser and persistence QA "
                "on the actual frozen packet before delivery"
            ),
        },
        "runtime_boundary": {
            "active_host_preflight": {
                "path": RUNTIME_PREFLIGHT_PATH.as_posix(),
                "sha256": _sha256(RUNTIME_PREFLIGHT_PATH),
                "status": runtime_preflight.get("status"),
                "exit_code": runtime_preflight.get("exit_code"),
                "interpretation": runtime_preflight.get("interpretation"),
            },
            "ab3p_plod": (
                "fresh Linux server bundle using docs/linux-server-runtimes.md"
            ),
            "clp": (
                "pinned CLP Python 3.13 worker; rules-only dry run first, then bounded "
                "live TypeSafe decisions only after authorization"
            ),
            "gold_exclusion": (
                "prediction bundles contain only source text/structure and frozen "
                "method configuration"
            ),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def _wilson_half_width(n: int) -> float:
    z = 1.959963984540054
    p = 0.5
    denominator = 1 + z * z / n
    return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/preflight-v1.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build the preflight and print its stable headline."""

    args = _parser().parse_args(argv)
    report = build_preflight(args.output)
    sample = _mapping(report["proposed_sample"], "proposed sample")
    exclusions = _mapping(report["exclusions"], "exclusions")
    print(
        json.dumps(
            {
                "status": report["status"],
                "total_article_groups": sample["total_article_groups"],
                "total_passages": sample["total_passages"],
                "excluded_pmids": exclusions["pmid_count"],
                "excluded_pmcids": exclusions["pmcid_count"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
