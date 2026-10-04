"""Build the frozen T060 comparison and assisted output-review packet."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.domain import AbbreviationDefinition
from abrex.evaluation import compare_resolvers
from abrex.literature.review_models import (
    ReviewCase,
    ReviewPacket,
    ReviewSelection,
    ReviewSpan,
    ReviewSuggestion,
    fingerprint,
    packet_identity_payload,
    validate_packet_identity,
)
from abrex.resolvers import (
    PredictionArtifact,
    fingerprint_prediction_artifact,
    read_prediction_artifact,
)

T060_SCHEMA_VERSION = "t060-development-comparison-v1"
T060_MANIFEST_SCHEMA_VERSION = "t060-evidence-manifest-v1"
DEFAULT_SEED = 20261002

PairKey = tuple[str, int, int, int, int]


def materialize_development_comparison(
    *,
    corpus_path: Path,
    corpus_manifest_path: Path,
    diagnostic_view_path: Path,
    source_packet_path: Path,
    prediction_paths: Mapping[str, Path],
    comparison_path: Path,
    review_packet_path: Path,
    evidence_manifest_path: Path,
    job_result_paths: Mapping[str, Path] | None = None,
    seed: int = DEFAULT_SEED,
    bootstrap_samples: int = 1000,
) -> dict[str, object]:
    """Validate T060 inputs and write deterministic comparison evidence."""

    records, corpus_manifest = read_canonical_dataset(corpus_path, corpus_manifest_path)
    repository_root = corpus_path.resolve().parents[2]
    documents = {record.document.document_id: record.document for record in records}
    dataset_fingerprint = fingerprint_records(records)
    artifacts = {
        name: read_prediction_artifact(
            path,
            documents=documents,
            expected_dataset_fingerprint=dataset_fingerprint,
        )
        for name, path in sorted(prediction_paths.items())
    }
    if len(artifacts) < 2:
        raise ValueError("T060 requires predictions from at least two methods")
    result_paths = job_result_paths or {}

    diagnostic = _read_object(diagnostic_view_path)
    source_packet = ReviewPacket.model_validate(_read_object(source_packet_path))
    validate_packet_identity(source_packet)
    group_by_document = {
        str(case["case_id"]): str(case["article_group_id"])
        for case in _object_list(diagnostic, "cases")
    }
    if set(group_by_document) != set(documents):
        raise ValueError("diagnostic view does not match the frozen document universe")

    comparison = compare_resolvers(
        records,
        {name: artifact.records for name, artifact in artifacts.items()},
        mode="exact_pair",
        group_by_document=group_by_document,
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    known, strict = _known_relations(diagnostic)
    queued, linked = _classify_predictions(artifacts, known, strict)
    input_hashes = {
        "corpus": _file_sha256(corpus_path),
        "corpus_manifest": _file_sha256(corpus_manifest_path),
        "diagnostic_view": _file_sha256(diagnostic_view_path),
        "source_packet": _file_sha256(source_packet_path),
        **{
            f"predictions:{name}": _file_sha256(path)
            for name, path in sorted(prediction_paths.items())
        },
        **{
            f"job_result:{name}": _file_sha256(path)
            for name, path in sorted(result_paths.items())
        },
    }
    source_identity = fingerprint(input_hashes)
    packet = _build_packet(
        source_packet,
        diagnostic,
        queued,
        artifacts,
        source_identity=source_identity,
        seed=seed,
    )
    output: dict[str, object] = {
        "schema_version": T060_SCHEMA_VERSION,
        "status": "review_and_plod_span_audit_pending",
        "dataset": {
            "id": corpus_manifest.dataset_id,
            "fingerprint": dataset_fingerprint,
            "documents": len(records),
            "article_groups": len(set(group_by_document.values())),
            "strict_pairs": sum(len(record.gold_annotations) for record in records),
        },
        "methods": _method_evidence(
            artifacts,
            prediction_paths,
            result_paths,
            repository_root=repository_root,
        ),
        "comparison": comparison.to_dict(),
        "prior_decision_linkage": linked,
        "assisted_review": {
            "packet_id": packet.packet_id,
            "cases": len(packet.cases),
            "suggestions": sum(len(case.suggestions) for case in packet.cases),
            "method_contributions": dict(
                sorted(
                    Counter(
                        method
                        for case in packet.cases
                        for suggestion in case.suggestions
                        for method in suggestion.method_ids
                    ).items()
                )
            ),
            "estimated_minutes": _estimated_minutes(packet),
            "estimate_basis": "30 seconds per passage plus 30 seconds per proposal",
            "exhaustive": True,
            "interpretation": (
                "Every prediction not exactly covered by a frozen T057 decision is "
                "queued. These are proposals, not false positives, until T061 review."
            ),
        },
        "execution_limits": [
            "Strict half-open exact-pair scoring only; pair and span metrics are "
            "not pooled.",
            "The development set and prior assisted decisions are not blind evidence.",
            "Gold-assisted union recall is an oracle diagnostic, not a deployable "
            "score.",
        ],
        "pending": [
            "T061 human review of the assisted output packet",
            "Independent PLOD span output is required to audit unpaired detections",
        ],
    }
    _write_json(comparison_path, output)
    _write_json(review_packet_path, packet.model_dump(mode="json"))
    manifest = {
        "schema_version": T060_MANIFEST_SCHEMA_VERSION,
        "source_identity": source_identity,
        "seed": seed,
        "bootstrap_samples": bootstrap_samples,
        "inputs": input_hashes,
        "outputs": {
            "comparison": {
                "path": _display_path(comparison_path, repository_root),
                "sha256": _file_sha256(comparison_path),
            },
            "review_packet": {
                "path": _display_path(review_packet_path, repository_root),
                "sha256": _file_sha256(review_packet_path),
                "packet_id": packet.packet_id,
                "content_sha256": packet.content_sha256,
            },
        },
    }
    _write_json(evidence_manifest_path, manifest)
    return output


def _known_relations(
    diagnostic: Mapping[str, object],
) -> tuple[dict[PairKey, Mapping[str, object]], set[PairKey]]:
    known: dict[PairKey, Mapping[str, object]] = {}
    strict: set[PairKey] = set()
    for case in _object_list(diagnostic, "cases"):
        document_id = str(case["case_id"])
        for relation in _object_list(case, "relations"):
            short = relation.get("short_form")
            long = relation.get("long_form")
            if not isinstance(short, dict) or not isinstance(long, dict):
                continue
            key = (
                document_id,
                int(short["start"]),
                int(short["end"]),
                int(long["start"]),
                int(long["end"]),
            )
            known[key] = relation
            if (
                relation.get("status") == "correct"
                and relation.get("disposition") == "strict"
            ):
                strict.add(key)
    return known, strict


def _classify_predictions(
    artifacts: Mapping[str, PredictionArtifact],
    known: Mapping[PairKey, Mapping[str, object]],
    strict: set[PairKey],
) -> tuple[dict[PairKey, list[tuple[str, AbbreviationDefinition]]], dict[str, object]]:
    queued: dict[PairKey, list[tuple[str, AbbreviationDefinition]]] = {}
    method_counts: dict[str, Counter[str]] = {}
    for method, artifact in sorted(artifacts.items()):
        counts: Counter[str] = Counter()
        for record in artifact.records:
            for prediction in record.predictions:
                key = _pair_key(prediction)
                if key is None:
                    counts["incomplete"] += 1
                elif key in strict:
                    counts["strict_exact"] += 1
                elif key in known:
                    relation = known[key]
                    counts[f"prior_{relation.get('status', 'unknown')}"] += 1
                else:
                    counts["queued_for_review"] += 1
                    queued.setdefault(key, []).append((method, prediction))
        method_counts[method] = counts
    return queued, {
        "frozen_relation_count": len(known),
        "strict_relation_count": len(strict),
        "method_counts": {
            name: dict(sorted(counts.items()))
            for name, counts in sorted(method_counts.items())
        },
    }


def _build_packet(
    source: ReviewPacket,
    diagnostic: Mapping[str, object],
    queued: Mapping[PairKey, Sequence[tuple[str, AbbreviationDefinition]]],
    artifacts: Mapping[str, PredictionArtifact],
    *,
    source_identity: str,
    seed: int,
) -> ReviewPacket:
    source_cases = {case.case_id: case for case in source.cases}
    prior_by_case = {
        str(case["case_id"]): _object_list(case, "relations")
        for case in _object_list(diagnostic, "cases")
    }
    by_document: dict[
        str, list[tuple[PairKey, Sequence[tuple[str, AbbreviationDefinition]]]]
    ] = {}
    for key, contributions in queued.items():
        by_document.setdefault(key[0], []).append((key, contributions))
    cases: list[ReviewCase] = []
    for document_id in sorted(by_document):
        base = source_cases.get(document_id)
        if base is None:
            raise ValueError(f"source review packet is missing {document_id!r}")
        suggestions = tuple(
            _suggestion(key, contributions, prior_by_case[document_id])
            for key, contributions in sorted(by_document[document_id])
        )
        method_diagnostics = tuple(
            {
                "method_id": method,
                "status": "complete",
                "coverage": "complete",
                "predictions": sum(
                    len(record.predictions) for record in artifact.records
                ),
                "diagnostics": sum(
                    len(record.diagnostics) for record in artifact.records
                ),
            }
            for method, artifact in sorted(artifacts.items())
        )
        cases.append(
            base.model_copy(
                update={
                    "category": "diagnostic",
                    "inventory_category": "t060_novel_prediction",
                    "suggestions": suggestions,
                    "source_comparisons": base.source_comparisons
                    + (
                        {
                            "source": "T057 frozen development decisions",
                            "relations": prior_by_case[document_id],
                        },
                    ),
                    "method_diagnostics": method_diagnostics,
                    "selection_reason": (
                        "Exhaustive T060 output review: at least one prediction was "
                        "not an exact match to a frozen T057 decision."
                    ),
                }
            )
        )
    arm_counts = Counter(case.arm for case in cases)
    suggestion_count = sum(len(case.suggestions) for case in cases)
    selection = ReviewSelection(
        targets={"novel_prediction_cases": len(cases), "proposals": suggestion_count},
        denominators={
            "novel_prediction_cases": len(cases),
            "proposals": suggestion_count,
        },
        selected={"novel_prediction_cases": len(cases), "proposals": suggestion_count},
        shortages={"novel_prediction_cases": 0, "proposals": 0},
        arm_counts=dict(sorted(arm_counts.items())),
        per_article_cap=max(1, len(cases)),
    )
    provisional = ReviewPacket(
        packet_id="pending",
        content_sha256="0" * 64,
        source_manifest_sha256=source_identity,
        source_run_id="t060-development-comparison",
        seed=seed,
        cases=tuple(cases),
        selection=selection,
    )
    digest = fingerprint(packet_identity_payload(provisional))
    packet = provisional.model_copy(
        update={"packet_id": f"t052-{digest[:20]}", "content_sha256": digest}
    )
    validate_packet_identity(packet)
    return packet


def _suggestion(
    key: PairKey,
    contributions: Sequence[tuple[str, AbbreviationDefinition]],
    prior_relations: Sequence[Mapping[str, object]],
) -> ReviewSuggestion:
    _, short_start, short_end, long_start, long_end = key
    methods = tuple(sorted({method for method, _ in contributions}))
    prediction = contributions[0][1]
    classification = (
        "contested_boundary"
        if any(_overlaps_known(key, relation) for relation in prior_relations)
        else "novel_pair"
    )
    digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:20]
    provenance = tuple(
        _prediction_provenance(method, item, classification)
        for method, item in sorted(contributions, key=lambda value: value[0])
    )
    return ReviewSuggestion(
        suggestion_id=f"suggestion-t060-{digest}",
        short_form=ReviewSpan(
            start=short_start, end=short_end, text=prediction.short_form_text or ""
        ),
        long_form=ReviewSpan(
            start=long_start, end=long_end, text=prediction.long_form_text or ""
        ),
        source_pair_ids=tuple(f"t060-{method}-{digest}" for method in methods),
        method_ids=methods,
        provenance=provenance,
    )


def _prediction_provenance(
    method: str, prediction: AbbreviationDefinition, classification: str
) -> dict[str, object]:
    result: dict[str, object] = {
        "method_id": method,
        "classification": classification,
    }
    if prediction.prediction is not None:
        result.update(
            {
                "identity": prediction.prediction.component,
                "version": prediction.prediction.component_version,
                "confidence": prediction.prediction.confidence,
                "score": prediction.prediction.score,
                "model_artifact_fingerprint": (
                    prediction.prediction.model_artifact_fingerprint
                ),
            }
        )
    if prediction.provenance is not None:
        result["adapter_identity"] = prediction.provenance.adapter_identity
        result["transformation_notes"] = list(
            prediction.provenance.transformation_notes
        )
    return result


def _method_evidence(
    artifacts: Mapping[str, PredictionArtifact],
    paths: Mapping[str, Path],
    result_paths: Mapping[str, Path],
    *,
    repository_root: Path,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, artifact in sorted(artifacts.items()):
        item: dict[str, object] = {
            "resolver": {
                "key": artifact.resolver.key,
                "version": artifact.resolver.version,
            },
            "prediction_path": _display_path(paths[name], repository_root),
            "prediction_sha256": _file_sha256(paths[name]),
            "prediction_fingerprint": fingerprint_prediction_artifact(artifact),
            "records": len(artifact.records),
            "predictions": sum(len(record.predictions) for record in artifact.records),
            "diagnostics": sum(len(record.diagnostics) for record in artifact.records),
            "failures": 0,
        }
        result_path = result_paths.get(name)
        if result_path is not None:
            job_result = _read_object(result_path)
            item["execution"] = {
                "status": job_result.get("status"),
                "elapsed_seconds": job_result.get("elapsed_seconds"),
                "result_id": job_result.get("result_id"),
                "bundle_id": job_result.get("bundle_id"),
                "environment": job_result.get("environment"),
            }
        result[name] = item
    return result


def _pair_key(prediction: AbbreviationDefinition) -> PairKey | None:
    if prediction.short_form is None or prediction.long_form is None:
        return None
    return (
        prediction.document_id,
        prediction.short_form.start,
        prediction.short_form.end,
        prediction.long_form.start,
        prediction.long_form.end,
    )


def _overlaps_known(key: PairKey, relation: Mapping[str, object]) -> bool:
    short = relation.get("short_form")
    long = relation.get("long_form")
    if not isinstance(short, dict) or not isinstance(long, dict):
        return False
    return _overlap(key[1], key[2], int(short["start"]), int(short["end"])) or _overlap(
        key[3], key[4], int(long["start"]), int(long["end"])
    )


def _overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end


def _estimated_minutes(packet: ReviewPacket) -> float:
    suggestions = sum(len(case.suggestions) for case in packet.cases)
    return round((len(packet.cases) * 30 + suggestions * 30) / 60, 1)


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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        return path.as_posix()


__all__ = [
    "DEFAULT_SEED",
    "T060_MANIFEST_SCHEMA_VERSION",
    "T060_SCHEMA_VERSION",
    "materialize_development_comparison",
]
