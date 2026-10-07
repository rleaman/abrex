"""Validate and bind completed Milestone C TypeSafe and Luna execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

TYPESAFE_USD_PER_MILLION_INPUT_TOKENS = Decimal("0.042")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_lines(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"{path} contains a non-object JSONL row")
        rows.append(value)
    return rows


def _object(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


def _prediction_summary(path: Path) -> dict[str, object]:
    rows = _json_lines(path)
    diagnostics = Counter(
        str(_object(item, "diagnostic").get("code"))
        for row in rows
        for item in row.get("diagnostics", [])
    )
    return {
        "path": path.as_posix(),
        "sha256": _sha256(path),
        "records": len(rows),
        "predictions": sum(len(row.get("predictions", [])) for row in rows),
        "diagnostics": dict(sorted(diagnostics.items())),
    }


def build_receipt(
    *,
    clp_receipt_path: Path,
    clp_response_path: Path,
    jev_cache_path: Path,
    jev_predictions_path: Path,
    luna_cache_path: Path,
    luna_attempts_path: Path,
    luna_predictions_path: Path,
    output_path: Path,
    azure_input_rate: Decimal,
    azure_output_rate: Decimal,
) -> dict[str, object]:
    """Check every authorized boundary and write an immutable receipt."""

    clp = _object(json.loads(clp_receipt_path.read_text(encoding="utf-8")), "clp")
    jev_rows = _json_lines(jev_cache_path)
    jev_responses = [_object(row.get("response"), "Jev response") for row in jev_rows]
    jev_input_tokens = sum(int(row.get("input_tokens") or 0) for row in jev_responses)
    jev_requests = sum(int(row.get("network_attempts") or 0) for row in jev_responses)
    clp_input_tokens = int(clp.get("input_tokens") or 0)
    clp_requests = int(clp.get("network_requests") or 0)
    typesafe_input_tokens = clp_input_tokens + jev_input_tokens
    typesafe_requests = clp_requests + jev_requests
    typesafe_cost = (
        Decimal(typesafe_input_tokens)
        * TYPESAFE_USD_PER_MILLION_INPUT_TOKENS
        / Decimal(1_000_000)
    )
    if typesafe_requests > 65:
        raise ValueError("TypeSafe request cap exceeded")
    if typesafe_input_tokens > 724_000:
        raise ValueError("TypeSafe input-token cap exceeded")
    if typesafe_cost > Decimal("0.05"):
        raise ValueError("TypeSafe monetary cap exceeded")
    if set(str(row.get("model")) for row in jev_responses) != {"jev-1.13.0"}:
        raise ValueError("Jev candidate responses did not use the frozen model")
    if clp.get("returned_model") != "jev-1.13.0":
        raise ValueError("CLP response did not use the frozen model")

    luna_rows = _json_lines(luna_cache_path)
    luna_responses = [
        _object(row.get("response"), "Luna response") for row in luna_rows
    ]
    luna_input_tokens = sum(
        int(_object(row.get("usage"), "Luna usage").get("input_tokens") or 0)
        for row in luna_responses
    )
    luna_output_tokens = sum(
        int(_object(row.get("usage"), "Luna usage").get("output_tokens") or 0)
        for row in luna_responses
    )
    luna_cost = (
        Decimal(luna_input_tokens) * azure_input_rate
        + Decimal(luna_output_tokens) * azure_output_rate
    ) / Decimal(1_000_000)
    attempt_rows = _json_lines(luna_attempts_path)
    attempt_events = Counter(str(row.get("event")) for row in attempt_rows)
    if len(luna_rows) > 120 or attempt_events != {"started": 120, "finished": 120}:
        raise ValueError("Luna request/attempt boundary does not reconcile")
    if luna_input_tokens > 201_000:
        raise ValueError("Luna input-token cap exceeded")
    if luna_cost > Decimal("0.10"):
        raise ValueError("Luna monetary cap exceeded")
    if set(str(row.get("model")) for row in luna_responses) != {"gpt-6-luna"}:
        raise ValueError("Luna responses did not use the frozen model")

    receipt: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-online-execution-v1",
        "status": "complete_within_authorized_caps",
        "prediction_scoring_status": "withheld_pending_second_review_and_adjudication",
        "typesafe": {
            "pricing_source": "https://typesafe.ai/blog/introducing-system-one-models-and-jev",
            "input_usd_per_million_tokens": str(TYPESAFE_USD_PER_MILLION_INPUT_TOKENS),
            "network_requests": typesafe_requests,
            "input_tokens": typesafe_input_tokens,
            "estimated_cost_usd": str(typesafe_cost),
            "authorized_caps": {
                "network_requests": 65,
                "input_tokens": 724000,
                "monetary_usd": "0.05",
                "retries": 0,
            },
            "clp": {
                **dict(clp),
                "receipt_sha256": _sha256(clp_receipt_path),
                "response_path": clp_response_path.as_posix(),
                "response_sha256": _sha256(clp_response_path),
            },
            "candidate_judge": {
                "model": "jev-1.13.0",
                "network_requests": jev_requests,
                "input_tokens": jev_input_tokens,
                "cache_path": jev_cache_path.as_posix(),
                "cache_sha256": _sha256(jev_cache_path),
                "predictions": _prediction_summary(jev_predictions_path),
            },
        },
        "luna": {
            "model": "gpt-6-luna",
            "prompt_version": "abrex-quote-grounded-2026-10-06-i02",
            "network_attempts": len(luna_rows),
            "retries": 0,
            "input_tokens": luna_input_tokens,
            "output_tokens": luna_output_tokens,
            "actual_cost_usd": str(luna_cost),
            "authorized_caps": {
                "network_attempts": 120,
                "estimated_input_tokens": 201000,
                "maximum_output_tokens_per_request": 8192,
                "monetary_usd": "0.10",
                "retries": 0,
            },
            "cache_path": luna_cache_path.as_posix(),
            "cache_sha256": _sha256(luna_cache_path),
            "attempt_ledger_path": luna_attempts_path.as_posix(),
            "attempt_ledger_sha256": _sha256(luna_attempts_path),
            "attempt_events": dict(sorted(attempt_events.items())),
            "predictions": _prediction_summary(luna_predictions_path),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    evidence = Path("evidence/campaign-2026-10/milestone-c")
    parser.add_argument(
        "--clp-receipt", type=Path, default=evidence / "clp-live-receipt-v1.json"
    )
    parser.add_argument(
        "--clp-response", type=Path, default=evidence / "clp-full-response-v1.json"
    )
    parser.add_argument(
        "--jev-cache", type=Path, default=evidence / "jev-confirmatory-cache-v1.jsonl"
    )
    parser.add_argument(
        "--jev-predictions", type=Path, default=evidence / "predictions-jev-v1.jsonl"
    )
    parser.add_argument(
        "--luna-cache", type=Path, default=evidence / "luna-confirmatory-cache-v1.jsonl"
    )
    parser.add_argument(
        "--luna-attempts",
        type=Path,
        default=evidence / "luna-confirmatory-attempts-v1.jsonl",
    )
    parser.add_argument(
        "--luna-predictions", type=Path, default=evidence / "predictions-luna-v1.jsonl"
    )
    parser.add_argument(
        "--output", type=Path, default=evidence / "online-execution-receipt-v1.json"
    )
    args = parser.parse_args(argv)
    receipt = build_receipt(
        clp_receipt_path=args.clp_receipt,
        clp_response_path=args.clp_response,
        jev_cache_path=args.jev_cache,
        jev_predictions_path=args.jev_predictions,
        luna_cache_path=args.luna_cache,
        luna_attempts_path=args.luna_attempts,
        luna_predictions_path=args.luna_predictions,
        output_path=args.output,
        azure_input_rate=Decimal(
            os.environ["AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS"]
        ),
        azure_output_rate=Decimal(
            os.environ["AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS"]
        ),
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
