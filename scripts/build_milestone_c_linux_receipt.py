"""Validate and bind the returned Milestone C Linux results."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.literature.milestone_c_results import build_linux_execution_receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    evidence = root / "evidence/campaign-2026-10/milestone-c"
    artifacts = root / ".artifacts/campaign-2026-10/milestone-c"
    parser.add_argument(
        "--returned-archive",
        type=Path,
        default=(
            artifacts
            / (
                "abrex-results-"
                "a1d57ed9ee18e1fc88ebe85e01ae33dddf3c3b853f32065b0ccf778dba1777be"
                ".zip"
            )
        ),
    )
    parser.add_argument(
        "--imported-root", type=Path, default=artifacts / "imported-linux-results-v2"
    )
    parser.add_argument(
        "--output", type=Path, default=evidence / "linux-execution-receipt-v1.json"
    )
    args = parser.parse_args(argv)
    receipt = build_linux_execution_receipt(
        bundle_release_path=evidence / "linux-bundle-release-v2.json",
        bundle_manifest_path=artifacts / "linux-bundle-v2/bundle.json",
        returned_archive_path=args.returned_archive,
        imported_root=args.imported_root,
        prediction_corpus_path=evidence / "prediction-input-v1.jsonl",
        prediction_corpus_manifest_path=evidence / "prediction-input-v1.manifest.json",
        output_path=args.output,
        repository_root=root,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
