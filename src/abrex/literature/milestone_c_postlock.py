"""Post-lock projection and independent-review preparation for Milestone C."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
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
    BlindReviewCase,
    blind_review_readiness,
    create_blind_packet,
    read_blind_packet,
    write_blind_packet,
)
from abrex.literature.development_views import (
    relation_eligibility,
    validate_relation_evidence,
)
from abrex.literature.review_interchange import write_annotation_state
from abrex.literature.review_models import (
    AnnotationState,
    PairDecision,
    empty_annotation_state,
    fingerprint,
    validate_annotation_state,
)

POLICY_ID = "t057-strict-exact-pair-v1"
SECOND_REVIEW_SEED = 20261006
SECOND_REVIEW_NEGATIVE_FRACTION = 0.10


@dataclass(frozen=True, slots=True)
class MilestoneCPostlockProjection:
    """Materialized execution inputs and independent-review identities."""

    prediction_records: tuple[CorpusRecord, ...]
    gold_records: tuple[CorpusRecord, ...]
    ledger: dict[str, object]
    run_manifest: dict[str, object]
    second_review_manifest: dict[str, object]


def materialize_milestone_c_postlock(
    *,
    packet_path: Path,
    state_path: Path,
    lock_path: Path,
    source_manifest_path: Path,
    protocol_path: Path,
    prediction_path: Path,
    prediction_manifest_path: Path,
    gold_path: Path,
    gold_manifest_path: Path,
    ledger_path: Path,
    run_manifest_path: Path,
    second_review_packet_path: Path,
    second_review_state_path: Path,
    second_review_selection_path: Path,
) -> MilestoneCPostlockProjection:
    """Validate the lock and freeze isolated execution and review artifacts."""

    packet = read_blind_packet(packet_path)
    state = AnnotationState.model_validate_json(state_path.read_text(encoding="utf-8"))
    lock = BlindAnnotationLock.model_validate_json(
        lock_path.read_text(encoding="utf-8")
    )
    source_manifest = _read_object(source_manifest_path)
    protocol = _read_object(protocol_path)
    annotation_packet = packet.annotation_packet()

    _validate_lock(packet.packet_id, packet.content_sha256, state, lock)
    validate_annotation_state(annotation_packet, state)
    readiness = blind_review_readiness(
        annotation_packet, state, tuple(case.case_id for case in packet.cases)
    )
    if not readiness.complete:
        raise ValueError("Milestone C primary annotation is not review-complete")
    _validate_source_boundary(
        packet_path=packet_path,
        source_manifest=source_manifest,
        source_manifest_path=source_manifest_path,
        protocol=protocol,
        protocol_path=protocol_path,
    )
    audit = _audit_annotations(packet.cases, state)

    prediction_records: list[CorpusRecord] = []
    gold_records: list[CorpusRecord] = []
    ledger_cases: list[dict[str, object]] = []
    disposition_counts: Counter[str] = Counter()
    stratum_counts: Counter[str] = Counter()
    strict_relations = 0
    for case in packet.cases:
        document = Document(case.case_id, case.text)
        stratum = _stratum(case)
        provenance = AnnotationProvenance(
            source_corpus="campaign-2026-10-milestone-c",
            source_record_id=case.case_id,
            adapter_identity="milestone-c-postlock-projection",
            adapter_version="1",
            transformation_notes=(
                f"article_id={case.article_id}",
                f"article_group_id={case.article_group_id}",
                f"stratum={stratum}",
            ),
        )
        prediction_records.append(
            CorpusRecord(
                document=document,
                record_id=case.case_id,
                provenance=provenance,
            )
        )
        strict: list[AbbreviationDefinition] = []
        relations: list[dict[str, object]] = []
        annotation = state.annotations[case.case_id]
        for decision in annotation.current.pairs:
            eligibility = relation_eligibility(decision)
            disposition_counts[eligibility.disposition] += 1
            relations.append(
                _relation_row(case.case_id, decision, eligibility.model_dump())
            )
            if eligibility.disposition == "strict":
                strict.append(_gold_definition(case.case_id, decision))
                strict_relations += 1
        gold_records.append(
            CorpusRecord(
                document=document,
                gold_annotations=tuple(strict),
                record_id=case.case_id,
                provenance=provenance,
            )
        )
        stratum_counts[stratum] += 1
        ledger_cases.append(
            {
                "case_id": case.case_id,
                "article_id": case.article_id,
                "article_group_id": case.article_group_id,
                "source_arm": case.arm,
                "source_kind": case.source_kind,
                "stratum": stratum,
                "search_status": annotation.current.missed_definition,
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
        dataset_id="campaign-2026-10-milestone-c-prediction-input-v1",
        validation=ValidationSummary(
            records_seen=len(prediction_tuple), records_kept=len(prediction_tuple)
        ),
        config_fingerprint=packet.content_sha256,
    )
    gold_dataset_manifest = build_dataset_manifest(
        gold_tuple,
        dataset_id="campaign-2026-10-milestone-c-strict-gold-v1",
        validation=ValidationSummary(
            records_seen=len(gold_tuple), records_kept=len(gold_tuple)
        ),
        config_fingerprint=lock.annotation_state_sha256,
    )
    _write_json(prediction_manifest_path, prediction_dataset_manifest.to_dict())
    _write_json(gold_manifest_path, gold_dataset_manifest.to_dict())

    ledger: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-eligibility-ledger-v1",
        "policy_id": POLICY_ID,
        "status": "frozen_primary_gold",
        "cases": ledger_cases,
        "counts": {
            "cases": len(ledger_cases),
            "article_groups": len({case.article_group_id for case in packet.cases}),
            "strict_relations": strict_relations,
            "diagnostic_relations": disposition_counts["diagnostic"],
            "unresolved_relations": disposition_counts["unresolved"],
            "empty_strict_cases": sum(
                not record.gold_annotations for record in gold_tuple
            ),
            "strata": dict(sorted(stratum_counts.items())),
        },
        "annotation_audit": audit,
    }
    ledger["content_sha256"] = fingerprint(ledger)
    _write_json(ledger_path, ledger)

    second_review = _materialize_second_review(
        cases=packet.cases,
        state=state,
        primary_lock=lock,
        primary_lock_path=lock_path,
        protocol_id=packet.protocol_id,
        packet_path=second_review_packet_path,
        state_path=second_review_state_path,
        selection_path=second_review_selection_path,
    )

    run_manifest: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-run-manifest-v1",
        "status": "inputs_frozen_predictions_pending",
        "policy_id": POLICY_ID,
        "prediction_blind_boundary": {
            "packet_id": packet.packet_id,
            "packet_content_sha256": packet.content_sha256,
            "annotation_state_content_sha256": lock.annotation_state_sha256,
            "state_file_sha256": _sha256_file(state_path),
            "lock_file_sha256": _sha256_file(lock_path),
            "locked_at": lock.locked_at,
            "predictions_exposed_before_lock": lock.predictions_exposed,
        },
        "protocol": {
            "path": protocol_path.as_posix(),
            "sha256": _sha256_file(protocol_path),
            "status": protocol.get("status"),
            "methods": protocol.get("methods"),
        },
        "source_isolation": {
            "source_manifest": source_manifest_path.as_posix(),
            "source_manifest_sha256": _sha256_file(source_manifest_path),
            "article_groups": len({case.article_group_id for case in packet.cases}),
            "evaluated_methods_run_during_sampling": False,
            "candidate_generators_run_during_sampling": False,
        },
        "datasets": {
            "prediction_input": {
                "path": prediction_path.as_posix(),
                "manifest_path": prediction_manifest_path.as_posix(),
                "fingerprint": prediction_fingerprint,
                "gold_annotations": 0,
            },
            "local_strict_gold": {
                "path": gold_path.as_posix(),
                "manifest_path": gold_manifest_path.as_posix(),
                "fingerprint": gold_fingerprint,
                "gold_annotations": strict_relations,
                "portable_bundle_allowed": False,
            },
        },
        "eligibility_ledger": {
            "path": ledger_path.as_posix(),
            "content_sha256": ledger["content_sha256"],
        },
        "second_review": {
            "selection_manifest": second_review_selection_path.as_posix(),
            "selection_content_sha256": second_review["content_sha256"],
            "status": "prediction_blind_review_pending",
        },
    }
    run_manifest["content_sha256"] = fingerprint(run_manifest)
    _write_json(run_manifest_path, run_manifest)
    return MilestoneCPostlockProjection(
        prediction_tuple, gold_tuple, ledger, run_manifest, second_review
    )


def _validate_lock(
    packet_id: str,
    packet_content_sha256: str,
    state: AnnotationState,
    lock: BlindAnnotationLock,
) -> None:
    if (
        lock.packet_id != packet_id
        or lock.packet_content_sha256 != packet_content_sha256
    ):
        raise ValueError("Milestone C lock does not bind the frozen packet")
    if lock.annotation_state_sha256 != fingerprint(state.model_dump(mode="json")):
        raise ValueError("Milestone C lock does not bind the annotation state")
    if lock.predictions_exposed:
        raise ValueError("Milestone C lock is not prediction-blind")


def _validate_source_boundary(
    *,
    packet_path: Path,
    source_manifest: dict[str, Any],
    source_manifest_path: Path,
    protocol: dict[str, Any],
    protocol_path: Path,
) -> None:
    blindness = source_manifest.get("blindness")
    if not isinstance(blindness, dict) or any(
        blindness.get(key) is not False
        for key in (
            "candidate_generators_run",
            "evaluated_methods_run",
            "predictions_exposed",
            "token_enrichment_used",
        )
    ):
        raise ValueError("Milestone C source manifest does not preserve blindness")
    packet = source_manifest.get("packet")
    recorded_protocol = source_manifest.get("protocol")
    if not isinstance(packet, dict) or not isinstance(recorded_protocol, dict):
        raise ValueError("Milestone C source manifest lacks frozen identities")
    if packet.get("sha256") != _sha256_file(packet_path):
        raise ValueError("Milestone C source manifest packet file hash changed")
    if recorded_protocol.get("sha256") != _sha256_file(protocol_path):
        raise ValueError("Milestone C source manifest protocol hash changed")
    if source_manifest.get("status") != "complete_source_only_sample_frozen":
        raise ValueError("Milestone C source sample is not frozen")
    if protocol.get("status") != "approved_and_frozen":
        raise ValueError("Milestone C protocol is not approved and frozen")
    if not source_manifest_path.is_file():
        raise ValueError("Milestone C source manifest is unavailable")


def _audit_annotations(
    cases: tuple[BlindReviewCase, ...], state: AnnotationState
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    pair_count = 0
    span_count = 0
    for case in cases:
        annotation = state.annotations.get(case.case_id)
        if annotation is None:
            issues.append({"case_id": case.case_id, "kind": "missing_annotation"})
            continue
        exact_pairs: set[tuple[int, int, int, int]] = set()
        for pair in annotation.current.pairs:
            pair_count += 1
            validate_relation_evidence(pair)
            for role, span in (
                ("short_form", pair.short_form),
                ("long_form", pair.long_form),
                *tuple(
                    (f"evidence_{index}", evidence)
                    for index, evidence in enumerate(pair.evidence_spans, start=1)
                ),
            ):
                if span is None:
                    continue
                span_count += 1
                if span.text != span.text.strip():
                    issues.append(
                        {
                            "case_id": case.case_id,
                            "decision_id": pair.decision_id,
                            "kind": "span_boundary_whitespace",
                            "role": role,
                        }
                    )
            if pair.notes != pair.notes.strip():
                issues.append(
                    {
                        "case_id": case.case_id,
                        "decision_id": pair.decision_id,
                        "kind": "relation_note_boundary_whitespace",
                    }
                )
            if pair.interpretation != pair.interpretation.strip():
                issues.append(
                    {
                        "case_id": case.case_id,
                        "decision_id": pair.decision_id,
                        "kind": "interpretation_boundary_whitespace",
                    }
                )
            if pair.short_form is not None and pair.long_form is not None:
                key = (
                    pair.short_form.start,
                    pair.short_form.end,
                    pair.long_form.start,
                    pair.long_form.end,
                )
                if key in exact_pairs:
                    issues.append(
                        {
                            "case_id": case.case_id,
                            "decision_id": pair.decision_id,
                            "kind": "duplicate_exact_relation",
                        }
                    )
                exact_pairs.add(key)
                if (
                    pair.short_form.start < pair.long_form.end
                    and pair.long_form.start < pair.short_form.end
                ):
                    issues.append(
                        {
                            "case_id": case.case_id,
                            "decision_id": pair.decision_id,
                            "kind": "overlapping_endpoints",
                        }
                    )
    if issues:
        raise ValueError(f"Milestone C annotation audit failed: {issues}")
    return {
        "status": "passed",
        "cases": len(cases),
        "pairs": pair_count,
        "spans": span_count,
        "issues": 0,
    }


def _materialize_second_review(
    *,
    cases: tuple[BlindReviewCase, ...],
    state: AnnotationState,
    primary_lock: BlindAnnotationLock,
    primary_lock_path: Path,
    protocol_id: str,
    packet_path: Path,
    state_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    positive_ids = {
        case.case_id for case in cases if state.annotations[case.case_id].current.pairs
    }
    negative_cases = sorted(
        (case for case in cases if case.case_id not in positive_ids),
        key=lambda case: case.case_id,
    )
    negative_count = math.ceil(len(negative_cases) * SECOND_REVIEW_NEGATIVE_FRACTION)
    sampled_negatives = {
        case.case_id
        for case in sorted(
            negative_cases,
            key=lambda case: hashlib.sha256(
                json.dumps(
                    [SECOND_REVIEW_SEED, "second-review-negative", case.case_id],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        )[:negative_count]
    }
    selected_ids = positive_ids | sampled_negatives
    selected_cases = tuple(case for case in cases if case.case_id in selected_ids)
    second_packet = create_blind_packet(
        selected_cases,
        protocol_id=f"{protocol_id}-independent-second-review-v1",
        seed=SECOND_REVIEW_SEED,
    )
    write_blind_packet(second_packet, packet_path)
    write_annotation_state(
        empty_annotation_state(second_packet.annotation_packet()), state_path
    )
    manifest: dict[str, object] = {
        "schema_version": ("campaign-2026-10-milestone-c-second-review-selection-v1"),
        "status": "prediction_blind_review_pending",
        "seed": SECOND_REVIEW_SEED,
        "negative_fraction": SECOND_REVIEW_NEGATIVE_FRACTION,
        "negative_rounding": "ceiling",
        "negative_ranking": (
            "ascending sha256(canonical compact JSON "
            "[seed,'second-review-negative',case_id])"
        ),
        "primary_lock": {
            "path": primary_lock_path.as_posix(),
            "sha256": _sha256_file(primary_lock_path),
            "annotation_state_sha256": primary_lock.annotation_state_sha256,
        },
        "packet": {
            "path": packet_path.as_posix(),
            "packet_id": second_packet.packet_id,
            "content_sha256": second_packet.content_sha256,
            "sha256": _sha256_file(packet_path),
        },
        "state": {
            "path": state_path.as_posix(),
            "sha256": _sha256_file(state_path),
            "annotation_count": 0,
        },
        "counts": {
            "primary_cases": len(cases),
            "positive_cases": len(positive_ids),
            "negative_cases": len(negative_cases),
            "sampled_negative_cases": len(sampled_negatives),
            "selected_cases": len(selected_cases),
        },
        "selected_case_ids": [case.case_id for case in selected_cases],
        "owner_only_review_focus": [
            {
                "case_id": "milestone-c-60282f673febc655719c",
                "decision_id": "added-60d66ddf-09a8-4d4c-b9f8-8370b1e1ea74",
                "kind": "note_context_consistency",
                "reason": (
                    "The primary note says outside knowledge or document support is "
                    "required while context_requirement is text_alone. Preserve the "
                    "locked primary answer and resolve only after independent review."
                ),
            }
        ],
    }
    manifest["content_sha256"] = fingerprint(manifest)
    _write_json(selection_path, manifest)
    return manifest


def _stratum(case: BlindReviewCase) -> str:
    if case.source_kind == "table_or_list":
        return "structural_challenge"
    if case.arm == "pubmed_abstract":
        return "representative_pubmed_abstract"
    return "representative_pmc_prose"


def _relation_row(
    case_id: str, decision: PairDecision, eligibility: dict[str, object]
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
            source_corpus="campaign-2026-10-milestone-c-primary",
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
            adapter_identity="milestone-c-postlock-projection",
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


__all__ = [
    "MilestoneCPostlockProjection",
    "materialize_milestone_c_postlock",
]
