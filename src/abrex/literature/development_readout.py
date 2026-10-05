"""T062 development recovery analysis over frozen assisted evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.literature.development_views import relation_eligibility
from abrex.literature.review_interchange import read_annotation_state
from abrex.literature.review_models import PairDecision, ReviewPacket, fingerprint
from abrex.literature.review_packet import read_review_packet
from abrex.resolvers import PredictionArtifact, read_prediction_artifact

PairKey = tuple[str, int, int, int, int]
EndpointKey = tuple[str, Literal["short_form", "long_form"], int, int]


def pair_key(
    document_id: str,
    short_form: Mapping[str, object],
    long_form: Mapping[str, object],
) -> PairKey:
    """Return one occurrence-specific exact-pair key."""

    return (
        document_id,
        _required_int(short_form, "start"),
        _required_int(short_form, "end"),
        _required_int(long_form, "start"),
        _required_int(long_form, "end"),
    )


def decision_key(case_id: str, decision: PairDecision) -> PairKey | None:
    """Return an exact key when a review decision has both endpoints."""

    if decision.short_form is None or decision.long_form is None:
        return None
    return (
        case_id,
        decision.short_form.start,
        decision.short_form.end,
        decision.long_form.start,
        decision.long_form.end,
    )


def prediction_keys(artifact: PredictionArtifact) -> list[PairKey]:
    """Retain every complete predicted occurrence, including duplicates."""

    result: list[PairKey] = []
    for record in artifact.records:
        for prediction in record.predictions:
            if prediction.short_form is None or prediction.long_form is None:
                continue
            result.append(
                (
                    record.document_id,
                    prediction.short_form.start,
                    prediction.short_form.end,
                    prediction.long_form.start,
                    prediction.long_form.end,
                )
            )
    return result


def pair_metrics(
    predictions: Sequence[PairKey],
    strict: set[PairKey],
    diagnostic: set[PairKey],
) -> dict[str, int | float]:
    """Score occurrences one-to-one while reporting outside-target matches."""

    counts = Counter(predictions)
    true_positives = sum(min(counts[key], 1) for key in strict)
    outside_target = sum(min(counts[key], 1) for key in diagnostic)
    false_positives = len(predictions) - true_positives - outside_target
    false_negatives = len(strict) - true_positives
    precision_denominator = true_positives + false_positives
    precision = true_positives / precision_denominator if precision_denominator else 0.0
    recall = true_positives / len(strict) if strict else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "predictions": len(predictions),
        "unique_prediction_occurrences": len(counts),
        "duplicate_predictions": len(predictions) - len(counts),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "outside_strict_target": outside_target,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def recovery_outcome(
    relation: PairKey,
    predictions: Sequence[PairKey],
    detector_endpoints: set[EndpointKey] | None = None,
) -> dict[str, object]:
    """Classify observable recovery without guessing a failure mechanism."""

    if relation in predictions:
        return {"outcome": "correct_exact_pair", "detected_endpoint_count": 2}
    document_id, short_start, short_end, long_start, long_end = relation
    detected_count = 0
    if detector_endpoints is not None:
        detected_count = sum(
            endpoint in detector_endpoints
            for endpoint in (
                (document_id, "short_form", short_start, short_end),
                (document_id, "long_form", long_start, long_end),
            )
        )
        if detected_count == 2:
            return {
                "outcome": "detected_spans_without_correct_pairing",
                "detected_endpoint_count": detected_count,
            }
    for candidate in predictions:
        if candidate[0] != document_id:
            continue
        if _overlap(candidate[1], candidate[2], short_start, short_end) and _overlap(
            candidate[3], candidate[4], long_start, long_end
        ):
            return {
                "outcome": "wrong_boundary",
                "detected_endpoint_count": detected_count,
            }
    return {
        "outcome": "absent_candidate",
        "detected_endpoint_count": detected_count,
    }


def materialize_development_readout(
    *,
    diagnostic_view_path: Path,
    review_sources: Sequence[tuple[Path, Path]],
    triage_path: Path,
    corpus_path: Path,
    corpus_manifest_path: Path,
    prediction_paths: Mapping[str, Path],
    plod_span_path: Path,
    t060_comparison_path: Path,
    jev_report_path: Path,
    schwartz_hearst_config_path: Path,
    plod_pairing_config_path: Path,
    ledger_path: Path,
    recovery_path: Path,
    prediction_dispositions_path: Path,
    report_json_path: Path,
    report_markdown_path: Path,
    decision_prefill_path: Path,
) -> dict[str, object]:
    """Build the immutable T062 ledger, tables, readout, and T063 prefill."""

    diagnostic = _read_object(diagnostic_view_path)
    triage = _read_object(triage_path)
    t060 = _read_object(t060_comparison_path)
    jev_report = _read_object(jev_report_path)
    records, _ = read_canonical_dataset(corpus_path, corpus_manifest_path)
    documents = {record.document.document_id: record.document for record in records}
    dataset_fingerprint = fingerprint_records(records)
    repository_root = report_json_path.resolve().parents[2]

    relations, strict, diagnostic_keys = _base_relations(diagnostic)
    review_packets: list[ReviewPacket] = []
    review_states = []
    for packet_path, state_path in review_sources:
        packet = read_review_packet(packet_path)
        state = read_annotation_state(packet, state_path)
        review_packets.append(packet)
        review_states.append(state)
        _merge_new_relations(relations, strict, diagnostic_keys, packet, state)

    artifacts = {
        name: read_prediction_artifact(
            path,
            documents=documents,
            expected_dataset_fingerprint=dataset_fingerprint,
        )
        for name, path in sorted(prediction_paths.items())
    }
    method_predictions = {
        name: prediction_keys(artifact) for name, artifact in artifacts.items()
    }
    span_artifact = read_prediction_artifact(
        plod_span_path,
        documents=documents,
        expected_dataset_fingerprint=dataset_fingerprint,
    )
    plod_endpoints = _artifact_endpoints(span_artifact)

    recovery_rows = _recovery_rows(
        relations,
        method_predictions,
        plod_endpoints,
    )
    disposition_rows = _prediction_dispositions(
        method_predictions,
        strict,
        diagnostic_keys,
        review_packets,
        review_states,
        triage,
    )
    method_summaries = {
        name: pair_metrics(predictions, strict, diagnostic_keys)
        for name, predictions in method_predictions.items()
    }
    baseline_name = "schwartz_hearst"
    baseline_predictions = method_predictions[baseline_name]
    comparisons = {
        name: _compare_to_baseline(
            name,
            predictions,
            baseline_name,
            baseline_predictions,
            strict,
            diagnostic_keys,
            relations,
        )
        for name, predictions in method_predictions.items()
        if name != baseline_name
    }
    simple_union = _union_summary(
        baseline_name,
        baseline_predictions,
        "plodv2_pairing",
        method_predictions["plodv2_pairing"],
        strict,
        diagnostic_keys,
    )
    all_union = [
        key for predictions in method_predictions.values() for key in predictions
    ]
    all_union_unique = list(dict.fromkeys(all_union))

    new_t061_strict = sum(
        row["source"] == "t061" and row["disposition"] == "strict"
        for row in relations.values()
    )
    new_t061_diagnostic = sum(
        row["source"] == "t061" and row["disposition"] == "diagnostic"
        for row in relations.values()
    )
    ledger: dict[str, object] = {
        "schema_version": "t062-development-ledger-v1",
        "policy_id": "t057-strict-exact-pair-v1+t061-assisted-supplement-v1",
        "status": "development_evidence",
        "source_hashes": _source_hashes(
            [
                diagnostic_view_path,
                triage_path,
                corpus_path,
                corpus_manifest_path,
                t060_comparison_path,
                jev_report_path,
                schwartz_hearst_config_path,
                plod_pairing_config_path,
                plod_span_path,
                *prediction_paths.values(),
                *(path for pair in review_sources for path in pair),
            ],
            repository_root,
        ),
        "counts": {
            "strict_relations": len(strict),
            "diagnostic_relations": len(diagnostic_keys),
            "new_t061_strict_relations": new_t061_strict,
            "new_t061_diagnostic_relations": new_t061_diagnostic,
            "unresolved_relations": sum(
                row["disposition"] == "unresolved" for row in relations.values()
            ),
        },
        "relations": [relations[key] for key in sorted(relations)],
    }
    review_cost = _review_cost(review_packets, review_states, triage)
    execution_cost = _execution_cost(t060, jev_report)
    challenger_parameters = {
        "strategy": "exact_union",
        "conflict_policy": "retain_all",
        "child_failure_policy": "raise",
        "children": ["schwartz_hearst", "plodv2_pairing"],
        "frozen_components": [
            {
                "key": "schwartz_hearst",
                "config_path": _display_path(
                    schwartz_hearst_config_path, repository_root
                ),
                "config_sha256": _file_sha256(schwartz_hearst_config_path),
            },
            {
                "key": "plodv2_pairing",
                "config_path": _display_path(plod_pairing_config_path, repository_root),
                "config_sha256": _file_sha256(plod_pairing_config_path),
            },
        ],
    }
    report: dict[str, object] = {
        "schema_version": "t062-development-readout-v1",
        "status": "complete",
        "evidence_class": (
            "assisted development evidence; not blind, representative, or a "
            "population performance estimate"
        ),
        "dataset": {
            "documents": len(records),
            "article_groups": len(
                {
                    str(case["article_group_id"])
                    for case in _object_list(diagnostic, "cases")
                }
            ),
            "strict_relations": len(strict),
            "diagnostic_relations": len(diagnostic_keys),
            "new_t061_strict_relations": new_t061_strict,
        },
        "methods": method_summaries,
        "comparisons_to_schwartz_hearst": comparisons,
        "simple_union_schwartz_hearst_plodv2": simple_union,
        "gold_assisted_all_method_oracle": {
            "correct_available_pairs": len(set(all_union_unique) & strict),
            "strict_relations": len(strict),
            "recall_ceiling": len(set(all_union_unique) & strict) / len(strict),
            "interpretation": (
                "Upper bound that selects only known-correct predictions from all "
                "available methods; it is not deployable."
            ),
        },
        "raw_relation_counts": _raw_relation_counts(relations),
        "review_cost": review_cost,
        "processing_cost": execution_cost,
        "recommendation": {
            "fixed_baseline": "schwartz_hearst",
            "single_challenger": "transparent_hybrid_exact_union_sh_plodv2",
            "registry_key": "transparent_hybrid",
            "parameters": challenger_parameters,
            "configuration_sha256": fingerprint(challenger_parameters),
            "rationale": (
                "On the assisted development view, PLODv2 pairing adds nine "
                "strict pairs absent from Schwartz-Hearst with one additional "
                "false positive; their exact union improves F1 from 0.661 to "
                "0.756. Freeze and test this transparent existing composition, "
                "without further tuning, against Schwartz-Hearst."
            ),
            "jev_disposition": (
                "Do not advance Jev to the fresh check: it adds six strict pairs "
                "but eleven additional false positives versus Schwartz-Hearst."
            ),
        },
        "protocol_proposal": _protocol_proposal(),
        "artifacts": {
            "ledger": _display_path(ledger_path, repository_root),
            "recovery_table": _display_path(recovery_path, repository_root),
            "prediction_dispositions": _display_path(
                prediction_dispositions_path, repository_root
            ),
        },
    }
    report["content_sha256"] = fingerprint(report)

    _write_json(ledger_path, ledger)
    _write_jsonl(recovery_path, recovery_rows)
    _write_jsonl(prediction_dispositions_path, disposition_rows)
    _write_json(report_json_path, report)
    report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report_markdown_path.write_text(
        _markdown_report(report), encoding="utf-8", newline="\n"
    )
    _write_json(
        decision_prefill_path,
        _decision_prefill(
            report,
            ledger_path,
            recovery_path,
            report_json_path,
            repository_root,
        ),
    )
    return report


def _base_relations(
    diagnostic: Mapping[str, object],
) -> tuple[dict[PairKey, dict[str, object]], set[PairKey], set[PairKey]]:
    relations: dict[PairKey, dict[str, object]] = {}
    strict: set[PairKey] = set()
    diagnostic_keys: set[PairKey] = set()
    for case in _object_list(diagnostic, "cases"):
        case_id = str(case["case_id"])
        for relation in _object_list(case, "relations"):
            short = relation.get("short_form")
            long = relation.get("long_form")
            if (
                relation.get("status") != "correct"
                or not isinstance(short, dict)
                or not isinstance(long, dict)
            ):
                continue
            key = pair_key(case_id, short, long)
            row = {
                **relation,
                "source": "t057",
                "article_id": case.get("article_id"),
                "article_group_id": case.get("article_group_id"),
                "arm": case.get("arm"),
            }
            relations[key] = row
            (
                strict if relation.get("disposition") == "strict" else diagnostic_keys
            ).add(key)
    return relations, strict, diagnostic_keys


def _merge_new_relations(
    relations: dict[PairKey, dict[str, object]],
    strict: set[PairKey],
    diagnostic: set[PairKey],
    packet: ReviewPacket,
    state: Any,
) -> None:
    cases = {case.case_id: case for case in packet.cases}
    for case_id, annotation in state.annotations.items():
        case = cases[case_id]
        for decision in annotation.current.pairs:
            key = decision_key(case_id, decision)
            if decision.status != "correct" or key is None or key in relations:
                continue
            eligibility = relation_eligibility(decision)
            row = {
                "case_id": case_id,
                "decision_id": decision.decision_id,
                "suggestion_id": decision.suggestion_id,
                "status": decision.status,
                "origin": decision.origin,
                "short_form": decision.short_form.model_dump(mode="json")
                if decision.short_form
                else None,
                "long_form": decision.long_form.model_dump(mode="json")
                if decision.long_form
                else None,
                "relation_kind": decision.relation_kind,
                "evidence_structure": decision.evidence_structure,
                "context_requirement": decision.context_requirement,
                "evidence_spans": [
                    span.model_dump(mode="json") for span in decision.evidence_spans
                ],
                "source_error": decision.source_error,
                "notes": decision.notes,
                "disposition": eligibility.disposition,
                "eligibility_reason": eligibility.reason,
                "source": "t061",
                "source_packet_id": packet.packet_id,
                "source_revision": annotation.revision,
                "article_id": case.article_id,
                "article_group_id": case.article_group_id,
                "arm": case.arm,
            }
            relations[key] = row
            if eligibility.disposition == "strict":
                strict.add(key)
            else:
                diagnostic.add(key)


def _recovery_rows(
    relations: Mapping[PairKey, Mapping[str, object]],
    method_predictions: Mapping[str, Sequence[PairKey]],
    plod_endpoints: set[EndpointKey],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key, relation in sorted(relations.items()):
        disposition = str(relation["disposition"])
        target_category = (
            "strict_exact_pair"
            if disposition == "strict"
            else "representation_limited_evidence"
            if relation.get("eligibility_reason") == "not_representable_as_exact_pair"
            else "out_of_scope_or_unsupported"
        )
        outcomes = {
            name: recovery_outcome(
                key,
                predictions,
                plod_endpoints if name == "plodv2_pairing" else None,
            )
            for name, predictions in method_predictions.items()
        }
        rows.append(
            {
                "case_id": key[0],
                "short_form": relation["short_form"],
                "long_form": relation["long_form"],
                "disposition": disposition,
                "target_category": target_category,
                "relation_kind": relation.get("relation_kind"),
                "evidence_structure": relation.get("evidence_structure"),
                "article_group_id": relation.get("article_group_id"),
                "source": relation.get("source"),
                "method_outcomes": outcomes,
            }
        )
    return rows


def _prediction_dispositions(
    method_predictions: Mapping[str, Sequence[PairKey]],
    strict: set[PairKey],
    diagnostic: set[PairKey],
    packets: Sequence[ReviewPacket],
    states: Sequence[Any],
    triage: Mapping[str, object],
) -> list[dict[str, object]]:
    suggestion_reasons: dict[PairKey, dict[str, object]] = {}
    decisions: dict[str, PairDecision] = {}
    for state in states:
        for annotation in state.annotations.values():
            for decision in annotation.current.pairs:
                if decision.suggestion_id:
                    decisions[decision.suggestion_id] = decision
    triage_items = {
        str(item["suggestion_id"]): item for item in _object_list(triage, "items")
    }
    for packet in packets:
        for case in packet.cases:
            for suggestion in case.suggestions:
                if suggestion.short_form is None or suggestion.long_form is None:
                    continue
                key = (
                    case.case_id,
                    suggestion.short_form.start,
                    suggestion.short_form.end,
                    suggestion.long_form.start,
                    suggestion.long_form.end,
                )
                decision = decisions.get(suggestion.suggestion_id)
                triage_item = triage_items.get(suggestion.suggestion_id, {})
                suggestion_reasons[key] = {
                    "suggestion_id": suggestion.suggestion_id,
                    "review_status": decision.status if decision else None,
                    "review_origin": decision.origin if decision else None,
                    "triage_disposition": triage_item.get("disposition"),
                    "triage_reason_code": triage_item.get("reason_code"),
                }
    rows: list[dict[str, object]] = []
    for method, predictions in sorted(method_predictions.items()):
        seen: Counter[PairKey] = Counter()
        for key in predictions:
            seen[key] += 1
            disposition = (
                "correct_exact_pair"
                if key in strict and seen[key] == 1
                else "out_of_scope_or_unsupported"
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
                    "review_evidence": suggestion_reasons.get(key),
                }
            )
    return rows


def _compare_to_baseline(
    method: str,
    predictions: Sequence[PairKey],
    baseline_name: str,
    baseline: Sequence[PairKey],
    strict: set[PairKey],
    diagnostic: set[PairKey],
    relations: Mapping[PairKey, Mapping[str, object]],
) -> dict[str, object]:
    method_set = set(predictions)
    baseline_set = set(baseline)
    additions = sorted((method_set & strict) - (baseline_set & strict))
    method_errors = method_set - strict - diagnostic
    baseline_errors = baseline_set - strict - diagnostic
    return {
        "method": method,
        "baseline": baseline_name,
        "unique_correct_additions": len(additions),
        "additional_false_positives": len(method_errors - baseline_errors),
        "unique_correct_pairs": [
            {
                "case_id": key[0],
                "short_form": relations[key]["short_form"],
                "long_form": relations[key]["long_form"],
            }
            for key in additions
        ],
    }


def _union_summary(
    left_name: str,
    left: Sequence[PairKey],
    right_name: str,
    right: Sequence[PairKey],
    strict: set[PairKey],
    diagnostic: set[PairKey],
) -> dict[str, object]:
    union = list(dict.fromkeys([*left, *right]))
    return {
        "configuration": "transparent_hybrid_exact_union_sh_plodv2",
        "children": [left_name, right_name],
        "metrics": pair_metrics(union, strict, diagnostic),
        "interpretation": (
            "Existing transparent exact-union baseline; development evidence "
            "does not establish denoising or fresh-sample superiority."
        ),
    }


def _raw_relation_counts(
    relations: Mapping[PairKey, Mapping[str, object]],
) -> dict[str, object]:
    return {
        "by_article_group": dict(
            sorted(
                Counter(
                    str(row["article_group_id"]) for row in relations.values()
                ).items()
            )
        ),
        "by_relation_kind": dict(
            sorted(
                Counter(
                    str(row.get("relation_kind")) for row in relations.values()
                ).items()
            )
        ),
        "by_evidence_structure": dict(
            sorted(
                Counter(
                    str(row.get("evidence_structure")) for row in relations.values()
                ).items()
            )
        ),
        "by_disposition": dict(
            sorted(
                Counter(str(row["disposition"]) for row in relations.values()).items()
            )
        ),
    }


def _review_cost(
    packets: Sequence[ReviewPacket], states: Sequence[Any], triage: Mapping[str, object]
) -> dict[str, object]:
    annotations = [
        annotation for state in states for annotation in state.annotations.values()
    ]
    decisions = [
        decision for annotation in annotations for decision in annotation.current.pairs
    ]
    triage_counts = triage.get("counts")
    if not isinstance(triage_counts, dict):
        raise ValueError("T061 triage counts must be an object")
    return {
        "human_reviewed_passages": len(annotations),
        "human_saved_current_decisions": len(decisions),
        "source_suggestions_in_reviewed_passages": sum(
            len(packet.cases[index].suggestions)
            for packet, state in zip(packets, states, strict=True)
            for index, case in enumerate(packet.cases)
            if case.case_id in state.annotations
        ),
        "machine_resolved_without_repeat_review": triage_counts.get(
            "resolved_by_frozen_evidence_or_policy"
        ),
        "interpretation": (
            "Assisted development review burden; elapsed human time was not "
            "measured and is not estimated retrospectively."
        ),
    }


def _execution_cost(
    t060: Mapping[str, object], jev_report: Mapping[str, object]
) -> dict[str, object]:
    methods = t060.get("methods")
    if not isinstance(methods, dict):
        raise ValueError("T060 methods must be an object")
    result: dict[str, object] = {}
    for name, raw in methods.items():
        if not isinstance(raw, dict):
            continue
        execution = raw.get("execution")
        result[str(name)] = {
            "predictions": raw.get("predictions"),
            "failures": raw.get("failures"),
            "elapsed_seconds": execution.get("elapsed_seconds")
            if isinstance(execution, dict)
            else None,
        }
    usage = jev_report.get("usage")
    if isinstance(usage, dict):
        existing = result.get("jev_candidate_judge")
        if not isinstance(existing, dict):
            existing = {}
        result["jev_candidate_judge"] = {
            **existing,
            "requests": usage.get("requests"),
            "summed_request_latency_seconds": usage.get(
                "summed_request_latency_seconds"
            ),
            "input_tokens": usage.get("input_tokens"),
            "estimated_input_cost_usd": usage.get("estimated_input_cost_usd"),
        }
    return result


def _protocol_proposal() -> dict[str, object]:
    return {
        "purpose": "small prediction-blind fresh check, not a powered benchmark",
        "items": 32,
        "prose_passages": 24,
        "prose_arm_mix": {"pubmed_abstract": 12, "pmc_text": 12},
        "table_or_list_sections": 8,
        "article_groups": 8,
        "maximum_items_per_group": 4,
        "seed": 20261002,
        "sampling": (
            "sample without detector/token enrichment; freeze sources and passage "
            "segmentation before predictions"
        ),
        "exclusions": [
            "all ABREX development and previously reviewed documents",
            "all CellLiteraturePipeline annotated documents and linked copies",
            "all linked versions of excluded article groups",
        ],
        "primary_policy": (
            "strict half-open exact SF/LF occurrence pairs; diagnostic, uncertain, "
            "and representation-limited evidence reported separately"
        ),
        "success_tolerances": {
            "strict_pair_f1": "challenger must exceed Schwartz-Hearst",
            "unique_correct_additions": 3,
            "maximum_additional_false_positives": 2,
            "runtime_failures": 0,
            "reporting": "prose and table/list arms separate; no pooled-only adoption",
        },
        "acquisition_limits": {
            "maximum_elapsed_hours": 2,
            "maximum_download_bytes": 134217728,
            "replacement_rule": (
                "replace only documented source-ineligible or failed-fetch groups "
                "using seeded order, never apparent abbreviation content"
            ),
        },
        "reviewer_plan": "single-reviewer, prediction-blind",
    }


def _decision_prefill(
    report: Mapping[str, object],
    ledger_path: Path,
    recovery_path: Path,
    report_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    recommendation = report["recommendation"]
    protocol = report["protocol_proposal"]
    return {
        "schema_version": "t063-protocol-decision-v2",
        "status": "awaiting_scientific_lead",
        "evidence_dependencies": {
            "t060_complete": True,
            "t061_complete": True,
            "t062_complete": True,
            "t062_report": _display_path(report_path, repository_root),
            "t062_report_sha256": _file_sha256(report_path),
            "t062_ledger": _display_path(ledger_path, repository_root),
            "t062_ledger_sha256": _file_sha256(ledger_path),
            "t062_recovery_table": _display_path(recovery_path, repository_root),
            "t062_recovery_table_sha256": _file_sha256(recovery_path),
        },
        "prefilled_recommendation": {
            "comparison": recommendation,
            "sample": protocol,
        },
        "required_user_decisions": [
            {
                "decision_id": "approve_recommended_protocol",
                "prompt": (
                    "Approve the complete prefilled recommendation, or list only "
                    "the fields to change."
                ),
                "recommended_response": "Approve T063",
            }
        ],
        "freeze_rule": (
            "Do not acquire T065 material until the scientific lead approves or "
            "revises this record."
        ),
    }


def _markdown_report(report: Mapping[str, object]) -> str:
    dataset = report["dataset"]
    assert isinstance(dataset, dict)
    methods = report["methods"]
    assert isinstance(methods, dict)
    union = report["simple_union_schwartz_hearst_plodv2"]
    assert isinstance(union, dict)
    union_metrics = union["metrics"]
    assert isinstance(union_metrics, dict)
    recommendation = report["recommendation"]
    assert isinstance(recommendation, dict)
    lines = [
        "# T062 development recovery readout",
        "",
        "This is assisted development evidence, not a blind or population estimate.",
        "",
        "## Revised development view",
        "",
        f"- Strict exact relations: {dataset['strict_relations']}",
        f"- New T061 strict relations: {dataset['new_t061_strict_relations']}",
        f"- Diagnostic relations: {dataset['diagnostic_relations']}",
        "",
        "## Exact-pair results",
        "",
        "| Method | TP | FP | Outside target | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, raw in sorted(methods.items()):
        assert isinstance(raw, dict)
        lines.append(
            f"| {name} | {raw['true_positives']} | {raw['false_positives']} | "
            f"{raw['outside_strict_target']} | {raw['false_negatives']} | "
            f"{raw['precision']:.3f} | {raw['recall']:.3f} | {raw['f1']:.3f} |"
        )
    lines.extend(
        [
            f"| S&H + PLOD exact union | {union_metrics['true_positives']} | "
            f"{union_metrics['false_positives']} | "
            f"{union_metrics['outside_strict_target']} | "
            f"{union_metrics['false_negatives']} | "
            f"{union_metrics['precision']:.3f} | {union_metrics['recall']:.3f} | "
            f"{union_metrics['f1']:.3f} |",
            "",
            "## Recommendation",
            "",
            str(recommendation["rationale"]),
            "",
            "Freeze Schwartz–Hearst as the baseline and the existing transparent "
            "exact union of Schwartz–Hearst plus PLODv2 pairing as the sole "
            "challenger.",
            "Do not advance Jev in this small fresh check.",
            "",
            "The complete occurrence-level recovery and prediction tables are listed "
            "in the JSON report's `artifacts` section.",
        ]
    )
    return "\n".join(lines) + "\n"


def _artifact_endpoints(artifact: PredictionArtifact) -> set[EndpointKey]:
    result: set[EndpointKey] = set()
    for record in artifact.records:
        for prediction in record.predictions:
            if prediction.short_form is not None:
                result.add(
                    (
                        record.document_id,
                        "short_form",
                        prediction.short_form.start,
                        prediction.short_form.end,
                    )
                )
            if prediction.long_form is not None:
                result.add(
                    (
                        record.document_id,
                        "long_form",
                        prediction.long_form.start,
                        prediction.long_form.end,
                    )
                )
    return result


def _source_hashes(paths: Sequence[Path], repository_root: Path) -> dict[str, str]:
    return {_display_path(path, repository_root): _file_sha256(path) for path in paths}


def _display_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        return path.as_posix()


def _required_int(value: Mapping[str, object], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise ValueError(f"{key!r} must be an integer")
    return result


def _overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end


def _object_list(value: Mapping[str, object], key: str) -> list[dict[str, Any]]:
    raw = value.get(key)
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError(f"{key!r} must be a list of objects")
    return raw


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, values: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
            for value in values
        ),
        encoding="utf-8",
        newline="\n",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "decision_key",
    "materialize_development_readout",
    "pair_key",
    "pair_metrics",
    "prediction_keys",
    "recovery_outcome",
]
