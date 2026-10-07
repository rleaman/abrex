"""Run one immutable, cost-bounded Luna extractor development iteration."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from abrex.config import load_resolved_config, serialize_resolved_config
from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.domain import AbbreviationDefinition, CorpusRecord
from abrex.resolvers import (
    ResolverRunResult,
    create_resolver_executor,
    resolver_config_from_resolved,
    write_prediction_artifact,
)

PairKey = tuple[str, int, int, int, int]
PREFLIGHT_PATH = Path(
    "evidence/campaign-2026-10/milestone-b/direct-extraction-preflight-v1.json"
)


def run_iteration(
    config_path: Path,
    output_directory: Path,
    *,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Preflight and optionally execute exactly one configured T062 iteration."""

    config = load_resolved_config((config_path,))
    resolver_config = resolver_config_from_resolved(config)
    records, manifest = _load_corpus(config)
    params = resolver_config.resolver.params
    preflight = _preflight(params, len(records))
    if preflight_only:
        return {"status": "preflight_passed", "preflight": preflight}

    executor = create_resolver_executor(resolver_config)
    result = executor.resolve_documents(
        (record.document for record in records), error_policy="collect"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / "predictions.jsonl"
    corpus_fingerprint = fingerprint_records(records)
    prediction_fingerprint = write_prediction_artifact(
        result,
        predictions_path,
        dataset_fingerprint=corpus_fingerprint,
    )
    usage = getattr(executor.resolver, "usage", None)
    if not isinstance(usage, Mapping):
        raise TypeError("direct extractor usage must be a mapping")
    report = build_readout(
        records,
        result,
        usage=usage,
        preflight=preflight,
        config_path=config_path,
        resolved_config=json.loads(serialize_resolved_config(config, format="json")),
        dataset_id=manifest.dataset_id,
        corpus_fingerprint=corpus_fingerprint,
        predictions_path=predictions_path,
        prediction_fingerprint=prediction_fingerprint,
    )
    report_path = output_directory / "readout.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def build_readout(
    records: Sequence[CorpusRecord],
    run: ResolverRunResult,
    *,
    usage: Mapping[str, object],
    preflight: Mapping[str, object],
    config_path: Path,
    resolved_config: Mapping[str, object],
    dataset_id: str,
    corpus_fingerprint: str,
    predictions_path: Path,
    prediction_fingerprint: str,
) -> dict[str, object]:
    """Build failure-aware metrics without treating failed calls as abstentions."""

    gold = {
        _pair_key(annotation)
        for record in records
        for annotation in record.gold_annotations
    }
    predictions = {
        _pair_key(prediction)
        for record in run.records
        for prediction in record.predictions
    }
    failed_ids = {
        error.document_id
        for error in run.execution_errors
        if error.document_id is not None
    }
    successful_ids = {record.document.document_id for record in records} - failed_ids
    successful_gold = {key for key in gold if key[0] in successful_ids}
    successful_metrics = _prf(
        len(predictions & gold),
        len(predictions - gold),
        len(successful_gold - predictions),
    )
    availability_metrics = _prf(
        len(predictions & gold), len(predictions - gold), len(gold - predictions)
    )
    missing = _candidate_omissions()
    diagnostics = run.diagnostics
    diagnostic_counts = Counter(item.code for item in diagnostics)
    returned_proposals = (
        len(predictions)
        + diagnostic_counts["DIRECT_QUOTE_GROUNDING_FAILED"]
        + diagnostic_counts["DIRECT_DUPLICATE_OUTPUT"]
    )
    grounding_failures = diagnostic_counts["DIRECT_QUOTE_GROUNDING_FAILED"]
    grounding_failure_fraction = (
        grounding_failures / returned_proposals if returned_proposals else 0.0
    )
    failure_fraction = len(failed_ids) / len(records)
    actual_cost = _number(usage, "actual_cost_usd")
    gates = {
        "request_completion": {
            "observed": len(successful_ids),
            "required": 19,
            "passed": len(successful_ids) >= 19,
        },
        "ungroundable_proposal_fraction": {
            "observed": grounding_failure_fraction,
            "maximum": 0.05,
            "passed": grounding_failure_fraction <= 0.05,
        },
        "exact_precision": {
            "observed": successful_metrics["precision"],
            "required": 0.85,
            "passed": successful_metrics["precision"] >= 0.85,
        },
        "exact_recall": {
            "observed": availability_metrics["recall"],
            "required": 0.70,
            "passed": availability_metrics["recall"] >= 0.70,
        },
        "exact_f1": {
            "observed": availability_metrics["f1"],
            "required": 0.756,
            "passed": availability_metrics["f1"] >= 0.756,
        },
        "candidate_omission_recovery": {
            "observed": len(predictions & missing),
            "required": 7,
            "passed": len(predictions & missing) >= 7,
        },
        "cost": {
            "observed_usd": actual_cost,
            "maximum_usd": 0.10,
            "passed": actual_cost <= 0.10,
        },
    }
    all_passed = all(bool(_mapping(value)["passed"]) for value in gates.values())
    return {
        "schema_version": "campaign-2026-10-luna-iteration-v1",
        "status": "development_gate_passed"
        if all_passed
        else "development_gate_failed",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "evidence_class": "assisted_t062_development",
        "git": _git_metadata(),
        "config": {
            "path": config_path.as_posix(),
            "sha256": _sha256(config_path),
            "resolved": resolved_config,
        },
        "corpus": {
            "dataset_id": dataset_id,
            "fingerprint": corpus_fingerprint,
            "documents": len(records),
            "gold_relations": len(gold),
        },
        "execution": {
            "successful_documents": len(successful_ids),
            "failed_documents": len(failed_ids),
            "failed_document_ids": sorted(failed_ids),
            "request_failure_fraction": failure_fraction,
            "usage": dict(usage),
        },
        "grounding": {
            "returned_proposals": returned_proposals,
            "accepted_predictions": len(predictions),
            "failed_proposals": grounding_failures,
            "failure_fraction": grounding_failure_fraction,
            "diagnostic_counts": dict(sorted(diagnostic_counts.items())),
        },
        "strict_exact": {
            "successful_subset": successful_metrics,
            "availability_adjusted": availability_metrics,
            "candidate_omitted_relations": len(missing),
            "candidate_omitted_relations_recovered": len(predictions & missing),
            "recovered_candidate_omission_keys": [
                list(key) for key in sorted(predictions & missing)
            ],
            "false_positive_keys": [list(key) for key in sorted(predictions - gold)],
            "false_negative_keys": [list(key) for key in sorted(gold - predictions)],
        },
        "development_gate": {"criteria": gates, "all_passed": all_passed},
        "preflight": dict(preflight),
        "artifacts": {
            "predictions": {
                "path": predictions_path.as_posix(),
                "sha256": _sha256(predictions_path),
                "fingerprint": prediction_fingerprint,
            }
        },
    }


