"""Build reproducible CLP Milestone A replay and error-analysis artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.evaluation.clp_transfer import (
    analyze_exact_offsets,
    compact_replay,
    read_json,
    read_jsonl,
    sha256_file,
    write_jsonl,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Build compact replays, the machine report, and a concise Markdown readout."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clp-root", type=Path, required=True)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("resources/clp/abbr-v5-validation-v1.jsonl"),
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        default=Path("resources/clp/abbr-v5-validation-v1.manifest.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-a"),
    )
    parser.add_argument(
        "--development-readout",
        type=Path,
        default=Path("docs/artifacts/T062-development-readout.json"),
    )
    parser.add_argument(
        "--development-recovery",
        type=Path,
        default=Path("evidence/T062/recovery-table-v1.jsonl"),
    )
    args = parser.parse_args(argv)

    clp_root = args.clp_root.resolve()
    output_dir = args.output_dir.resolve()
    snapshot_rows = read_jsonl(args.snapshot)
    snapshot_manifest = read_json(args.snapshot_manifest)
    variants = {
        "rules_only": {
            "report": clp_root / "work/abbr-v5-validation-v51-final3",
            "native": output_dir / "clp-rules-only-native-evaluation-v1/summary.json",
        },
        "full": {
            "report": clp_root / "work/abbr-v5-validation-v51-live3-t052",
            "native": output_dir / "clp-full-native-evaluation-v1/summary.json",
        },
    }
    variant_reports: dict[str, Any] = {}
    artifact_hashes: dict[str, str] = {}
    for name, paths in variants.items():
        report_dir = cast(Path, paths["report"])
        sequence_path = report_dir / "sequences.jsonl"
        report_manifest_path = report_dir / "manifest.json"
        source_identity = {
            "sequence_sha256": sha256_file(sequence_path),
            "manifest_sha256": sha256_file(report_manifest_path),
        }
        replay = compact_replay(
            snapshot_rows,
            read_jsonl(sequence_path),
            variant=name,
            source_identity=source_identity,
        )
        replay_path = output_dir / f"clp-{name.replace('_', '-')}-replay-v1.jsonl"
        artifact_hashes[str(replay_path.relative_to(Path.cwd()))] = write_jsonl(
            replay_path, replay
        )
        native_path = cast(Path, paths["native"])
        native_summary = read_json(native_path)
        variant_reports[name] = {
            "execution_mode": (
                "saved cache-only replay; unresolved cache misses retained"
                if name == "rules_only"
                else "saved cache-only replay of previously live Jev decisions"
            ),
            "source_identity": source_identity,
            "native_metrics": _native_metrics(native_summary),
            "abrex_exact_offsets": analyze_exact_offsets(snapshot_rows, replay),
        }

    full_manifest = read_json(
        clp_root / "work/abbr-v5-validation-v51-live3-t052/manifest.json"
    )
    development = read_json(args.development_readout)
    recovery = read_jsonl(args.development_recovery)
    report: dict[str, Any] = {
        "schema_version": "clp-milestone-a-report-v1",
        "status": "complete",
        "evidence_class": (
            "assisted/risk-stratified development evidence; not independent validation"
        ),
        "source_pin": _source_pin(clp_root, snapshot_manifest, full_manifest),
        "section_reconciliation": {
            "sections": 200,
            "positive": 143,
            "negative": 50,
            "parser_extension_excluded": 7,
            "legacy_exported_negative_total": 57,
            "explanation": (
                "The legacy exported total combined 50 true negative sections with "
                "7 needs-parser-extension sections; strict section acceptance excludes "
                "the latter while routing reports them separately."
            ),
            "source_pairs": 4035,
            "exact_offset_mapped_pairs": 3696,
            "unmapped_pairs": 339,
            "semantic_orientation_repairs": 19,
            "mapping_loss_rate": 339 / 4035,
            "mapping_loss_causes": _mapping_loss_causes(snapshot_rows),
        },
        "variants": variant_reports,
        "existing_method_comparison": _development_comparison(development),
        "existing_method_error_outcomes": _development_error_outcomes(recovery),
        "plod_gold_assisted_diagnostic_ceiling": _plod_ceiling(recovery),
        "artifacts": artifact_hashes,
        "limitations": [
            "CLP-native normalized/string metrics and Abrex exact-offset metrics use different denominators and are never pooled.",
            "The full replay makes no new Jev requests and spends no new model budget.",
            "The 339 unmapped source pairs remain explicit exclusions; corresponding predictions are not automatically false positives.",
            "PLOD endpoint and pairing ceilings use gold to select evidence and are not deployable scores.",
            "Article identities are retained for concentration analysis; the 200 sections are risk-stratified development evidence.",
        ],
    }
    report_path = output_dir / "clp-milestone-a-report-v1.json"
    supporting = {
        Path("resources/clp/clp-v5.1-source.zip"),
        output_dir / "clp-worker-v2-smoke-response.json",
    }
    for path in supporting:
        if path.is_file():
            relative = path.resolve().relative_to(Path.cwd().resolve())
            artifact_hashes[str(relative)] = sha256_file(path)
    report_text = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    report_path.write_text(report_text, encoding="utf-8", newline="\n")
    artifact_hashes[str(report_path.relative_to(Path.cwd()))] = sha256_file(report_path)
    readout_path = Path("docs/artifacts/clp-milestone-a-readout.md")
    readout_path.write_text(_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"report": str(report_path), "status": "complete"}, indent=2))
    return 0


def _native_metrics(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "baseline_id": summary.get("baseline_id"),
        "gold": summary.get("gold"),
        "section_acceptance": summary.get("section_acceptance"),
        "section_routing": summary.get("section_routing"),
        "normalized_occurrence_pairs": summary.get("normalized_occurrence_pairs"),
        "source_string_occurrence_pairs": summary.get("source_string_occurrence_pairs"),
        "endpoint": summary.get("endpoint"),
        "orientation_on_matched_pairs": summary.get("orientation_on_matched_pairs"),
        "by_gold_pattern": summary.get("by_gold_pattern"),
    }


def _source_pin(
    clp_root: Path,
    snapshot_manifest: Mapping[str, Any],
    full_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    source = _mapping(snapshot_manifest.get("source"), "snapshot source")
    run = _mapping(full_manifest.get("run"), "CLP run")
    commit = subprocess.run(
        ["git", "-C", str(clp_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "repository": "CellLiteraturePipeline",
        "annotation_source_commit": source.get("commit"),
        "inspected_checkout_commit": commit,
        "policy_version": run.get("policy_version"),
        "confidence_threshold": run.get("confidence_threshold"),
        "python": run.get("python"),
        "candidate_generator_source": run.get("candidate_generator_source"),
        "hybrid_source": run.get("hybrid_source"),
        "dictionary": run.get("dictionary"),
        "jev_cache": run.get("jev_cache_at_completion"),
        "transfer_boundary": (
            "versioned compact JSON replay retaining source passage indexes, "
            "orientation, rule, acceptance, and source identities"
        ),
        "source_archive": {
            "path": "resources/clp/clp-v5.1-source.zip",
            "sha256": "290a52ad53216de64fca78abff2682057cc77b0d3c3ee698580a8ca9f94df7d7",
        },
        "verified_direct_runtime": {
            "python": "3.13.1",
            "bioc": "2.1",
            "PyYAML": "6.0.3",
            "typesafe-sdk": "0.7.2",
            "numpy": "2.5.3",
            "scipy": "1.18.1",
            "torch": "2.14.0",
            "transformers": "4.57.6",
            "flair": "0.15.1",
            "optuna": "4.9.0",
            "filelock": "4.0.6",
        },
    }


def _development_comparison(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset": report.get("dataset"),
        "methods": report.get("methods"),
        "transparent_union": report.get("simple_union_schwartz_hearst_plodv2"),
        "gold_assisted_all_method_oracle": report.get(
            "gold_assisted_all_method_oracle"
        ),
        "evidence_class": report.get("evidence_class"),
    }


def _development_error_outcomes(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strict = [row for row in rows if row.get("disposition") == "strict"]
    result: dict[str, Any] = {"strict_relations": len(strict), "methods": {}}
    for method in (
        "ab3p",
        "jev_candidate_judge",
        "plodv2_pairing",
        "schwartz_hearst",
    ):
        counts: Counter[str] = Counter()
        for row in strict:
            methods = _mapping(row.get("method_outcomes"), "method outcomes")
            outcome = _mapping(methods.get(method), method)
            counts[str(outcome.get("outcome"))] += 1
        result["methods"][method] = dict(sorted(counts.items()))
    return result


def _mapping_loss_causes(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    causes: Counter[str] = Counter()
    for row in rows:
        raw_annotations = row.get("annotations", [])
        if not isinstance(raw_annotations, list):
            raise TypeError("snapshot annotations must be an array")
        raw_passages = row.get("passages", [])
        if not isinstance(raw_passages, list):
            raise TypeError("snapshot passages must be an array")
        passages = {
            int(_mapping(value, "passage")["index"]): _mapping(value, "passage")
            for value in raw_passages
        }
        for raw_annotation in raw_annotations:
            annotation = _mapping(raw_annotation, "annotation")
            if annotation.get("mapping_status") == "mapped":
                continue
            raw_indexes = annotation.get("source_passage_indexes", [])
            if not isinstance(raw_indexes, list):
                raise TypeError("source passage indexes must be an array")
            indexes = [int(value) for value in raw_indexes]
            role = "short_form" if annotation.get("short_span") is None else "long_form"
            value = str(annotation[role])
            occurrences = sum(
                _overlapping_occurrences(str(passages[index].get("text", "")), value)
                for index in indexes
                if index in passages
            )
            causes[f"{role}_{'repeated' if occurrences > 1 else 'absent'}"] += 1
    return dict(sorted(causes.items()))


def _overlapping_occurrences(text: str, value: str) -> int:
    count = 0
    cursor = 0
    while value:
        found = text.find(value, cursor)
        if found < 0:
            break
        count += 1
        cursor = found + 1
    return count


def _plod_ceiling(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strict = [row for row in rows if row.get("disposition") == "strict"]
    endpoints = Counter()
    examples: list[dict[str, Any]] = []
    for row in strict:
        methods = _mapping(row.get("method_outcomes"), "method outcomes")
        plod = _mapping(methods.get("plodv2_pairing"), "PLOD outcome")
        detected = int(plod.get("detected_endpoint_count", 0))
        endpoints[detected] += 1
        if detected == 1 and len(examples) < 5:
            examples.append(
                {
                    "case_id": row.get("case_id"),
                    "article_group_id": row.get("article_group_id"),
                    "short_form": row.get("short_form"),
                    "long_form": row.get("long_form"),
                }
            )
    both = endpoints[2]
    at_least_one = endpoints[1] + endpoints[2]
    exact_endpoints = 2 * both + endpoints[1]
    denominator = 2 * len(strict)
    return {
        "strict_relations": len(strict),
        "relations_with_both_exact_endpoints": both,
        "pairing_recall_ceiling_if_only_retained_exact_endpoints_are_usable": (
            both / len(strict) if strict else 0.0
        ),
        "exact_endpoint_recall_ceiling": (
            exact_endpoints / denominator if denominator else 0.0
        ),
        "pair_recall_ceiling_if_gold_supplies_one_missing_endpoint": (
            at_least_one / len(strict) if strict else 0.0
        ),
        "endpoint_count_distribution": dict(sorted(endpoints.items())),
        "one-endpoint_examples": examples,
        "interpretation": (
            "Gold-assisted diagnostic ceiling over retained PLOD spans; not a deployable score."
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    variants = _mapping(report["variants"], "variants")
    rules = _mapping(variants["rules_only"], "rules")
    full = _mapping(variants["full"], "full")
    rules_native = _mapping(rules["native_metrics"], "rules native")
    full_native = _mapping(full["native_metrics"], "full native")
    rules_exact = _mapping(rules["abrex_exact_offsets"], "rules exact")
    full_exact = _mapping(full["abrex_exact_offsets"], "full exact")
    rn = _mapping(rules_native["normalized_occurrence_pairs"], "rules pairs")
    fn = _mapping(full_native["normalized_occurrence_pairs"], "full pairs")
    re = _mapping(rules_exact["metrics"], "rules exact metrics")
    fe = _mapping(full_exact["metrics"], "full exact metrics")
    full_errors = _mapping(full_exact["error_categories"], "full errors")
    return f"""# CLP Milestone A readout

