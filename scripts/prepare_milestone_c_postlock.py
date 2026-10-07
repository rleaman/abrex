"""Freeze Milestone C post-lock datasets and independent-review packet."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from abrex.literature.milestone_c_postlock import materialize_milestone_c_postlock


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence = root / "evidence/campaign-2026-10/milestone-c"
    result = materialize_milestone_c_postlock(
        packet_path=evidence / "review-packet-blind-v1.json",
        state_path=evidence / "review-packet-blind-v1.annotations.json",
        lock_path=evidence / "review-packet-blind-v1.annotations.lock.json",
        source_manifest_path=evidence / "source-manifest-v1.json",
        protocol_path=evidence / "protocol-v1.json",
        prediction_path=evidence / "prediction-input-v1.jsonl",
        prediction_manifest_path=evidence / "prediction-input-v1.manifest.json",
        gold_path=evidence / "strict-gold-v1.jsonl",
        gold_manifest_path=evidence / "strict-gold-v1.manifest.json",
        ledger_path=evidence / "eligibility-ledger-v1.json",
        run_manifest_path=evidence / "run-manifest-v1.json",
        second_review_packet_path=evidence / "second-review-packet-blind-v1.json",
        second_review_state_path=(
            evidence / "second-review-packet-blind-v1.annotations.json"
        ),
        second_review_selection_path=evidence / "second-review-selection-v1.json",
    )
    ledger_counts = cast(Mapping[str, object], result.ledger["counts"])
    second_review_counts = cast(
        Mapping[str, object], result.second_review_manifest["counts"]
    )
    print(
        json.dumps(
            {
                "cases": len(result.prediction_records),
                "strict_relations": ledger_counts["strict_relations"],
                "second_review_cases": second_review_counts["selected_cases"],
                "status": result.run_manifest["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
