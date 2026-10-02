"""Calibrate and summarize the frozen Jev development-cache evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora import read_canonical_dataset
from abrex.resolvers.jev import CALIBRATION_GRID, calibrate_threshold

PairKey = tuple[str, int, int, int, int]


def analyze(corpus: Path, manifest: Path, cache: Path) -> dict[str, object]:
    """Return strict-pair calibration, candidate coverage, usage, and latency."""

    records, dataset_manifest = read_canonical_dataset(corpus, manifest)
    gold: set[PairKey] = set()
    for record in records:
        for annotation in record.gold_annotations:
            if annotation.short_form is None or annotation.long_form is None:
                continue
            gold.add(
                (
                    record.document.document_id,
                    annotation.short_form.start,
                    annotation.short_form.end,
                    annotation.long_form.start,
                    annotation.long_form.end,
                )
            )
    candidate_pairs: set[PairKey] = set()
    predicted_scores: dict[PairKey, float] = {}
    requests = 0
    input_tokens = 0
    output_tokens = 0
    latency_seconds = 0.0
    with cache.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise TypeError(f"cache line {line_number} must be an object")
            row = cast(dict[str, Any], raw)
            state = _mapping(row.get("state"), "state")
            document_id = _string(state, "document_id")
            candidates = _mapping(state.get("candidates"), "candidates")
            response = _mapping(row.get("response"), "response")
            choices = _mapping(response.get("choices"), "choices")
            requests += 1
            input_tokens += _optional_int(response.get("input_tokens"))
            output_tokens += _optional_int(response.get("output_tokens"))
            latency_seconds += float(response.get("latency_seconds", 0.0))
            for candidate_id, raw_candidate in candidates.items():
                candidate = _mapping(raw_candidate, "candidate")
                short = _coordinates(candidate, "short_span")
                long = _coordinates(candidate, "long_span")
                forward = (document_id, short[0], short[1], long[0], long[1])
                reverse = (document_id, long[0], long[1], short[0], short[1])
                candidate_pairs.update((forward, reverse))
                answer = _mapping(choices.get(candidate_id), "choice")
                choice = _string(answer, "choice")
                if choice == "not_definition":
                    continue
                prediction = forward if choice == "forward" else reverse
                probabilities = _mapping(answer.get("probabilities"), "probabilities")
                score = float(probabilities[choice])
                predicted_scores[prediction] = max(
                    score, predicted_scores.get(prediction, 0.0)
                )
    observations = tuple(
        (score, pair in gold) for pair, score in predicted_scores.items()
    )
    calibrated = calibrate_threshold(
        observations, grid=CALIBRATION_GRID, total_positives=len(gold)
    )
    covered = gold & candidate_pairs
    cache_sha = hashlib.sha256(cache.read_bytes()).hexdigest()
    return {
        "schema_version": "t059-jev-development-v1",
        "status": "development_evidence",
        "dataset": {
            "id": dataset_manifest.dataset_id,
            "fingerprint": dataset_manifest.fingerprint,
            "documents": len(records),
            "strict_pairs": len(gold),
        },
        "model": "jev-1.13.0",
        "policy_version": "abrex-candidate-choice-v1",
        "cache_sha256": cache_sha,
        "candidate_coverage": {
            "covered_gold_pairs": len(covered),
            "missing_gold_pairs": len(gold - covered),
            "recall_ceiling": len(covered) / len(gold) if gold else 0.0,
            "unique_oriented_candidates": len(candidate_pairs),
        },
        "calibration": {
            "grid": list(CALIBRATION_GRID),
            "threshold": calibrated.threshold,
            "true_positives": calibrated.true_positives,
            "false_positives": calibrated.false_positives,
            "false_negatives": calibrated.false_negatives,
            "precision": calibrated.precision,
            "recall": calibrated.recall,
            "f1": calibrated.f1,
            "tie_break": "precision_then_higher_threshold",
        },
        "usage": {
            "requests": requests,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_input_cost_usd": input_tokens * 0.042 / 1_000_000,
            "summed_request_latency_seconds": latency_seconds,
            "mean_request_latency_seconds": latency_seconds / requests,
        },
        "limitations": [
            "assisted, diagnostically selected development evidence",
            "candidate coverage is separate from Jev judgment quality",
            "threshold must remain frozen for any subsequent blind evaluation",
        ],
    }


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _string(value: Mapping[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise TypeError(f"{name} must be a non-empty string")
    return result


def _coordinates(value: Mapping[str, Any], name: str) -> tuple[int, int]:
    raw = value.get(name)
    if (
        not isinstance(raw, list)
        or len(raw) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in raw)
    ):
        raise TypeError(f"{name} must contain two integer coordinates")
    return cast(tuple[int, int], tuple(raw))


def _optional_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("token usage must be an integer or null")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("evidence/T059/t057-strict-development.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evidence/T059/t057-strict-development.manifest.json"),
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(".artifacts/T059/t057-jev-cache.jsonl"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/artifacts/T059-jev-development.json")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write the deterministic development analysis."""

    args = _parser().parse_args(argv)
    result = analyze(args.corpus, args.manifest, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
