"""Run the bounded T058 baseline-runtime readiness smoke."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from abrex.literature.pilot_models import PilotConfig
from abrex.literature.runtime_readiness import run_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="exit nonzero after saving diagnostics if any primary method is not ready",
    )
    args = parser.parse_args()
    raw = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("literature_pilot"), dict):
        raise ValueError("configuration must contain a literature_pilot mapping")
    config = PilotConfig.model_validate(raw["literature_pilot"])
    report = run_readiness(config, args.runtime_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "methods": [item.model_dump(mode="json") for item in report.methods],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return int(
        args.require_all and any(item.status != "available" for item in report.methods)
    )


if __name__ == "__main__":
    raise SystemExit(main())
