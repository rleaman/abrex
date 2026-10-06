"""Build the failure-aware Milestone B direct-extraction readout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, median
from typing import Any, cast

PairKey = tuple[str, int, int, int, int]


def build_readout(
    *,
    corpus_path: Path,
    prediction_path: Path,
    cache_path: Path,
    preflight_path: Path,
    output_path: Path,
    markdown_path: Path,
    input_price: float = 0.10,
    output_price: float = 0.50,
) -> dict[str, object]:
    """Reconcile partial predictions without scoring runtime failures as empty."""

    corpus_rows = _jsonl(corpus_path)
    prediction_rows = _jsonl(prediction_path)
    cache_rows = _jsonl(cache_path)
    preflight = _object(preflight_path)
    texts = {
        str(_mapping(row["document"], "document")["document_id"]): str(
            _mapping(row["document"], "document")["text"]
        )
        for row in corpus_rows
    }
    gold = {
        _pair_key(_mapping(annotation, "gold annotation")): annotation
        for row in corpus_rows
        for annotation in _sequence(row.get("gold_annotations"), "gold annotations")
    }
    predictions = {
        _pair_key(_mapping(prediction, "prediction")): prediction
        for row in prediction_rows
        for prediction in _sequence(row.get("predictions"), "predictions")
    }
    failed_ids = {
        str(row["document_id"])
        for row in prediction_rows
        if any(
            _mapping(item, "diagnostic").get("code") == "RESOLVER_EXECUTION_FAILED"
            for item in _sequence(row.get("diagnostics"), "diagnostics")
        )
    }
    successful_ids = set(texts) - failed_ids
    successful_gold = {key for key in gold if key[0] in successful_ids}
    tp = len(predictions.keys() & gold.keys())
    fp = len(predictions.keys() - gold.keys())
    successful_fn = len(successful_gold - predictions.keys())
    successful_metrics = _prf(tp, fp, successful_fn)
    availability_adjusted = _prf(tp, fp, len(gold) - tp)

    candidate = _mapping(preflight["candidate_judging"], "candidate judging")
    missing = {
        (
            str(item["document_id"]),
            int(_mapping(item["short_form"], "missing short")["start"]),
            int(_mapping(item["short_form"], "missing short")["end"]),
            int(_mapping(item["long_form"], "missing long")["start"]),
            int(_mapping(item["long_form"], "missing long")["end"]),
        )
        for raw in _sequence(candidate["missing_relations"], "missing relations")
        for item in (_mapping(raw, "missing relation"),)
    }
    recovered_missing = predictions.keys() & missing

    diagnostics = [
        _mapping(item, "diagnostic")
        for row in prediction_rows
        for item in _sequence(row.get("diagnostics"), "diagnostics")
    ]
    diagnostic_counts = Counter(str(item["code"]) for item in diagnostics)
    unsupported = [
        item for item in diagnostics if item["code"] == "DIRECT_UNSUPPORTED_OUTPUT"
    ]
    invalid_analysis = _invalid_offset_analysis(unsupported, texts)
    returned_proposals = len(predictions) + len(unsupported)
    invalid_fraction = (
        len(unsupported) / returned_proposals if returned_proposals else 0
    )

    cache_responses = [
        _mapping(row["response"], "cache response") for row in cache_rows
    ]
    success_input_tokens = sum(
        int(_mapping(response["usage"], "usage")["input_tokens"])
        for response in cache_responses
    )
    success_output_tokens = sum(
        int(_mapping(response["usage"], "usage")["output_tokens"])
        for response in cache_responses
    )
    latencies = [float(response["latency_seconds"]) for response in cache_responses]
    success_cost = _cost(
        success_input_tokens,
        success_output_tokens,
        input_price=input_price,
        output_price=output_price,
    )
    diagnostic_attempt_cost = _cost(
        747,
        2_048,
        input_price=input_price,
        output_price=output_price,
    )
    failed_final_output_tokens = len(failed_ids) * 4_096
    known_cost_lower_bound = (
        success_cost
        + _cost(
            0,
            failed_final_output_tokens,
            input_price=input_price,
            output_price=output_price,
        )
        + 2 * diagnostic_attempt_cost
    )
    total_cost_upper_bound = 0.045 + 2 * diagnostic_attempt_cost

    failure_fraction = len(failed_ids) / len(prediction_rows)
    gates = {
        "candidate_omitted_recovery": {
            "observed": len(recovered_missing),
            "required": 7,
            "passed": len(recovered_missing) >= 7,
        },
        "successful_subset_exact_precision": {
            "observed": successful_metrics["precision"],
            "required": 0.65,
            "passed": successful_metrics["precision"] >= 0.65,
        },
        "request_failure_fraction": {
            "observed": failure_fraction,
            "maximum": 0.05,
            "passed": failure_fraction <= 0.05,
        },
        "invalid_grounded_output_fraction": {
            "observed": invalid_fraction,
            "maximum": 0.10,
            "passed": invalid_fraction <= 0.10,
        },
        "total_cost_usd": {
            "observed_upper_bound": total_cost_upper_bound,
            "maximum": 0.05,
            "passed": total_cost_upper_bound <= 0.05,
        },
    }
    all_gates_passed = all(
        bool(_mapping(value, "gate")["passed"]) for value in gates.values()
    )

    report: dict[str, object] = {
        "schema_version": "campaign-2026-10-direct-extraction-readout-v1",
        "evidence_class": "assisted_development",
        "status": "negative_result_do_not_advance_unchanged_prompt",
        "artifacts": {
            "corpus": _identity(corpus_path),
            "predictions": _identity(prediction_path),
            "successful_response_cache": _identity(cache_path),
            "preflight": _identity(preflight_path),
        },
        "execution": {
            "documents": len(prediction_rows),
            "successful_documents": len(successful_ids),
            "failed_documents": len(failed_ids),
            "failure_fraction": failure_fraction,
            "failed_document_ids": sorted(failed_ids),
            "failure_reason": "incomplete:max_output_tokens_before_output_text",
            "final_maximum_output_tokens_per_request": 4_096,
            "final_network_retries": 0,
            "provider_requests": 22,
            "provider_request_breakdown": {
                "initial_2048_attempt": 1,
                "diagnostic_2048_attempt": 1,
                "final_4096_batch": 20,
            },
            "non_provider_sandbox_connection_failure": 1,
        },
        "strict_exact": {
            "successful_subset": {
                **successful_metrics,
                "gold_relations": len(successful_gold),
                "prediction_relations": len(predictions),
                "interpretation": (
                    "scorable documents only; never presented as full-run metrics"
                ),
            },
            "availability_adjusted_descriptive": {
                **availability_adjusted,
                "gold_relations": len(gold),
                "prediction_relations": len(predictions),
                "interpretation": (
                    "descriptive lower-availability view only; failed documents are "
                    "not reclassified as scientific empty predictions"
                ),
            },
            "gold_relations_in_failed_documents": len(gold) - len(successful_gold),
            "candidate_omitted_relations": len(missing),
            "candidate_omitted_relations_recovered": len(recovered_missing),
            "recovered_candidate_omitted_keys": [
                list(key) for key in sorted(recovered_missing)
            ],
            "false_positive_keys": [
                list(key) for key in sorted(predictions.keys() - gold.keys())
            ],
        },
        "grounding": {
            "returned_pair_proposals": returned_proposals,
            "accepted_grounded_predictions": len(predictions),
            "unsupported_outputs": len(unsupported),
            "invalid_grounded_output_fraction": invalid_fraction,
            "diagnostic_counts": dict(sorted(diagnostic_counts.items())),
            "unsupported_message_counts": dict(
                sorted(Counter(str(item["message"]) for item in unsupported).items())
            ),
            "offset_analysis": invalid_analysis,
        },
        "usage": {
            "prices_usd_per_million_tokens": {
                "input": input_price,
                "output": output_price,
            },
            "successful_cached_responses": {
                "responses": len(cache_responses),
                "input_tokens": success_input_tokens,
                "output_tokens": success_output_tokens,
                "actual_cost_usd": success_cost,
                "latency_seconds": {
                    "minimum": min(latencies),
                    "median": median(latencies),
                    "mean": mean(latencies),
                    "maximum": max(latencies),
                },
                "returned_models": sorted(
                    {
                        str(response["model"])
                        for response in cache_responses
                        if isinstance(response.get("model"), str)
                    }
                ),
            },
            "failed_final_responses": {
                "responses": len(failed_ids),
                "known_output_tokens": failed_final_output_tokens,
                "input_tokens": "not persisted after evaluator rejected partial run",
            },
            "pre_final_diagnostic_attempts": {
                "responses": 2,
                "input_tokens_each": 747,
                "output_tokens_each": 2_048,
                "cost_usd_each": diagnostic_attempt_cost,
                "basis": (
                    "identical first-document payload and identical max-token "
                    "incomplete response; the second response retained exact usage"
                ),
            },
            "known_cost_lower_bound_usd": known_cost_lower_bound,
            "total_cost_upper_bound_usd": total_cost_upper_bound,
            "upper_bound_basis": (
                "the completed final process enforced a $0.045 actual-usage cap; "
                "add both observed 2,048-token first-document attempts"
            ),
            "authorized_total_cap_usd": 0.05,
        },
        "advancement_gate": {
            "criteria": gates,
            "all_passed": all_gates_passed,
            "decision": "do_not_advance_unchanged_prompt_to_milestone_c",
            "reason": (
                "request failure, invalid grounding, and candidate-omission recovery "
                "criteria failed before any confirmatory use"
            ),
        },
        "review": {
            "unresolved_human_judgments": 0,
            "reason": (
                "the sole exact false positive reuses a reviewed long form with a "
                "later non-defining short-form occurrence; all other rejected output "
                "failed literal source grounding"
            ),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_markdown(report), encoding="utf-8", newline="\n")
    return report


def _invalid_offset_analysis(
    diagnostics: Sequence[Mapping[str, Any]], texts: Mapping[str, str]
) -> dict[str, object]:
    multiplicity: Counter[str] = Counter()
    deltas: Counter[int] = Counter()
    endpoint_patterns: Counter[str] = Counter()
    examples: list[dict[str, object]] = []
    pattern = re.compile(r"^\[(\d+),(\d+)\)$")
    for item in diagnostics:
        document_id = str(item["document_id"])
        details = _mapping(item["details"], "diagnostic details")
        endpoint = "short_form" if "short_form" in str(item["message"]) else "long_form"
        quote = str(details[endpoint])
        match = pattern.match(str(details[f"{endpoint.split('_')[0]}_span"]))
        if match is None:
            raise ValueError(f"invalid diagnostic span: {details}")
        stated_start, stated_end = (int(value) for value in match.groups())
        occurrences = _occurrences(texts[document_id], quote)
        category = (
            "absent"
            if not occurrences
            else "unique"
            if len(occurrences) == 1
            else "repeated"
        )
        multiplicity[category] += 1
        exact_start = stated_start in occurrences
        exact_end = stated_end == stated_start + len(quote)
        start_status = "correct" if exact_start else "wrong"
        end_status = "correct" if exact_end else "wrong"
        endpoint_patterns[f"start_{start_status}_end_{end_status}"] += 1
        if len(occurrences) == 1:
            deltas[occurrences[0] - stated_start] += 1
        examples.append(
            {
                "document_id": document_id,
                "endpoint": endpoint,
                "quote": quote,
                "stated_span": [stated_start, stated_end],
                "literal_occurrence_starts": occurrences,
                "multiplicity": category,
            }
        )
    return {
        "literal_quote_multiplicity": dict(sorted(multiplicity.items())),
        "stated_span_error_patterns": dict(sorted(endpoint_patterns.items())),
        "unique_quote_start_delta": {
            str(key): value for key, value in sorted(deltas.items())
        },
        "examples": examples,
        "interpretation": (
            "quotes were present but model-supplied offsets were invalid; no offset "
            "search or repair entered exact scoring"
        ),
    }


def _occurrences(text: str, quote: str) -> list[int]:
    result: list[int] = []
    start = 0
    while True:
        index = text.find(quote, start)
        if index < 0:
            return result
        result.append(index)
        start = index + 1


def _pair_key(value: Mapping[str, Any]) -> PairKey:
    short = _mapping(value["short_form"], "short form")
    long = _mapping(value["long_form"], "long form")
    return (
        str(value["document_id"]),
        int(short["start"]),
        int(short["end"]),
        int(long["start"]),
        int(long["end"]),
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


def _cost(
    input_tokens: int,
    output_tokens: int,
    *,
    input_price: float,
    output_price: float,
) -> float:
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def _identity(path: Path) -> dict[str, object]:
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"JSONL object required: {path}")
        values.append(cast(dict[str, Any], value))
    return values


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, list | tuple):
        raise TypeError(f"{name} must be an array")
    return cast(Sequence[Any], value)


def _markdown(report: Mapping[str, object]) -> str:
    execution = _mapping(report["execution"], "execution")
    strict = _mapping(report["strict_exact"], "strict exact")
    subset = _mapping(strict["successful_subset"], "successful subset")
    adjusted = _mapping(
        strict["availability_adjusted_descriptive"], "availability adjusted"
    )
    grounding = _mapping(report["grounding"], "grounding")
    usage = _mapping(report["usage"], "usage")
    gate = _mapping(report["advancement_gate"], "advancement gate")
    success_usage = _mapping(usage["successful_cached_responses"], "successful usage")
    successful_documents = execution["successful_documents"]
    documents = execution["documents"]
    failed_documents = execution["failed_documents"]
    failure_fraction = float(execution["failure_fraction"])
    accepted = grounding["accepted_grounded_predictions"]
    unsupported = grounding["unsupported_outputs"]
    returned = grounding["returned_pair_proposals"]
    invalid_fraction = float(grounding["invalid_grounded_output_fraction"])
    return f"""# Milestone B direct-extraction result

