"""Consolidate the bounded Luna quote-grounded development iterations."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

ITERATION_PATHS = (
    Path("evidence/campaign-2026-10/milestone-b/luna-iterations/i01/readout.json"),
    Path("evidence/campaign-2026-10/milestone-b/luna-iterations/i02/readout.json"),
)


def build_summary(output_path: Path, markdown_path: Path) -> dict[str, object]:
    """Bind both immutable iterations and select the first gate-passing version."""

    readouts = [_object(path) for path in ITERATION_PATHS]
    iterations: list[dict[str, object]] = []
    for number, (path, readout) in enumerate(
        zip(ITERATION_PATHS, readouts, strict=True), start=1
    ):
        strict = _mapping(readout["strict_exact"])
        metrics = _mapping(strict["availability_adjusted"])
        execution = _mapping(readout["execution"])
        usage = _mapping(execution["usage"])
        grounding = _mapping(readout["grounding"])
        gate = _mapping(readout["development_gate"])
        iterations.append(
            {
                "iteration": number,
                "path": path.as_posix(),
                "sha256": _sha256(path),
                "status": readout["status"],
                "successful_documents": execution["successful_documents"],
                "true_positives": metrics["true_positives"],
                "false_positives": metrics["false_positives"],
                "false_negatives": metrics["false_negatives"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "candidate_omissions_recovered": strict[
                    "candidate_omitted_relations_recovered"
                ],
                "grounding_failure_fraction": grounding["failure_fraction"],
                "actual_cost_usd": usage["actual_cost_usd"],
                "all_gates_passed": gate["all_passed"],
            }
        )
    selected = iterations[1]
    if selected["all_gates_passed"] is not True:
        raise ValueError("iteration 2 must pass the frozen development gate")
    total_cost = sum(_number(item["actual_cost_usd"]) for item in iterations)
    summary: dict[str, object] = {
        "schema_version": "campaign-2026-10-luna-iteration-summary-v1",
        "evidence_class": "assisted_t062_development",
        "status": "quote_grounded_extractor_selected_for_blind_evaluation",
        "authorization": {
            "maximum_iterations": 10,
            "per_iteration_cap_usd": 0.10,
            "iterations_executed": 2,
            "cumulative_actual_cost_usd": total_cost,
        },
        "iterations": iterations,
        "selection": {
            "iteration": 2,
            "prompt_version": "abrex-quote-grounded-2026-10-06-i02",
            "reasoning_effort": "low",
            "maximum_output_tokens_per_request": 8192,
            "decision": "freeze_for_new_prediction_blind_evaluation",
            "stop_reason": (
                "the first failure-directed revision passed every predeclared "
                "development gate; further T062 tuning would increase overfitting"
            ),
            "new_azure_requests_required_before_blind_sample": False,
        },
        "remaining_error_accounting": {
            "false_positives": {
                "out_of_scope_diagnostic_relations": 5,
                "long_form_boundary_mismatch": 1,
            },
            "false_negatives": {
                "missed_target_definitions": 5,
                "overlapping_alternative_gold_boundaries": 3,
                "long_form_boundary_mismatch": 1,
            },
            "quote_grounding_failures": {
                "count": 2,
                "strict_target_relations_lost": 0,
                "interpretation": (
                    "both were diagnostic representation-limited elliptical "
                    "relations and remained outside strict target scoring"
                ),
            },
        },
        "scientific_boundary": (
            "T062 is exposed assisted development evidence. The selected extractor "
            "requires a newly annotated prediction-blind sample before any "
            "generalization or confirmatory claim."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_markdown(summary), encoding="utf-8", newline="\n")
    return summary


def _markdown(summary: Mapping[str, object]) -> str:
    iterations = _sequence(summary["iterations"])
    first = _mapping(iterations[0])
    second = _mapping(iterations[1])
    authorization = _mapping(summary["authorization"])
    header = (
        "| Iteration | TP | FP | FN | Precision | Recall | F1 | "
        "Omission recovery | Grounding failure | Cost |"
    )
    separator = "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    first_row = _iteration_row(first)
    second_row = _iteration_row(second)
    return f"""# Luna quote-grounded extractor development result

The quote-grounded extractor passed every predeclared T062 development gate on
iteration 2 and is frozen for evaluation on new prediction-blind annotations.
No further T062 tuning or Azure request is warranted before that evaluation.

{header}
{separator}
{first_row}
{second_row}

Both iterations completed structured output for all 20 documents. Iteration 2
used low reasoning, an 8,192-token output allowance, exact evidence quotations,
and deterministic Unicode offset recovery. It produced 58 TP, six FP, and nine
FN, for precision 0.9063, recall 0.8657, and F1 0.8855. It recovered nine of the
14 relations omitted by the candidate generators. Two of 66 proposals failed
literal evidence grounding; both were diagnostic representation-limited
relations outside strict target scoring.

Five of the remaining six false positives are reviewed out-of-scope diagnostic
naming/code relations. Three of the nine false negatives are overlapping
alternative gold boundaries for occurrences where another boundary was matched.
These remain visible; they were not repaired or removed from the strict totals.

Two of the authorized ten iterations were used. Cumulative actual provider cost
was ${float(authorization["cumulative_actual_cost_usd"]):.7f}; each iteration
remained independently below its $0.10 cap. Iteration 2 is selected because it
is the first version to pass every frozen development gate. Continuing to tune
against exposed T062 gold would add overfitting without answering generalization.
"""


def _iteration_row(value: Mapping[str, Any]) -> str:
    return (
        f"| {value['iteration']} | {value['true_positives']} | "
        f"{value['false_positives']} | {value['false_negatives']} | "
        f"{_number(value['precision']):.4f} | {_number(value['recall']):.4f} | "
        f"{_number(value['f1']):.4f} | "
        f"{value['candidate_omissions_recovered']}/14 | "
        f"{_number(value['grounding_failure_fraction']):.1%} | "
        f"${_number(value['actual_cost_usd']):.7f} |"
    )


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


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


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("number required")
    return float(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-b/luna-iterations/summary-v1.json"
        ),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/artifacts/campaign-2026-10-luna-iteration-result.md"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build the summary and print its selected version."""

    args = _parser().parse_args(argv)
    summary = build_summary(args.output, args.markdown)
    print(json.dumps(summary["selection"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
