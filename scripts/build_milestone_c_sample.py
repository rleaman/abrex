"""Acquire or replay the approved Milestone C source-only sample."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from abrex.config import load_config_layer
from abrex.literature.milestone_c_acquisition import acquire_milestone_c_sample
from abrex.literature.milestone_c_sampling import MilestoneCSampleConfig


def load_sample_config(path: Path) -> MilestoneCSampleConfig:
    """Load the campaign sampling section through its typed boundary."""

    raw = load_config_layer(path)
    section = raw.get("milestone_c_sample")
    if not isinstance(section, Mapping):
        raise ValueError("config requires a milestone_c_sample mapping")
    return MilestoneCSampleConfig.model_validate(section)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/literature/campaign-2026-10-milestone-c.yaml"),
    )
    args = parser.parse_args(argv)
    report = acquire_milestone_c_sample(load_sample_config(args.config))
    counts = report.get("counts", {})
    print(
        json.dumps(
            {
                "status": report["status"],
                "counts": counts,
                "manifest": (
                    "evidence/campaign-2026-10/milestone-c/source-manifest-v1.json"
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if str(report["status"]).startswith("complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
