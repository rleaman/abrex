"""Materialize the T060 comparison and assisted review packet."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.development_comparison import materialize_development_comparison


def main() -> int:
    root = Path(__file__).parents[1]
    artifacts = root / ".artifacts/T060"
    imported = artifacts / "imported-linux-results"
    materialize_development_comparison(
        corpus_path=root / "evidence/T059/t057-strict-development.jsonl",
        corpus_manifest_path=(
            root / "evidence/T059/t057-strict-development.manifest.json"
        ),
        diagnostic_view_path=root / "evidence/T057/diagnostic-development.json",
        source_packet_path=root / "evidence/T052/review-packet-v2.json",
        prediction_paths={
            "ab3p": imported / "t060-ab3p-linux/predictions.jsonl",
            "jev_candidate_judge": artifacts
            / "jev-split-v2/predictions"
            / "7978ab61a649ec43c904ba5186ff1a01e01908fff9e4fa82833eee946b2aa83a"
            / "predictions.jsonl",
            "plodv2_pairing": imported / "t060-plodv2-pairing-linux/predictions.jsonl",
            "schwartz_hearst": artifacts
            / "schwartz-hearst/predictions"
            / "627e8dc7eb8c6f4ef5887d348cef5659d4f4facb137edf010da4da343fcf14f0"
            / "predictions.jsonl",
        },
        job_result_paths={
            "ab3p": imported / "t060-ab3p-linux/result.json",
            "plodv2_pairing": imported / "t060-plodv2-pairing-linux/result.json",
            "plodv2_spans": imported / "t060-plodv2-spans-linux/result.json",
        },
        plod_span_path=imported / "t060-plodv2-spans-linux/predictions.jsonl",
        comparison_path=(
            root / "docs/artifacts/T060-development-comparison-split-v2.json"
        ),
        review_packet_path=root / "evidence/T060/review-packet-split-v2.json",
        evidence_manifest_path=root / "evidence/T060/manifest-split-v2.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
