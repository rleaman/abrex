"""Calibrate and summarize split-question Jev development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from abrex.corpora import read_canonical_dataset
from abrex.resolvers.jev import CALIBRATION_GRID

PairKey = tuple[str, int, int, int, int]


@dataclass(frozen=True, slots=True)
class CandidateJudgment:
    """One source-grounded candidate and its independent judgments."""

    prediction: PairKey | None
    definition_probability: float
    orientation_probability: float


@dataclass(frozen=True, slots=True)
class SplitCalibration:
    """Joint thresholds and resulting strict-pair counts."""

    definition_threshold: float
    orientation_threshold: float
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def calibrate_split_thresholds(
    judgments: Sequence[CandidateJudgment],
    gold: set[PairKey],
    *,
    grid: Sequence[float] = CALIBRATION_GRID,
) -> SplitCalibration:
    """Maximize strict pair F1, then precision, then the higher thresholds."""

    if not judgments:
        raise ValueError("split calibration requires at least one judgment")
    if not grid:
        raise ValueError("calibration grid must not be empty")
    if any(not 0 <= threshold <= 1 for threshold in grid):
        raise ValueError("calibration thresholds must be between zero and one")
    results: list[SplitCalibration] = []
    for definition_threshold in grid:
        for orientation_threshold in grid:
            predicted = {
                item.prediction
                for item in judgments
                if item.prediction is not None
                and item.definition_probability >= definition_threshold
                and item.orientation_probability >= orientation_threshold
            }
            true_positives = len(predicted & gold)
            false_positives = len(predicted - gold)
            false_negatives = len(gold - predicted)
            precision = (
                true_positives / (true_positives + false_positives)
                if true_positives + false_positives
                else 0.0
            )
            recall = true_positives / len(gold) if gold else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
            results.append(
                SplitCalibration(
                    definition_threshold,
                    orientation_threshold,
                    true_positives,
                    false_positives,
                    false_negatives,
                    precision,
                    recall,
                    f1,
                )
            )
    return max(
        results,
        key=lambda item: (
            item.f1,
            item.precision,
            item.definition_threshold,
            item.orientation_threshold,
        ),
    )


def analyze(corpus: Path, manifest: Path, cache: Path) -> dict[str, object]:
    """Return joint calibration, candidate coverage, usage, and latency."""

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
    judgments: list[CandidateJudgment] = []
    orientation_counts: Counter[str] = Counter()
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
            if row.get("policy_version") != "abrex-candidate-split-v2":
                raise ValueError(f"cache line {line_number} is not split-policy data")
            state = _mapping(row.get("state"), "state")
            document_id = _string(state, "document_id")
            candidates = _mapping(state.get("candidates"), "candidates")
            response = _mapping(row.get("response"), "response")
            choices = _mapping(response.get("choices"), "choices")
            nouls = _mapping(response.get("nouls"), "nouls")
            requests += 1
            input_tokens += _optional_int(response.get("input_tokens"))
            output_tokens += _optional_int(response.get("output_tokens"))
            latency_seconds += float(response.get("latency_seconds", 0.0))
            for candidate_id, raw_candidate in candidates.items():
                candidate = _mapping(raw_candidate, "candidate")
                first = _coordinates(candidate, "first_span")
                second = _coordinates(candidate, "second_span")
                first_short = (
                    document_id,
                    first[0],
                    first[1],
                    second[0],
                    second[1],
                )
                second_short = (
                    document_id,
                    second[0],
                    second[1],
                    first[0],
                    first[1],
                )
                candidate_pairs.update((first_short, second_short))
                definition = _mapping(
                    nouls.get(f"{candidate_id}_definition"), "definition"
                )
                orientation = _mapping(
                    choices.get(f"{candidate_id}_orientation"), "orientation"
                )
                orientation_choice = _string(orientation, "choice")
                orientation_counts[orientation_choice] += 1
                probabilities = _mapping(
                    orientation.get("probabilities"), "probabilities"
                )
                prediction = {
                    "first_is_short_form": first_short,
                    "second_is_short_form": second_short,
                    "unclear": None,
                }.get(orientation_choice)
                if orientation_choice not in {
                    "first_is_short_form",
                    "second_is_short_form",
                    "unclear",
                }:
                    raise ValueError(
                        f"invalid orientation choice {orientation_choice!r}"
                    )
                judgments.append(
                    CandidateJudgment(
                        prediction,
                        float(definition["probability"]),
                        float(probabilities[orientation_choice]),
                    )
                )
    calibrated = calibrate_split_thresholds(judgments, gold)
    covered = gold & candidate_pairs
    cache_sha = hashlib.sha256(cache.read_bytes()).hexdigest()
    return {
        "schema_version": "t059-jev-split-development-v2",
        "status": "development_evidence",
        "dataset": {
            "id": dataset_manifest.dataset_id,
            "fingerprint": dataset_manifest.fingerprint,
            "documents": len(records),
            "strict_pairs": len(gold),
        },
        "model": "jev-1.13.0",
        "policy_version": "abrex-candidate-split-v2",
        "cache_sha256": cache_sha,
        "candidate_coverage": {
            "covered_gold_pairs": len(covered),
            "missing_gold_pairs": len(gold - covered),
            "recall_ceiling": len(covered) / len(gold) if gold else 0.0,
            "unique_oriented_candidates": len(candidate_pairs),
        },
        "judgments": {
            "candidates": len(judgments),
            "orientation_choices": dict(sorted(orientation_counts.items())),
        },
        "calibration": {
            "grid": list(CALIBRATION_GRID),
            "definition_threshold": calibrated.definition_threshold,
            "orientation_threshold": calibrated.orientation_threshold,
            "true_positives": calibrated.true_positives,
            "false_positives": calibrated.false_positives,
            "false_negatives": calibrated.false_negatives,
            "precision": calibrated.precision,
            "recall": calibrated.recall,
            "f1": calibrated.f1,
            "tie_break": (
                "precision_then_higher_definition_then_orientation_threshold"
            ),
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
            "joint thresholds must remain frozen for subsequent blind evaluation",
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
        default=Path(".artifacts/T059/t057-jev-split-v2-cache.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/artifacts/T059-jev-split-development.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write the deterministic split-policy development analysis."""

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
