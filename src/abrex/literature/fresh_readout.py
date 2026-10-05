"""T067 frozen fresh-check scoring and decision readout."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.jobs import JobResultManifest
from abrex.literature.development_readout import PairKey, pair_metrics, prediction_keys
from abrex.literature.review_models import fingerprint
from abrex.resolvers import read_prediction_artifact


def method_summary(
    predictions: Sequence[PairKey],
    strict: set[PairKey],
    diagnostic: set[PairKey],
    *,
    case_ids: set[str],
) -> dict[str, object]:
    """Score one method and expose coverage and empty-passage errors."""

    selected = [item for item in predictions if item[0] in case_ids]
    selected_strict = {item for item in strict if item[0] in case_ids}
    selected_diagnostic = {item for item in diagnostic if item[0] in case_ids}
    metrics = pair_metrics(selected, selected_strict, selected_diagnostic)
    gold_cases = {item[0] for item in selected_strict}
    true_positive_cases = {item[0] for item in selected if item in selected_strict}
    empty_cases = case_ids - gold_cases
    empty_predictions = [item for item in selected if item[0] in empty_cases]
    return {
        **metrics,
        "strict_pair_coverage": metrics["recall"],
        "gold_positive_cases": len(gold_cases),
        "gold_positive_cases_with_true_positive": len(true_positive_cases),
        "gold_positive_case_coverage": (
            len(true_positive_cases) / len(gold_cases) if gold_cases else 0.0
        ),
        "empty_strict_cases": len(empty_cases),
        "empty_passage_false_positives": sum(
            item not in selected_diagnostic for item in empty_predictions
        ),
        "empty_passage_outside_target_matches": sum(
            item in selected_diagnostic for item in empty_predictions
        ),
    }


def materialize_fresh_readout(
    *,
    prediction_corpus_path: Path,
    prediction_corpus_manifest_path: Path,
    gold_corpus_path: Path,
    gold_corpus_manifest_path: Path,
    ledger_path: Path,
    run_manifest_path: Path,
    prediction_paths: Mapping[str, Path],
    result_paths: Mapping[str, Path],
    report_path: Path,
    report_markdown_path: Path,
    disposition_path: Path,
) -> dict[str, object]:
    """Validate imported results, score the frozen union, and freeze the report."""

    repository_root = report_path.resolve().parents[2]
    run_manifest = _read_object(run_manifest_path)
    ledger = _read_object(ledger_path)
    prediction_records, prediction_manifest = read_canonical_dataset(
        prediction_corpus_path, prediction_corpus_manifest_path
    )
    gold_records, _ = read_canonical_dataset(
        gold_corpus_path, gold_corpus_manifest_path
    )
    prediction_fingerprint = fingerprint_records(prediction_records)
    if prediction_fingerprint != prediction_manifest.fingerprint:
        raise ValueError("prediction corpus identity changed")
    prediction_documents = {
        record.document.document_id: record.document for record in prediction_records
    }
    gold_documents = {
        record.document.document_id: record.document for record in gold_records
    }
    if prediction_documents != gold_documents:
        raise ValueError(
            "prediction and local gold corpora do not contain identical text"
        )
    _validate_run_inputs(run_manifest, ledger_path, prediction_fingerprint)

    required = {"schwartz_hearst", "plodv2_pairing"}
    if set(prediction_paths) != required or set(result_paths) != required:
        raise ValueError("T067 requires exactly the frozen baseline and PLOD component")
    artifacts = {
        name: read_prediction_artifact(
            path,
            documents=prediction_documents,
            expected_dataset_fingerprint=prediction_fingerprint,
        )
        for name, path in prediction_paths.items()
    }
    results = {
        name: _validated_result(
            result_paths[name], prediction_paths[name], name, prediction_fingerprint
        )
        for name in required
    }
    runtime_failures = sum(result.status != "complete" for result in results.values())
    method_predictions = {
        name: prediction_keys(artifact) for name, artifact in artifacts.items()
    }
    baseline = method_predictions["schwartz_hearst"]
    plod = method_predictions["plodv2_pairing"]
    challenger = list(dict.fromkeys([*baseline, *plod]))
    methods = {
        "schwartz_hearst": baseline,
        "plodv2_pairing": plod,
        "transparent_hybrid_exact_union_sh_plodv2": challenger,
    }
    strict = {
        (
            record.document.document_id,
            annotation.short_form.start,
            annotation.short_form.end,
            annotation.long_form.start,
            annotation.long_form.end,
        )
        for record in gold_records
        for annotation in record.gold_annotations
        if annotation.short_form is not None and annotation.long_form is not None
    }
    cases = _ledger_cases(ledger)
    diagnostic = _diagnostic_keys(cases)
    all_ids = set(prediction_documents)
    arm_ids = {
        arm: {str(case["case_id"]) for case in cases if case["evaluation_arm"] == arm}
        for arm in ("prose", "table_or_list")
    }
    summaries = {
        name: {
            "overall": method_summary(values, strict, diagnostic, case_ids=all_ids),
            "by_arm": {
                arm: method_summary(values, strict, diagnostic, case_ids=ids)
                for arm, ids in arm_ids.items()
            },
        }
        for name, values in methods.items()
    }
    baseline_correct = set(baseline) & strict
    challenger_correct = set(challenger) & strict
    baseline_errors = set(baseline) - strict - diagnostic
    challenger_errors = set(challenger) - strict - diagnostic
    unique_additions = challenger_correct - baseline_correct
    additional_false_positives = challenger_errors - baseline_errors
    baseline_overall = cast(
        Mapping[str, object], summaries["schwartz_hearst"]["overall"]
    )
    challenger_overall = cast(
        Mapping[str, object],
        summaries["transparent_hybrid_exact_union_sh_plodv2"]["overall"],
    )
    baseline_f1 = _float(baseline_overall["f1"])
    challenger_f1 = _float(challenger_overall["f1"])
    tolerance_checks = {
        "strict_pair_f1_exceeds_baseline": challenger_f1 > baseline_f1,
        "at_least_three_unique_correct_additions": len(unique_additions) >= 3,
        "at_most_two_additional_false_positives": len(additional_false_positives) <= 2,
        "zero_runtime_failures": runtime_failures == 0,
    }
    passed = all(tolerance_checks.values())
    group_rows = _group_rows(cases, methods, strict, diagnostic)
    disposition_rows = _prediction_dispositions(methods, strict, diagnostic)
    report: dict[str, object] = {
        "schema_version": "t067-fresh-evaluation-readout-v1",
        "status": "pass" if passed else "fail",
        "evidence_class": (
            "single-reviewer prediction-blind fresh check; small sample, not a "
            "population performance estimate"
        ),
        "policy_id": ledger.get("policy_id"),
        "input_identities": {
            "run_manifest_sha256": _sha256_file(run_manifest_path),
            "prediction_dataset_fingerprint": prediction_fingerprint,
            "gold_dataset_fingerprint": fingerprint_records(gold_records),
            "eligibility_ledger_content_sha256": ledger.get("content_sha256"),
            "prediction_artifacts": {
                name: _sha256_file(path) for name, path in prediction_paths.items()
            },
            "job_results": {name: result.result_id for name, result in results.items()},
        },
        "dataset": ledger.get("counts"),
        "methods": summaries,
        "comparison": {
            "baseline": "schwartz_hearst",
            "challenger": "transparent_hybrid_exact_union_sh_plodv2",
            "unique_correct_additions": len(unique_additions),
            "additional_false_positives": len(additional_false_positives),
            "tolerance_checks": tolerance_checks,
            "overall_result": "pass" if passed else "fail",
        },
        "article_group_analysis": {
            "groups": group_rows,
            "uncertainty_statement": (
                "Eight groups are shown as paired descriptive differences; no "
                "population weighting or inferential confidence interval is claimed."
            ),
        },
        "execution": {
            name: {
                "status": result.status,
                "elapsed_seconds": result.elapsed_seconds,
                "resolver": result.resolver,
                "runtime_failures": int(result.status != "complete"),
                "input_tokens": None,
                "estimated_cost_usd": None,
            }
            for name, result in results.items()
        },
        "recommendation": (
            "Adopt the frozen transparent Schwartz-Hearst plus PLODv2 exact union "
            "as the supported existing combination."
            if passed
            else "Retain Schwartz-Hearst as the strongest supported baseline."
        ),
        "artifacts": {
            "prediction_dispositions": _display_path(disposition_path, repository_root)
        },
    }
    report["content_sha256"] = fingerprint(report)
    _freeze_json(report_path, report)
    _write_jsonl(disposition_path, disposition_rows)
    markdown = _markdown(report)
    if (
        report_markdown_path.exists()
        and report_markdown_path.read_text(encoding="utf-8") != markdown
    ):
        raise ValueError(
            "refusing to overwrite a different frozen T067 Markdown report"
        )
    report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report_markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
    return report


def _validated_result(
    path: Path, prediction_path: Path, resolver_key: str, dataset_fingerprint: str
) -> JobResultManifest:
    result = JobResultManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if result.status != "complete":
        raise ValueError(f"required T067 job failed: {resolver_key}")
    if result.dataset_fingerprint != dataset_fingerprint:
        raise ValueError(f"T067 result dataset mismatch: {resolver_key}")
    if result.resolver.get("key") != resolver_key:
        raise ValueError(f"T067 result resolver mismatch: {resolver_key}")
    expected = result.files.get("predictions.jsonl")
    if expected != _sha256_file(prediction_path):
        raise ValueError(f"T067 prediction checksum mismatch: {resolver_key}")
    return result


def _validate_run_inputs(
    run_manifest: Mapping[str, object], ledger_path: Path, dataset_fingerprint: str
) -> None:
    if run_manifest.get("status") != "inputs_frozen_predictions_pending":
        raise ValueError("T067 run manifest is not the frozen pre-run manifest")
    datasets = run_manifest.get("datasets")
    prediction = (
        datasets.get("prediction_input") if isinstance(datasets, dict) else None
    )
    if (
        not isinstance(prediction, dict)
        or prediction.get("fingerprint") != dataset_fingerprint
    ):
        raise ValueError("T067 prediction dataset differs from the pre-run freeze")
    if prediction.get("gold_annotations") != 0:
        raise ValueError("T067 prediction input is not gold-free")
    ledger = run_manifest.get("eligibility_ledger")
    current = _read_object(ledger_path)
    if not isinstance(ledger, dict) or ledger.get("content_sha256") != current.get(
        "content_sha256"
    ):
        raise ValueError("T067 eligibility ledger differs from the pre-run freeze")


def _ledger_cases(ledger: Mapping[str, object]) -> list[dict[str, object]]:
    raw = ledger.get("cases")
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError("T067 eligibility ledger cases are invalid")
    return raw


def _diagnostic_keys(cases: Sequence[Mapping[str, object]]) -> set[PairKey]:
    result: set[PairKey] = set()
    for case in cases:
        raw = case.get("relations")
        if not isinstance(raw, list):
            raise ValueError("T067 eligibility ledger relations are invalid")
        for relation in raw:
            if (
                not isinstance(relation, dict)
                or relation.get("disposition") != "diagnostic"
            ):
                continue
            short = relation.get("short_form")
            long = relation.get("long_form")
            if isinstance(short, dict) and isinstance(long, dict):
                result.add(
                    (
                        str(case["case_id"]),
                        int(short["start"]),
                        int(short["end"]),
                        int(long["start"]),
                        int(long["end"]),
                    )
                )
    return result


def _group_rows(
    cases: Sequence[Mapping[str, object]],
    methods: Mapping[str, Sequence[PairKey]],
    strict: set[PairKey],
    diagnostic: set[PairKey],
) -> list[dict[str, object]]:
    by_group: dict[str, set[str]] = {}
    for case in cases:
        by_group.setdefault(str(case["article_group_id"]), set()).add(
            str(case["case_id"])
        )
    rows: list[dict[str, object]] = []
    for group, ids in sorted(by_group.items()):
        baseline = method_summary(
            methods["schwartz_hearst"], strict, diagnostic, case_ids=ids
        )
        challenger = method_summary(
            methods["transparent_hybrid_exact_union_sh_plodv2"],
            strict,
            diagnostic,
            case_ids=ids,
        )
        rows.append(
            {
                "article_group_id": group,
                "cases": len(ids),
                "strict_relations": sum(item[0] in ids for item in strict),
                "baseline": baseline,
                "challenger": challenger,
                "paired_f1_difference": _float(challenger["f1"])
                - _float(baseline["f1"]),
            }
        )
    return rows


def _prediction_dispositions(
    methods: Mapping[str, Sequence[PairKey]],
    strict: set[PairKey],
    diagnostic: set[PairKey],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for method, predictions in methods.items():
        seen: Counter[PairKey] = Counter()
        for key in predictions:
            seen[key] += 1
            disposition = (
                "true_positive"
                if key in strict and seen[key] == 1
                else "outside_strict_target"
                if key in diagnostic and seen[key] == 1
                else "false_positive_or_duplicate"
            )
            rows.append(
                {
                    "method": method,
                    "case_id": key[0],
                    "short_start": key[1],
                    "short_end": key[2],
                    "long_start": key[3],
                    "long_end": key[4],
                    "disposition": disposition,
                }
            )
    return rows


def _markdown(report: Mapping[str, object]) -> str:
    comparison = report["comparison"]
    assert isinstance(comparison, dict)
    methods = report["methods"]
    assert isinstance(methods, dict)
    lines = [
        "# T067 fresh evaluation readout",
        "",
        f"Result: **{str(comparison['overall_result']).upper()}**.",
        "",
        "| Method | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("schwartz_hearst", "transparent_hybrid_exact_union_sh_plodv2"):
        value = methods[name]
        assert isinstance(value, dict)
        overall = value["overall"]
        assert isinstance(overall, dict)
        lines.append(
            f"| {name} | {overall['true_positives']} | {overall['false_positives']} "
            f"| {overall['false_negatives']} | {float(overall['precision']):.3f} "
            f"| {float(overall['recall']):.3f} | {float(overall['f1']):.3f} |"
        )
    lines.extend(
        [
            "",
            f"Recommendation: {report['recommendation']}",
            "",
            "Prose and table/list results, execution provenance, tolerance checks, "
            "and paired article-group differences are preserved in the JSON report.",
        ]
    )
    return "\n".join(lines) + "\n"


def _freeze_json(path: Path, value: object) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError("refusing to overwrite a different frozen T067 primary report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError("refusing to overwrite different T067 prediction dispositions")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        return str(path.resolve())


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("numeric metric required")
    return float(value)


__all__ = ["materialize_fresh_readout", "method_summary"]
