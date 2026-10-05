"""Materialize the T062 recovery analysis and T063 decision prefill."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.development_readout import materialize_development_readout


def main() -> int:
    root = Path(__file__).parents[1]
    t060 = root / ".artifacts/T060"
    imported = t060 / "imported-linux-results"
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
        ledger_path=root / "evidence/T062/development-ledger-v1.json",
        recovery_path=root / "evidence/T062/recovery-table-v1.jsonl",
        prediction_dispositions_path=(
            root / "evidence/T062/prediction-dispositions-v1.jsonl"
        ),
        report_json_path=root / "docs/artifacts/T062-development-readout.json",
        report_markdown_path=root / "docs/artifacts/T062-development-readout.md",
        decision_prefill_path=root / "docs/artifacts/T063-decision-prefill.json",
    )
    dataset = report["dataset"]
    if not isinstance(dataset, dict):
        raise ValueError("T062 report dataset must be an object")
    print(
        "T062 complete: "
        f"{dataset['strict_relations']} strict relations; "
        "T063 recommendation prefilled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
