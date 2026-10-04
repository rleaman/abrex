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
            / "jev/predictions"
            / "0ee04a1ddaab62203f5d4f8501081624c60f120ce9c29f4469dd6aa5df48a93c"
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
        },
        comparison_path=root / "docs/artifacts/T060-development-comparison.json",
        review_packet_path=root / "evidence/T060/review-packet.json",
        evidence_manifest_path=root / "evidence/T060/manifest.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
