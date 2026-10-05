"""Freeze T067 inputs after the corrected prediction-blind annotation lock."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.fresh_evaluation import materialize_fresh_projection


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "evidence/T067"
    materialize_fresh_projection(
        packet_path=root / "evidence/T065/review-packet-blind-v1.json",
        state_path=(
            root / "evidence/T066/review-packet-blind-v1.annotations.corrected-v2.json"
        ),
        lock_path=(
            root
            / "evidence/T066/review-packet-blind-v1.annotations.corrected-v2.lock.json"
        ),
        correction_manifest_path=root / "evidence/T066/correction-manifest-v2.json",
        source_manifest_path=root / "evidence/T065/source-manifest-v1.json",
        protocol_path=root / "docs/artifacts/T063-decision-prefill.json",
        component_config_paths={
            "schwartz_hearst": root / "configs/experiments/T060-schwartz-hearst.yaml",
            "plodv2_pairing": root / "configs/experiments/T060-plodv2-linux.yaml",
        },
        prediction_path=output / "fresh-prediction-input-v1.jsonl",
        prediction_manifest_path=output / "fresh-prediction-input-v1.manifest.json",
        gold_path=output / "fresh-strict-gold-v1.jsonl",
        gold_manifest_path=output / "fresh-strict-gold-v1.manifest.json",
        ledger_path=output / "fresh-eligibility-ledger-v1.json",
        run_manifest_path=output / "fresh-run-manifest-v1.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