def _load_corpus(config: object) -> tuple[tuple[CorpusRecord, ...], Any]:
    extras = getattr(config, "model_extra", None)
    raw = extras.get("corpus") if isinstance(extras, Mapping) else None
    if not isinstance(raw, Mapping):
        raise TypeError("configuration requires a corpus mapping")
    params = raw.get("params")
    if not isinstance(params, Mapping):
        raise TypeError("corpus requires params")
    path = params.get("path")
    manifest = params.get("manifest_path")
    if not isinstance(path, str) or not isinstance(manifest, str):
        raise TypeError("corpus paths must be strings")
    return read_canonical_dataset(Path(path), Path(manifest))


def _preflight(params: Mapping[str, object], documents: int) -> dict[str, object]:
    attempts = _integer(params, "maximum_network_attempts")
    max_output = _integer(params, "maximum_output_tokens_per_request")
    max_input = _integer(params, "maximum_estimated_input_tokens")
    retries = _integer(params, "retries")
    input_price = _number(params, "input_usd_per_million_tokens")
    output_price = _number(params, "output_usd_per_million_tokens")
    cap = _number(params, "monetary_cap_usd")
    worst_cost = (
        max_input * input_price + documents * max_output * output_price
    ) / 1_000_000
    if attempts != documents or retries != 0:
        raise ValueError("iteration requires exactly one network attempt per document")
    if cap > 0.10 or worst_cost > cap:
        raise ValueError(
            f"iteration worst-case cost ${worst_cost:.7f} exceeds cap ${cap:.7f}"
        )
    if max_output < 8192:
        raise ValueError("iteration output allowance must be at least 8192 tokens")
    return {
        "documents": documents,
        "maximum_network_attempts": attempts,
        "maximum_output_tokens_per_request": max_output,
        "maximum_estimated_input_tokens": max_input,
        "retries": retries,
        "monetary_cap_usd": cap,
        "worst_case_cost_usd": worst_cost,
        "passed": True,
    }


def _candidate_omissions() -> set[PairKey]:
    raw = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    candidate = _mapping(_mapping(raw)["candidate_judging"])
    result: set[PairKey] = set()
    for value in _sequence(candidate["missing_relations"]):
        item = _mapping(value)
        short = _mapping(item["short_form"])
        long = _mapping(item["long_form"])
        result.add(
            (
                str(item["document_id"]),
                int(short["start"]),
                int(short["end"]),
                int(long["start"]),
                int(long["end"]),
            )
        )
    return result


def _pair_key(value: AbbreviationDefinition) -> PairKey:
    if value.short_form is None or value.long_form is None:
        raise ValueError("strict pair metrics require both occurrence spans")
    return (
        value.document_id,
        value.short_form.start,
        value.short_form.end,
        value.long_form.start,
        value.long_form.end,
    )


def _prf(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _git_metadata() -> dict[str, object]:
    try:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"), capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ("git", "status", "--porcelain"),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _integer(params: Mapping[str, object], name: str) -> int:
    value = params.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _number(params: Mapping[str, object], name: str) -> float:
    value = params.get(name)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as error:
            raise TypeError(f"{name} must be numeric") from error
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric")
    return float(value)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("mapping required")
    return cast(Mapping[str, Any], value)


def _sequence(value: object) -> Sequence[Any]:
    if not isinstance(value, list | tuple):
        raise TypeError("sequence required")
    return cast(Sequence[Any], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected immutable iteration and print its compact result."""

    args = _parser().parse_args(argv)
    report = run_iteration(
        args.config,
        args.output_directory,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
