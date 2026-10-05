from __future__ import annotations

import json
from pathlib import Path

from abrex.literature.development_readout import (
    EndpointKey,
    materialize_development_readout,
    pair_metrics,
    recovery_outcome,
)
from abrex.literature.review_models import fingerprint


def test_pair_metrics_uses_one_to_one_occurrence_matching() -> None:
    strict = {
        ("doc", 10, 12, 0, 9),
        ("doc", 30, 32, 20, 29),
    }
    diagnostic = {("doc", 50, 52, 40, 49)}
    predictions = [
        ("doc", 10, 12, 0, 9),
        ("doc", 10, 12, 0, 9),
        ("doc", 50, 52, 40, 49),
        ("doc", 70, 72, 60, 69),
    ]

    result = pair_metrics(predictions, strict, diagnostic)

    assert result["true_positives"] == 1
    assert result["outside_strict_target"] == 1
    assert result["false_positives"] == 2
    assert result["false_negatives"] == 1
    assert result["duplicate_predictions"] == 1


def test_recovery_outcomes_keep_detection_pairing_and_boundaries_separate() -> None:
    relation = ("doc", 10, 12, 0, 9)
    exact_endpoints: set[EndpointKey] = {
        ("doc", "short_form", 10, 12),
        ("doc", "long_form", 0, 9),
    }

    assert recovery_outcome(relation, [relation])["outcome"] == "correct_exact_pair"
    assert (
        recovery_outcome(relation, [], exact_endpoints)["outcome"]
        == "detected_spans_without_correct_pairing"
    )
    assert (
        recovery_outcome(relation, [("doc", 10, 12, 0, 8)])["outcome"]
        == "wrong_boundary"
    )
    assert (
        recovery_outcome(
            relation,
            [
                (
                    "other",
                    10,
                    12,
                    0,
                    9,
                )
            ],
        )["outcome"]
        == "absent_candidate"
    )


def test_frozen_t062_readout_is_complete_and_content_addressed() -> None:
    root = Path(__file__).parents[2]
    report = json.loads(
        (root / "docs/artifacts/T062-development-readout.json").read_text(
            encoding="utf-8"
        )
    )
    digest = report.pop("content_sha256")

    assert fingerprint(report) == digest
    assert report["status"] == "complete"
    assert report["dataset"] == {
        "article_groups": 15,
        "diagnostic_relations": 12,
        "documents": 20,
        "new_t061_strict_relations": 8,
        "strict_relations": 67,
    }
    assert report["methods"]["plodv2_pairing"]["false_positives"] == 1
    assert report["methods"]["schwartz_hearst"]["true_positives"] == 36
    assert (
        report["simple_union_schwartz_hearst_plodv2"]["metrics"]["true_positives"] == 45
    )
    assert report["gold_assisted_all_method_oracle"]["correct_available_pairs"] == 47


def test_t062_tables_cover_every_relation_and_prediction() -> None:
    root = Path(__file__).parents[2]
    recovery = [
        json.loads(line)
        for line in (root / "evidence/T062/recovery-table-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    predictions = [
        json.loads(line)
        for line in (root / "evidence/T062/prediction-dispositions-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert len(recovery) == 79
    assert sum(row["disposition"] == "strict" for row in recovery) == 67
    assert sum(row["disposition"] == "diagnostic" for row in recovery) == 12
    assert not any(row["disposition"] == "unresolved" for row in recovery)
    assert len(predictions) == 165
    assert {row["method"] for row in predictions} == {
        "ab3p",
        "jev_candidate_judge",
        "plodv2_pairing",
        "schwartz_hearst",
    }


def test_t063_prefill_records_bundled_approval() -> None:
    root = Path(__file__).parents[2]
    decision = json.loads(
        (root / "docs/artifacts/T063-decision-prefill.json").read_text(encoding="utf-8")
    )

    assert decision["status"] == "approved_and_frozen"
    assert decision["approval"] == {
        "approved_at": "2026-10-04",
        "approved_by": "scientific_lead",
        "response": "Approve T063",
        "scope": "prefilled_recommendation",
    }
    dependencies = decision["evidence_dependencies"]
    assert dependencies["t060_complete"] is True
    assert dependencies["t061_complete"] is True
    assert dependencies["t062_complete"] is True
    assert decision["required_user_decisions"] == [
        {
            "decision_id": "approve_recommended_protocol",
            "prompt": (
                "Approve the complete prefilled recommendation, or list only "
                "the fields to change."
            ),
            "recommended_response": "Approve T063",
        }
    ]


def test_t062_materialization_rebuilds_complete_outputs(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    t060 = root / ".artifacts/T060"
    imported = t060 / "imported-linux-results"
    output = tmp_path / "evidence/T062"
    report_path = tmp_path / "docs/artifacts/T062-development-readout.json"
    report = materialize_development_readout(
        diagnostic_view_path=root / "evidence/T057/diagnostic-development.json",
        review_sources=(
            (
                root / "evidence/T060/review-packet-split-v2.json",
                root / "evidence/T060/review-packet-split-v2.annotations.json",
            ),
            (
                root / "evidence/T061/review-packet-minimal.json",
                root / "evidence/T061/review-packet-minimal.annotations.json",
            ),
        ),
        triage_path=root / "evidence/T061/triage.json",
        corpus_path=root / "evidence/T059/t057-strict-development.jsonl",
        corpus_manifest_path=(
            root / "evidence/T059/t057-strict-development.manifest.json"
        ),
        prediction_paths={
            "ab3p": imported / "t060-ab3p-linux/predictions.jsonl",
            "jev_candidate_judge": t060
            / "jev-split-v2/predictions"
            / "7978ab61a649ec43c904ba5186ff1a01e01908fff9e4fa82833eee946b2aa83a"
            / "predictions.jsonl",
            "plodv2_pairing": imported / "t060-plodv2-pairing-linux/predictions.jsonl",
            "schwartz_hearst": t060
            / "schwartz-hearst/predictions"
            / "627e8dc7eb8c6f4ef5887d348cef5659d4f4facb137edf010da4da343fcf14f0"
            / "predictions.jsonl",
        },
        plod_span_path=imported / "t060-plodv2-spans-linux/predictions.jsonl",
        t060_comparison_path=(
            root / "docs/artifacts/T060-development-comparison-split-v2.json"
        ),
        jev_report_path=root / "docs/artifacts/T059-jev-split-development.json",
        schwartz_hearst_config_path=(
            root / "configs/experiments/T060-schwartz-hearst.yaml"
        ),
        plod_pairing_config_path=root / "configs/experiments/T060-plodv2-linux.yaml",
        ledger_path=output / "development-ledger-v1.json",
        recovery_path=output / "recovery-table-v1.jsonl",
        prediction_dispositions_path=output / "prediction-dispositions-v1.jsonl",
        report_json_path=report_path,
        report_markdown_path=(tmp_path / "docs/artifacts/T062-development-readout.md"),
        decision_prefill_path=tmp_path / "docs/artifacts/T063-decision-prefill.json",
    )

    assert report["status"] == "complete"
    assert report["dataset"]["strict_relations"] == 67  # type: ignore[index]
    assert output.joinpath("development-ledger-v1.json").is_file()
    assert output.joinpath("recovery-table-v1.jsonl").is_file()
    assert output.joinpath("prediction-dispositions-v1.jsonl").is_file()
    assert report_path.is_file()
