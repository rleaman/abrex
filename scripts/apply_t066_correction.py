"""Create the authorized prediction-blind T066 correction revision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from abrex.literature.blind_review import (
    BlindAnnotationLock,
    create_annotation_lock,
    read_blind_packet,
    write_annotation_lock,
)
from abrex.literature.review_models import (
    AnnotationState,
    AnnotationSubmission,
    CaseSubmission,
    DecisionSnapshot,
    PairDecision,
    apply_submission,
    fingerprint,
    validate_annotation_state,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "evidence/T065/review-packet-blind-v1.json"
ORIGINAL_STATE_PATH = ROOT / "evidence/T065/review-packet-blind-v1.annotations.json"
ORIGINAL_LOCK_PATH = ROOT / "evidence/T065/review-packet-blind-v1.annotations.lock.json"
OUTPUT_DIR = ROOT / "evidence/T066"
CORRECTED_STATE_PATH = (
    OUTPUT_DIR / "review-packet-blind-v1.annotations.corrected-v2.json"
)
CORRECTED_LOCK_PATH = (
    OUTPUT_DIR / "review-packet-blind-v1.annotations.corrected-v2.lock.json"
)
MANIFEST_PATH = OUTPUT_DIR / "correction-manifest-v2.json"

EXPECTED_PACKET_FILE_SHA256 = (
    "394fa95caba002af8f0a8825674cec0a8c1d245883b083af4b0ed24e6ef791e5"
)
EXPECTED_ORIGINAL_STATE_FILE_SHA256 = (
    "7ecb3f755441fb401175e7d65af71b117b0b2d6d57b49cac5fc41e294f2d5d97"
)
EXPECTED_ORIGINAL_LOCK_FILE_SHA256 = (
    "5a3f17d23b4caa008fe1bc8bde1fa492ae77d856b9e042be24e907eeb2d52367"
)

CORRECTIONS = {
    "fresh-84c175f848ec1493c7a3": (
        12,
        "added-00b602aa-2119-444b-90fa-7d4cffe34a77",
    ),
    "fresh-5a4294e47425c9acf1c4": (
        30,
        "added-8a74cda7-1a3d-428c-80eb-94766af5b364",
    ),
}
TARGET_FIELDS = {
    "status": "correct",
    "relation_kind": "abbreviation_expansion",
    "evidence_structure": "contiguous_shared",
    "context_requirement": "text_alone",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _assert_inputs() -> None:
    expected = {
        PACKET_PATH: EXPECTED_PACKET_FILE_SHA256,
        ORIGINAL_STATE_PATH: EXPECTED_ORIGINAL_STATE_FILE_SHA256,
        ORIGINAL_LOCK_PATH: EXPECTED_ORIGINAL_LOCK_FILE_SHA256,
    }
    for path, digest in expected.items():
        if _sha256(path) != digest:
            raise RuntimeError(f"refusing correction: input hash changed for {path}")


def _correct_snapshot(
    snapshot: DecisionSnapshot, decision_id: str
) -> tuple[DecisionSnapshot, dict[str, object]]:
    changed = False
    revised: list[PairDecision] = []
    recorded_change: dict[str, object] = {}
    for relation in snapshot.pairs:
        if relation.decision_id != decision_id:
            revised.append(relation)
            continue
        before = relation.model_dump(mode="json")
        after = dict(before)
        after.update(TARGET_FIELDS)
        revised_relation = PairDecision.model_validate(after)
        revised.append(revised_relation)
        recorded_change = {
            "decision_id": decision_id,
            "short_form": relation.short_form.text if relation.short_form else None,
            "long_form": relation.long_form.text if relation.long_form else None,
            "before": {key: before[key] for key in TARGET_FIELDS},
            "after": dict(TARGET_FIELDS),
        }
        changed = True
    if not changed:
        raise RuntimeError(f"target decision is absent: {decision_id}")
    return (
        DecisionSnapshot(
            pairs=tuple(revised),
            missed_definition=snapshot.missed_definition,
            notes=snapshot.notes,
        ),
        recorded_change,
    )


def _assert_exact_revision(
    original: AnnotationState, corrected: AnnotationState
) -> None:
    if original.current_case_id != corrected.current_case_id:
        raise RuntimeError("correction changed the resume case")
    for case_id, original_annotation in original.annotations.items():
        corrected_annotation = corrected.annotations[case_id]
        if case_id not in CORRECTIONS:
            if corrected_annotation != original_annotation:
                raise RuntimeError(f"correction changed unrelated case {case_id}")
            continue
        if corrected_annotation.revision != original_annotation.revision + 1:
            raise RuntimeError(f"correction did not add one revision for {case_id}")
        if corrected_annotation.history[:-1] != original_annotation.history:
            raise RuntimeError(f"correction changed prior history for {case_id}")
        before_pairs = {
            pair.decision_id: pair.model_dump(mode="json")
            for pair in original_annotation.current.pairs
        }
        after_pairs = {
            pair.decision_id: pair.model_dump(mode="json")
            for pair in corrected_annotation.current.pairs
        }
        decision_id = CORRECTIONS[case_id][1]
        for current_id, before in before_pairs.items():
            after = after_pairs[current_id]
            if current_id != decision_id and after != before:
                raise RuntimeError(
                    f"correction changed unrelated relation {current_id}"
                )
            if current_id == decision_id:
                differences = {key for key in before if before[key] != after[key]}
                expected_differences = {
                    key
                    for key, target in TARGET_FIELDS.items()
                    if before[key] != target
                }
                if differences != expected_differences or any(
                    after[key] != target for key, target in TARGET_FIELDS.items()
                ):
                    raise RuntimeError(
                        f"unexpected corrected fields for {current_id}: {differences}"
                    )


def main() -> int:
    """Apply two authorized corrections and bind them to a replacement lock."""

    _assert_inputs()
    packet = read_blind_packet(PACKET_PATH)
    annotation_packet = packet.annotation_packet()
    original = AnnotationState.model_validate_json(
        ORIGINAL_STATE_PATH.read_text(encoding="utf-8")
    )
    original_lock = BlindAnnotationLock.model_validate_json(
        ORIGINAL_LOCK_PATH.read_text(encoding="utf-8")
    )
    if original_lock.annotation_state_sha256 != fingerprint(
        original.model_dump(mode="json")
    ):
        raise RuntimeError("original lock does not bind the supplied state")
    submissions: dict[str, CaseSubmission] = {}
    changes: list[dict[str, object]] = []
    for case_id, (case_number, decision_id) in CORRECTIONS.items():
        annotation = original.annotations[case_id]
        snapshot, change = _correct_snapshot(annotation.current, decision_id)
        change.update({"case_id": case_id, "case_number": case_number})
        changes.append(change)
        submissions[case_id] = CaseSubmission(
            expected_revision=annotation.revision,
            decision=snapshot,
        )
    corrected = apply_submission(
        annotation_packet,
        original,
        AnnotationSubmission(
            packet_id=packet.packet_id,
            packet_content_sha256=packet.content_sha256,
            current_case_id=original.current_case_id,
            annotations=submissions,
        ),
        source="json_import",
    )
    validate_annotation_state(annotation_packet, corrected)
    _assert_exact_revision(original, corrected)
    replacement_lock = create_annotation_lock(annotation_packet, corrected)
    _write_json(CORRECTED_STATE_PATH, corrected.model_dump(mode="json"))
    write_annotation_lock(replacement_lock, CORRECTED_LOCK_PATH)
    manifest = {
        "schema_version": "t066-prediction-blind-correction-v2",
        "status": "corrected_and_relocked",
        "authorization": {
            "authorized_by": "scientific_lead",
            "authorized_on": "2026-10-05",
            "response": (
                "Case 12 and case 30 should have both been ordinary "
                "abbreviation_expansion with contiguous_shared evidence and "
                "text_alone context."
            ),
        },
        "exposure": {
            "predictions_exposed_before_correction": False,
            "correction_source": "user post-lock clarification",
            "exposure_status": "prediction_blind",
        },
        "original": {
            "state_path": ORIGINAL_STATE_PATH.relative_to(ROOT).as_posix(),
            "state_file_sha256": _sha256(ORIGINAL_STATE_PATH),
            "state_content_sha256": original_lock.annotation_state_sha256,
            "lock_path": ORIGINAL_LOCK_PATH.relative_to(ROOT).as_posix(),
            "lock_file_sha256": _sha256(ORIGINAL_LOCK_PATH),
            "locked_at": original_lock.locked_at,
        },
        "corrected": {
            "state_path": CORRECTED_STATE_PATH.relative_to(ROOT).as_posix(),
            "state_file_sha256": _sha256(CORRECTED_STATE_PATH),
            "state_content_sha256": replacement_lock.annotation_state_sha256,
            "lock_path": CORRECTED_LOCK_PATH.relative_to(ROOT).as_posix(),
            "lock_file_sha256": _sha256(CORRECTED_LOCK_PATH),
            "locked_at": replacement_lock.locked_at,
        },
        "changes": sorted(changes, key=lambda item: int(item["case_number"])),
        "invariants": {
            "original_files_unchanged": True,
            "prior_revision_history_preserved": True,
            "unrelated_cases_unchanged": True,
            "unrelated_relations_unchanged": True,
            "span_endpoints_unchanged": True,
            "packet_identity_unchanged": True,
        },
    }
    _write_json(MANIFEST_PATH, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