This is risk-stratified development evidence, not independent validation.

## Reconciled source universe

- 200 sections: 143 positive, 50 negative, and 7 parser-extension sections excluded from strict acceptance scoring.
- 4,035 source pairs: 3,696 uniquely mapped to Abrex half-open offsets and 339 explicit mapping exclusions (8.40%).
- The derivative now records 19 semantic-orientation repairs from one legacy reversed section; source strings and provenance remain preserved.

## CLP-native view

| Variant | Mode | Matched / gold | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| Rules-only | cache-only, misses unresolved | {rn["matched"]} / {rn["gold"]} | {rn["precision"]:.4f} | {rn["recall"]:.4f} | {rn["f1"]:.4f} |
| Full V5.1 | saved Jev-decision replay | {fn["matched"]} / {fn["gold"]} | {fn["precision"]:.4f} | {fn["recall"]:.4f} | {fn["f1"]:.4f} |

## Abrex exact-offset view

| Variant | Precision | Recall | F1 |
|---|---:|---:|---:|
| Rules-only | {re["precision"]:.4f} | {re["recall"]:.4f} | {re["f1"]:.4f} |
| Full V5.1 | {fe["precision"]:.4f} | {fe["recall"]:.4f} | {fe["f1"]:.4f} |

These denominators differ from CLP-native normalized occurrence metrics and are not pooled. Predictions corresponding to the 339 unmapped reference pairs are excluded rather than labeled false positives.

## Full-replay error accounting

{json.dumps(full_errors, ensure_ascii=False, sort_keys=True)}

The machine report retains occurrence examples, article identities, pattern strata, source hashes, existing S&H/Ab3P/PLOD/Jev development comparators, and the explicitly gold-assisted PLOD endpoint/pairing ceilings.
"""


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


if __name__ == "__main__":
    raise SystemExit(main())