This is assisted development evidence. The frozen GPT-6 Luna prompt does not
advance unchanged to Milestone C.

## Execution

- Completed structured responses: {successful_documents} / {documents}.
- Runtime failures: {failed_documents} / {documents} ({failure_fraction:.1%}), all
  `max_output_tokens` before output text.
- Accepted grounded predictions: {accepted}.
- Invalid grounded proposals: {unsupported} / {returned} ({invalid_fraction:.1%});
  every rejection was serialized and none was repaired from gold.

## Exact evidence

On the {successful_documents} scorable documents only: TP
{subset["true_positives"]}, FP {subset["false_positives"]}, and FN
{subset["false_negatives"]}. Precision is {float(subset["precision"]):.4f},
recall is {float(subset["recall"]):.4f}, and F1 is
{float(subset["f1"]):.4f}. This is not a full-run score.

The availability-adjusted descriptive view has precision
{float(adjusted["precision"]):.4f}, recall {float(adjusted["recall"]):.4f}, and
F1 {float(adjusted["f1"]):.4f}. It does not relabel failed documents as
legitimate empty predictions. Only {strict["candidate_omitted_relations_recovered"]} of
{strict["candidate_omitted_relations"]} candidate-omitted gold relations was
recovered.

## Cost and decision

Exact successful-cache usage cost was
${float(success_usage["actual_cost_usd"]):.7f}.
Including the two diagnostic attempts and the final batch, total spend is bounded
between ${float(usage["known_cost_lower_bound_usd"]):.7f} and
${float(usage["total_cost_upper_bound_usd"]):.7f}, below the authorized $0.05.

The predeclared request-failure, invalid-grounding, and candidate-omission
recovery gates failed. Decision: `{gate["decision"]}`. The one exact false
positive is a later non-defining occurrence of an already reviewed short/long
form, so no unresolved human adjudication remains.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path("evidence/campaign-2026-10/milestone-b")
    parser.add_argument("--corpus", type=Path, default=base / "t062-development.jsonl")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=base / "direct-extraction-predictions-v1.jsonl",
    )
    parser.add_argument(
        "--cache", type=Path, default=base / "direct-extraction-cache.jsonl"
    )
    parser.add_argument(
        "--preflight", type=Path, default=base / "direct-extraction-preflight-v1.json"
    )
    parser.add_argument(
        "--output", type=Path, default=base / "direct-extraction-readout-v1.json"
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/artifacts/campaign-2026-10-milestone-b-result.md"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build the readout and print its compact decision."""

    args = _parser().parse_args(argv)
    report = build_readout(
        corpus_path=args.corpus,
        prediction_path=args.predictions,
        cache_path=args.cache,
        preflight_path=args.preflight,
        output_path=args.output,
        markdown_path=args.markdown,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "execution": report["execution"],
                "advancement_gate": report["advancement_gate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
