"""Audit a completed T066 blind annotation lock without changing it."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from abrex.literature.blind_review import (
    BlindAnnotationLock,
    blind_review_readiness,
    read_blind_packet,
)
from abrex.literature.review_models import (
    AnnotationState,
    fingerprint,
    validate_annotation_state,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_lock(
    packet_path: Path, state_path: Path, lock_path: Path
) -> dict[str, object]:
    """Validate immutable identities, completeness, and review-worthy flags."""

    packet = read_blind_packet(packet_path)
    annotation_packet = packet.annotation_packet()
    state = AnnotationState.model_validate_json(state_path.read_text(encoding="utf-8"))
    lock = BlindAnnotationLock.model_validate_json(
        lock_path.read_text(encoding="utf-8")
    )
    validate_annotation_state(annotation_packet, state)
    readiness = blind_review_readiness(
        annotation_packet,
        state,
        tuple(case.case_id for case in annotation_packet.cases),
    )
    state_digest = fingerprint(state.model_dump(mode="json"))
    checks = {
        "packet_identity_valid": True,
        "state_identity_valid": (
            state.packet_id == packet.packet_id
            and state.packet_content_sha256 == packet.content_sha256
        ),
        "lock_packet_identity_valid": (
            lock.packet_id == packet.packet_id
            and lock.packet_content_sha256 == packet.content_sha256
        ),
        "lock_state_digest_valid": lock.annotation_state_sha256 == state_digest,
        "all_cases_annotated": len(state.annotations) == len(packet.cases),
        "all_cases_ready": readiness.complete,
        "prediction_blind": (
            lock.exposure_status == "prediction_blind"
            and lock.predictions_exposed is False
        ),
    }
    source_kinds = {case.case_id: case.source_kind for case in packet.cases}
    positions = {case.case_id: index for index, case in enumerate(packet.cases, 1)}
    relation_counts: Counter[str] = Counter()
    zero_relation_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    uncertain: list[dict[str, object]] = []
    source_errors: list[dict[str, object]] = []
    other_relations: list[dict[str, object]] = []
    duplicates: list[dict[str, object]] = []
    total_revisions = 0
    for case_id, annotation in state.annotations.items():
        snapshot = annotation.current
        kind = source_kinds[case_id]
        total_revisions += annotation.revision
        if not snapshot.pairs:
            zero_relation_counts[kind] += 1
        seen: set[tuple[int, int, int, int]] = set()
        for relation in snapshot.pairs:
            relation_counts[kind] += 1
            status_counts[relation.status] += 1
            fields = {
                "status": relation.status,
                "relation_kind": relation.relation_kind,
                "evidence_structure": relation.evidence_structure,
                "context_requirement": relation.context_requirement,
            }
            if "uncertain" in fields.values() or relation.status != "correct":
                uncertain.append(
                    {
                        "case_id": case_id,
                        "case_number": positions[case_id],
                        "decision_id": relation.decision_id,
                        **fields,
                    }
                )
            if relation.source_error:
                source_errors.append(
                    {
                        "case_id": case_id,
                        "case_number": positions[case_id],
                        "decision_id": relation.decision_id,
                    }
                )
            if relation.relation_kind == "other_naming_or_code_relation":
                other_relations.append(
                    {
                        "case_id": case_id,
                        "case_number": positions[case_id],
                        "decision_id": relation.decision_id,
                    }
                )
            if relation.short_form is None or relation.long_form is None:
                continue
            key = (
                relation.short_form.start,
                relation.short_form.end,
                relation.long_form.start,
                relation.long_form.end,
            )
            if key in seen:
                duplicates.append(
                    {
                        "case_id": case_id,
                        "case_number": positions[case_id],
                        "decision_id": relation.decision_id,
                    }
                )
            seen.add(key)
    integrity_passed = all(checks.values()) and not duplicates
    return {
        "schema_version": "t066-lock-audit-v1",
        "status": "passed" if integrity_passed else "failed",
        "integrity_checks": checks,
        "counts": {
            "cases": len(packet.cases),
            "annotated_cases": len(state.annotations),
            "relations": sum(relation_counts.values()),
            "zero_relation_cases": sum(zero_relation_counts.values()),
            "revisions": total_revisions,
            "relations_by_source_kind": dict(sorted(relation_counts.items())),
            "zero_relation_cases_by_source_kind": dict(
                sorted(zero_relation_counts.items())
            ),
            "relation_statuses": dict(sorted(status_counts.items())),
        },
        "review_flags": {
            "uncertain_relations": uncertain,
            "source_error_relations": source_errors,
            "other_naming_or_code_relations": other_relations,
            "duplicate_endpoint_relations": duplicates,
        },
        "artifacts": {
            "packet_file_sha256": _sha256(packet_path),
            "state_file_sha256": _sha256(state_path),
            "state_content_sha256": state_digest,
            "lock_file_sha256": _sha256(lock_path),
            "locked_at": lock.locked_at,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path("evidence/T065/review-packet-blind-v1.json"),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("evidence/T065/review-packet-blind-v1.annotations.json"),
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("evidence/T065/review-packet-blind-v1.annotations.lock.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_lock(args.packet, args.state, args.lock)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
