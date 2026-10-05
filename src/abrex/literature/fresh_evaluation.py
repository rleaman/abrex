"""Immutable T067 projection of prediction-blind review evidence.

This module deliberately creates two datasets with identical documents: a
prediction-only corpus for resolver execution and a local gold corpus for
evaluation after predictions have been frozen.  The prediction corpus is the
only one referenced by portable job configurations.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from abrex.corpora import build_dataset_manifest, write_canonical_jsonl
from abrex.corpora.validation import ValidationSummary
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    SourceTextSpan,
    TextSpan,
)
from abrex.literature.blind_review import (
    BlindAnnotationLock,
    blind_review_readiness,
    read_blind_packet,
)
from abrex.literature.development_views import relation_eligibility
from abrex.literature.review_models import (
    AnnotationState,
    PairDecision,
    fingerprint,
    validate_annotation_state,
)

POLICY_ID = "t057-strict-exact-pair-v1"


@dataclass(frozen=True, slots=True)
class FreshProjection:
    """Materialized T067 inputs and their immutable identities."""

    prediction_records: tuple[CorpusRecord, ...]
    gold_records: tuple[CorpusRecord, ...]
    ledger: dict[str, object]
    manifest: dict[str, object]


def materialize_fresh_projection(
    *,
    packet_path: Path,
    state_path: Path,
    lock_path: Path,
    correction_manifest_path: Path,
    source_manifest_path: Path,
    protocol_path: Path,
    component_config_paths: Mapping[str, Path],
    prediction_path: Path,
    prediction_manifest_path: Path,
    gold_path: Path,
    gold_manifest_path: Path,
    ledger_path: Path,
    run_manifest_path: Path,
) -> FreshProjection:
    """Validate the blind boundary and freeze separate execution/gold views."""

    correction = _read_object(correction_manifest_path)
    source_manifest = _read_object(source_manifest_path)
    protocol = _read_object(protocol_path)
    packet = read_blind_packet(packet_path)
    state = AnnotationState.model_validate_json(state_path.read_text(encoding="utf-8"))
    lock = BlindAnnotationLock.model_validate_json(
        lock_path.read_text(encoding="utf-8")
    )

    _validate_lock(packet.content_sha256, packet.packet_id, state, lock)
    _validate_correction_files(correction, state_path, lock_path)
    annotation_packet = packet.annotation_packet()
    validate_annotation_state(annotation_packet, state)
    readiness = blind_review_readiness(
        annotation_packet, state, tuple(case.case_id for case in packet.cases)
    )
    if not readiness.complete:
        raise ValueError("T066 corrected annotation state is not review-complete")
    _validate_blind_source(source_manifest, protocol_path, protocol)
    frozen_components = _validate_protocol_components(protocol, component_config_paths)

    prediction_records: list[CorpusRecord] = []
    gold_records: list[CorpusRecord] = []
    ledger_cases: list[dict[str, object]] = []
    disposition_counts: Counter[str] = Counter()
    arm_counts: Counter[str] = Counter()
    strict_relations = 0
    for case in packet.cases:
        document = Document(case.case_id, case.text)
        provenance = AnnotationProvenance(
            source_corpus="T065-fresh-prediction-blind",
            source_record_id=case.case_id,
            adapter_identity="t067-fresh-projection",
            adapter_version="1",
            transformation_notes=(
                f"article_id={case.article_id}",
                f"article_group_id={case.article_group_id}",
                f"source_kind={case.source_kind}",
                f"source_arm={case.arm}",
            ),
        )
        prediction_records.append(
            CorpusRecord(
                document=document,
                record_id=case.case_id,
                provenance=provenance,
            )
        )
        annotation = state.annotations[case.case_id]
        strict: list[AbbreviationDefinition] = []
        relations: list[dict[str, object]] = []
        for decision in annotation.current.pairs:
            eligibility = relation_eligibility(decision)
            disposition_counts[eligibility.disposition] += 1
            row = _relation_row(case.case_id, decision, eligibility.model_dump())
            relations.append(row)
            if eligibility.disposition == "strict":
                strict.append(_gold_definition(case.case_id, decision))
                strict_relations += 1
        evaluation_arm = (
            "table_or_list" if case.source_kind == "table_or_list" else "prose"
        )
        arm_counts[evaluation_arm] += 1
        gold_records.append(
            CorpusRecord(
                document=document,
                gold_annotations=tuple(strict),
                record_id=case.case_id,
                provenance=provenance,
            )
        )
        ledger_cases.append(
            {
                "case_id": case.case_id,
                "article_id": case.article_id,
                "article_group_id": case.article_group_id,
                "source_arm": case.arm,
                "source_kind": case.source_kind,
                "evaluation_arm": evaluation_arm,
                "search_status": "searched",
                "metric_eligible": True,
                "strict_relation_count": len(strict),
                "relations": relations,
            }
        )

    prediction_tuple = tuple(prediction_records)
    gold_tuple = tuple(gold_records)
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_fingerprint = write_canonical_jsonl(prediction_tuple, prediction_path)
    gold_fingerprint = write_canonical_jsonl(gold_tuple, gold_path)
    prediction_dataset_manifest = build_dataset_manifest(
        prediction_tuple,
        dataset_id="T067-fresh-prediction-input-v1",
        validation=ValidationSummary(
            records_seen=len(prediction_tuple), records_kept=len(prediction_tuple)
        ),
        config_fingerprint=packet.content_sha256,
    )
    gold_dataset_manifest = build_dataset_manifest(
        gold_tuple,
        dataset_id="T067-fresh-strict-gold-v1",
        validation=ValidationSummary(
            records_seen=len(gold_tuple), records_kept=len(gold_tuple)
        ),
        config_fingerprint=lock.annotation_state_sha256,
    )
    _write_json(prediction_manifest_path, prediction_dataset_manifest.to_dict())
    _write_json(gold_manifest_path, gold_dataset_manifest.to_dict())

    ledger: dict[str, object] = {
        "schema_version": "t067-fresh-eligibility-ledger-v1",
        "policy_id": POLICY_ID,
        "status": "frozen_primary_gold",
        "cases": ledger_cases,
        "counts": {
            "cases": len(ledger_cases),
            "article_groups": len({case.article_group_id for case in packet.cases}),
            "strict_relations": strict_relations,
            "diagnostic_relations": disposition_counts["diagnostic"],
            "unresolved_relations": disposition_counts["unresolved"],
            "prose_cases": arm_counts["prose"],
            "table_or_list_cases": arm_counts["table_or_list"],
            "empty_strict_cases": sum(
                not record.gold_annotations for record in gold_tuple
            ),
        },
    }
    ledger["content_sha256"] = fingerprint(ledger)
    _write_json(ledger_path, ledger)

    run_manifest: dict[str, object] = {
        "schema_version": "t067-fresh-run-manifest-v1",
        "status": "inputs_frozen_predictions_pending",
        "policy_id": POLICY_ID,
        "prediction_blind_boundary": {
            "packet_id": packet.packet_id,
            "packet_content_sha256": packet.content_sha256,
            "annotation_state_content_sha256": lock.annotation_state_sha256,
            "lock_file_sha256": _sha256_file(lock_path),
            "correction_manifest_sha256": _sha256_file(correction_manifest_path),
            "predictions_exposed_before_lock": lock.predictions_exposed,
        },
        "protocol": {
            "path": _relative(protocol_path, run_manifest_path),
            "sha256": _sha256_file(protocol_path),
            "status": protocol.get("status"),
            "components": frozen_components,
        },
        "source_isolation": {
            "source_manifest": _relative(source_manifest_path, run_manifest_path),
            "source_manifest_sha256": _sha256_file(source_manifest_path),
            "article_groups": len({case.article_group_id for case in packet.cases}),
            "evaluated_methods_run_during_sampling": False,
            "candidate_generators_run_during_sampling": False,
        },
        "datasets": {
            "prediction_input": {
                "path": _relative(prediction_path, run_manifest_path),
                "manifest_path": _relative(prediction_manifest_path, run_manifest_path),
                "fingerprint": prediction_fingerprint,
                "gold_annotations": 0,
            },
            "local_strict_gold": {
                "path": _relative(gold_path, run_manifest_path),
                "manifest_path": _relative(gold_manifest_path, run_manifest_path),
                "fingerprint": gold_fingerprint,
                "gold_annotations": strict_relations,
                "portable_bundle_allowed": False,
            },
        },
        "eligibility_ledger": {
            "path": _relative(ledger_path, run_manifest_path),
            "content_sha256": ledger["content_sha256"],
        },
    }
    run_manifest["content_sha256"] = fingerprint(run_manifest)
    _write_json(run_manifest_path, run_manifest)
    return FreshProjection(prediction_tuple, gold_tuple, ledger, run_manifest)


def _validate_lock(
    packet_sha256: str,
    packet_id: str,
    state: AnnotationState,
    lock: BlindAnnotationLock,
) -> None:
    if lock.packet_id != packet_id or lock.packet_content_sha256 != packet_sha256:
        raise ValueError("T066 lock does not bind the frozen T065 packet")
    if lock.annotation_state_sha256 != fingerprint(state.model_dump(mode="json")):
        raise ValueError("T066 lock does not bind the corrected annotation state")
    if lock.predictions_exposed:
        raise ValueError("T066 lock is not prediction-blind")


def _validate_correction_files(
    correction: Mapping[str, object], state_path: Path, lock_path: Path
) -> None:
    corrected = correction.get("corrected")
    if not isinstance(corrected, dict):
        raise ValueError("T066 correction manifest lacks corrected identities")
    expected = {
        "state_file_sha256": _sha256_file(state_path),
        "lock_file_sha256": _sha256_file(lock_path),
    }
    for key, actual in expected.items():
        if corrected.get(key) != actual:
            raise ValueError(f"T066 correction manifest mismatch: {key}")
    exposure = correction.get("exposure")
    if (
        not isinstance(exposure, dict)
        or exposure.get("predictions_exposed_before_correction") is not False
    ):
        raise ValueError("T066 correction was not recorded as prediction-blind")


def _validate_blind_source(
    source: Mapping[str, object], protocol_path: Path, protocol: Mapping[str, object]
) -> None:
    blindness = source.get("blindness")
    if not isinstance(blindness, dict) or any(
        blindness.get(key) is not False
        for key in (
            "candidate_generators_run",
            "evaluated_methods_run",
            "predictions_exposed",
            "token_enrichment_used",
        )
    ):
        raise ValueError("T065 source manifest does not preserve prediction blindness")
    config = source.get("config")
    if not isinstance(config, dict):
        raise ValueError("T065 source manifest lacks configuration")
    if config.get("protocol_sha256") != _sha256_file(protocol_path):
        raise ValueError("T065 source manifest refers to a different T063 protocol")
    if protocol.get("status") != "approved_and_frozen":
        raise ValueError("T063 protocol is not approved and frozen")


def _validate_protocol_components(
    protocol: Mapping[str, object], paths: Mapping[str, Path]
) -> list[dict[str, str]]:
    recommendation = protocol.get("prefilled_recommendation")
    comparison = (
        recommendation.get("comparison") if isinstance(recommendation, dict) else None
    )
    parameters = comparison.get("parameters") if isinstance(comparison, dict) else None
    frozen = (
        parameters.get("frozen_components") if isinstance(parameters, dict) else None
    )
    if not isinstance(frozen, list):
        raise ValueError("T063 protocol lacks frozen components")
    result: list[dict[str, str]] = []
    expected_by_key = {
        str(item["key"]): {
            "sha256": str(item["config_sha256"]),
            "path": str(item.get("config_path", "")),
        }
        for item in frozen
        if isinstance(item, dict) and "key" in item and "config_sha256" in item
    }
    if set(expected_by_key) != set(paths):
        raise ValueError("supplied T067 components differ from the T063 freeze")
    for key, path in sorted(paths.items()):
        actual = _sha256_file(path)
        if actual != expected_by_key[key]["sha256"]:
            raise ValueError(f"frozen component configuration changed: {key}")
        result.append(
            {
                "key": key,
                "path": expected_by_key[key]["path"],
                "sha256": actual,
            }
        )
    return result


def _relation_row(
    case_id: str, decision: PairDecision, eligibility: Mapping[str, object]
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "decision_id": decision.decision_id,
        "status": decision.status,
        "short_form": decision.short_form.model_dump(mode="json")
        if decision.short_form
        else None,
        "long_form": decision.long_form.model_dump(mode="json")
        if decision.long_form
        else None,
        "relation_kind": decision.relation_kind,
        "evidence_structure": decision.evidence_structure,
        "context_requirement": decision.context_requirement,
        "source_error": decision.source_error,
        "disposition": eligibility["disposition"],
        "eligibility_reason": eligibility["reason"],
    }


def _gold_definition(case_id: str, decision: PairDecision) -> AbbreviationDefinition:
    if decision.short_form is None or decision.long_form is None:
        raise ValueError("strict relation lacks an exact endpoint")
    return AbbreviationDefinition(
        document_id=case_id,
        short_form=TextSpan(decision.short_form.start, decision.short_form.end),
        long_form=TextSpan(decision.long_form.start, decision.long_form.end),
        short_form_text=decision.short_form.text,
        long_form_text=decision.long_form.text,
        provenance=AnnotationProvenance(
            source_corpus="T066-corrected-v2",
            source_record_id=case_id,
            source_annotation_id=decision.decision_id,
            original_short_form=SourceTextSpan(
                decision.short_form.start,
                decision.short_form.end,
                decision.short_form.text,
            ),
            original_long_form=SourceTextSpan(
                decision.long_form.start,
                decision.long_form.end,
                decision.long_form.text,
            ),
            adapter_identity="t067-fresh-projection",
            adapter_version="1",
            transformation_notes=("verbatim_half_open_review_span",),
        ),
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, anchor: Path) -> str:
    try:
        return path.resolve().relative_to(anchor.resolve().parents[2]).as_posix()
    except ValueError:
        return str(path.resolve())


__all__ = ["FreshProjection", "POLICY_ID", "materialize_fresh_projection"]
