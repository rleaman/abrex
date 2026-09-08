"""Audit the bounded T040 campaign inputs without redesigning on a holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(inputs: tuple[Path, ...], output: Path) -> None:
    artifacts = {path.name: _sha256(path) for path in inputs}
    payload = {
        "schema_version": "t040-campaign-audit-v1",
        "protocol": {
            "corpus": "ab3p_corpus_t022_smoke",
            "matching": "exact_pair",
            "metrics": ["pair_prf", "seeded_article_group_bootstrap"],
            "final_holdout_access": "forbidden",
            "selection": "retain strongest validated baseline unless "
            "predeclared gain is supported",
        },
        "inputs": artifacts,
        "ablations": {
            "native_offset_ab3p": {
                "status": "validated_exploratory",
                "f1": 0.9029850746268657,
            },
            "plodv2_pairing": {
                "status": "validated_exploratory",
                "f1": 0.7790262172284644,
            },
            "schwartz_hearst": {
                "status": "validated_exploratory",
                "f1": 0.8527131782945736,
            },
            "transparent_hybrid": {
                "status": "validated_exploratory",
                "f1": 0.9018181818181819,
            },
            "lexical_local": {
                "status": "no_gain_bounded_pilot",
                "recall": 0.8601398601398601,
            },
            "logistic_regression": {
                "status": "plumbing_smoke_only",
                "scientific_comparison": False,
            },
        },
        "decision": {
            "release_candidate": "native_offset_ab3p",
            "production_improvement_supported": False,
            "reason": "No approved contemporary gold or adequately powered "
            "gold-plus-silver development set is available; hybrid and lexical "
            "pilots do not establish a gain.",
            "holdout_status": "unused_and_reserved",
        },
        "limitations": [
            "T022 is a bounded historical smoke slice, not a representative "
            "final evaluation.",
            "T030 labels remain provisional and were not used to select a "
            "release candidate.",
            "T034 aggregate resource overlap is unknown; no independent "
            "confirmation is claimed.",
            "Runtime and work-scale dictionary quality remain unvalidated.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args(argv)
    build_report(tuple(args.inputs), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
