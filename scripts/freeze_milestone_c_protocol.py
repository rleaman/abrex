"""Freeze the explicitly approved Milestone C protocol without drawing a sample."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast


def freeze_protocol(
    preflight_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Validate the prepared proposal and write its immutable approval record."""

    preflight = _object(preflight_path)
    if preflight.get("status") != "draft_pending_protocol_approval_and_sample_freeze":
        raise ValueError("Milestone C preflight is not the prepared approval draft")
    sample = _mapping(preflight.get("proposed_sample"), "proposed sample")
    criteria = _mapping(
        preflight.get("proposed_success_criteria"), "proposed success criteria"
    )
    dispositions = _mapping(preflight.get("method_dispositions"), "method dispositions")
    methods = dispositions.get("confirmatory_methods")
    contrasts = criteria.get("confirmatory_primary_contrasts")
    if not isinstance(methods, list) or len(methods) != 6:
        raise ValueError("prepared protocol must contain six confirmatory methods")
    if not isinstance(contrasts, list) or len(contrasts) != 2:
        raise ValueError("prepared protocol must contain two primary contrasts")
    if sample.get("total_article_groups") != 72 or sample.get("total_passages") != 120:
        raise ValueError(
            "prepared protocol sample differs from the approved 72/120 design"
        )

    frozen = {
        "schema_version": "campaign-2026-10-milestone-c-protocol-v1",
        "status": "approved_and_frozen",
        "approved_at": "2026-10-06",
        "approval": {
            "actor": "user/scientific lead",
            "response": "Approve the Milestone C protocol as prepared.",
            "provenance": "conversation user message on 2026-10-06",
        },
        "preflight": {
            "path": preflight_path.as_posix(),
            "sha256": _sha256(preflight_path),
            "schema_version": preflight.get("schema_version"),
        },
        "sample": sample,
        "methods": {
            "confirmatory": methods,
            "inventory": preflight.get("method_inventory"),
            "fixed_resource_identities": preflight.get("fixed_resource_identities"),
        },
        "success_criteria": criteria,
        "reporting_contract": preflight.get("reporting_contract"),
        "exclusions": preflight.get("exclusions"),
        "authorization_boundary": {
            "authorized_now": [
                "source-only sample acquisition and freeze",
                "source-structure sidecar construction",
                "prediction-blind review packet construction and testing",
                "rules-only CLP dry run without scientific-data model requests",
            ],
            "not_authorized": [
                "TypeSafe scientific-data requests or spend",
                "confirmatory resolver prediction runs",
                "annotation reveal before lock",
                "additional Azure OpenAI requests",
            ],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return frozen


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/preflight-v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/protocol-v1.json"),
    )
    args = parser.parse_args(argv)
    frozen = freeze_protocol(args.preflight, args.output)
    print(
        json.dumps(
            {"status": frozen["status"], "output": str(args.output)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
