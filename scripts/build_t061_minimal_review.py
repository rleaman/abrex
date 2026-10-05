"""Reduce T061 to judgments not settled by existing development evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from abrex.literature.review_interchange import (
    read_annotation_state,
    write_annotation_state,
)
from abrex.literature.review_models import (
    AnnotationState,
    AnnotationSubmission,
    CaseSubmission,
    DecisionSnapshot,
    PairDecision,
    ReviewPacket,
    ReviewSelection,
    apply_submission,
    empty_annotation_state,
    fingerprint,
    packet_identity_payload,
)
from abrex.literature.review_packet import read_review_packet
from abrex.literature.review_readiness import review_readiness

ROOT = Path(__file__).parents[1]
SOURCE_PACKET_PATH = ROOT / "evidence/T060/review-packet-split-v2.json"
SOURCE_STATE_PATH = ROOT / "evidence/T060/review-packet-split-v2.annotations.json"
T057_PATH = ROOT / "evidence/T057/diagnostic-development.json"
OUTPUT_DIR = ROOT / "evidence/T061"
OUTPUT_PACKET_PATH = OUTPUT_DIR / "review-packet-minimal.json"
OUTPUT_STATE_PATH = OUTPUT_DIR / "review-packet-minimal.annotations.json"
TRIAGE_PATH = OUTPUT_DIR / "triage.json"

TARGET_SUGGESTION_ID = "suggestion-t060-f2a15a432b13ea25f2b0"


@dataclass(frozen=True)
class FrozenResolution:
    reason_code: str
    explanation: str
    reference_decision_ids: tuple[str, ...] = ()


# These are not substitute human judgments. Each item is already determined by
# a frozen T057 decision/search or by the exact-boundary rule. Keeping this map
# explicit makes the queue reduction reviewable and prevents silent filtering.
FROZEN_RESOLUTIONS: dict[str, FrozenResolution] = {
    "suggestion-t060-8537002bc6984603273e": FrozenResolution(
        "component_substring_not_accepted_short_form",
        "T057 accepted the complete short form LDL-PL/LDL-apoB, not LDL.",
        ("added-d9a97ba8-d461-4d29-aaa3-c4afafae08c0",),
    ),
    "suggestion-t060-93555c53ac11de5500be": FrozenResolution(
        "endpoint_role_conflict",
        "T057 accepted VLDL-PL as the short form in a different exact pair.",
        ("decision-suggestion-dca419a96f7d31ee",),
    ),
    "suggestion-t060-eb27857e8b4ac2846239": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 fixed the exact VLDL-PL long form as phospholipids in total VLDL.",
        ("decision-suggestion-dca419a96f7d31ee",),
    ),
    "suggestion-t060-e23145f4b8adcfb4a171": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 fixed the exact VLDL-PL long form without the leading conjunction.",
        ("decision-suggestion-dca419a96f7d31ee",),
    ),
    "suggestion-t060-9a56370277bb614067d1": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 fixed the exact VLDL2-PL long form as VLDL subclass 2.",
        ("added-28b4484f-ef7e-4999-9f99-844bc96d14ac",),
    ),
    "suggestion-t060-4091883dd60c93694642": FrozenResolution(
        "searched_passage_component_inference",
        "The searched T057 passage did not accept an inferred VLDL component mapping.",
    ),
    "suggestion-t060-cc97746e99e7ea645415": FrozenResolution(
        "component_substring_not_accepted_short_form",
        "T057 accepted the complete short form LDL-FC/LDL-apoB, not LDL.",
        ("added-39186c1d-ad2f-4df5-8022-4da0db6e14e2",),
    ),
    "suggestion-t060-33c9ec128709eeb495b4": FrozenResolution(
        "searched_passage_component_inference",
        "The searched T057 passage did not accept an inferred VLDL component mapping.",
    ),
    "suggestion-t060-2c4c7dc6d5bcce010acc": FrozenResolution(
        "component_substring_not_accepted_short_form",
        "T057 accepted the complete short form IDL-C/IDL-apoB, not IDL.",
        ("added-89628d10-50a1-40f6-9fc3-c25a8f028071",),
    ),
    "suggestion-t060-59ff3f630a8e3aa5d351": FrozenResolution(
        "endpoint_role_conflict",
        "T057 accepted HDL-PL as the short form in a different exact pair.",
        ("added-b9f8650f-a2b3-4fba-ad31-88c09b33a7f3",),
    ),
    "suggestion-t060-16130f33ccbe92e68d22": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 retained the printed second HDL1-PL occurrence as diagnostic "
        "evidence with long form 2, not the mixed boundary proposed here.",
        (
            "decision-suggestion-09e5ad7e87e8434a",
            "added-11d0b66e-8b2a-44dc-9bd9-5792424c7954",
        ),
    ),
    "suggestion-t060-abec72641ca80b64934c": FrozenResolution(
        "endpoint_role_conflict",
        "T057 accepted HDL-apoA-I as the short form in a different exact pair.",
        ("decision-suggestion-7d1d3fb29d59c32c",),
    ),
    "suggestion-t060-f00380295638e294a289": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 fixed the exact HDL-apoA-I long form as apoA-I in the total HDL.",
        ("decision-suggestion-7d1d3fb29d59c32c",),
    ),
    "suggestion-t060-1c9bdf5b506a3b745b3c": FrozenResolution(
        "incomplete_long_form_boundary",
        "class B type 1 is a strict suffix of the adjacent complete phrase "
        "scavenger receptor class B type 1; the exact-boundary policy does not "
        "require a second scientific judgment.",
    ),
    "suggestion-t060-5644d54f8aada4910ba8": FrozenResolution(
        "long_form_boundary_conflict",
        "T057 retained D-group as a diagnostic relation with exact long-form "
        "evidence decapitation.",
        ("decision-suggestion-82605f4667733c5a",),
    ),
    "suggestion-t060-bb2b51815a617c6c6f12": FrozenResolution(
        "prior_relation_conflict",
        "T057 retained N-group as a diagnostic relation with long-form evidence "
        "nembutal.",
        ("added-1f44ab2e-7246-4eb4-aaf9-ac7b08ce1f0d",),
    ),
    "suggestion-t060-e9a853fb1dcce5562db1": FrozenResolution(
        "prior_relation_conflict",
        "T057 retained N-group as a diagnostic relation with long-form evidence "
        "nembutal.",
        ("added-1f44ab2e-7246-4eb4-aaf9-ac7b08ce1f0d",),
    ),
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_t057() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    payload = json.loads(T057_PATH.read_text(encoding="utf-8"))
    cases = {
        str(case["case_id"]): case
        for case in payload["cases"]
        if isinstance(case, dict)
    }
    return payload, cases


def _minimal_packet(source: ReviewPacket) -> ReviewPacket:
    matches = [
        (case, suggestion)
        for case in source.cases
        for suggestion in case.suggestions
        if suggestion.suggestion_id == TARGET_SUGGESTION_ID
    ]
    if len(matches) != 1:
        raise ValueError("the one unresolved T061 suggestion was not found uniquely")
    source_case, suggestion = matches[0]
    review_case = source_case.model_copy(
        update={
            "suggestions": (suggestion,),
            "selection_reason": (
                "Only exact-pair proposal not already resolved by completed T061 "
                "work, frozen T057 evidence, or the frozen exact-boundary policy."
            ),
        }
    )
    selection = ReviewSelection(
        targets={"user_judgment_required": 1},
        denominators={
            "source_cases": len(source.cases),
            "source_suggestions": sum(len(case.suggestions) for case in source.cases),
            "user_judgment_required": 1,
        },
        selected={"user_judgment_required": 1},
        shortages={"user_judgment_required": 0},
        arm_counts={review_case.arm: 1},
        per_article_cap=1,
    )
    provisional = ReviewPacket(
        packet_id="pending",
        content_sha256="0" * 64,
        source_manifest_sha256=source.source_manifest_sha256,
        source_run_id="t060-development-comparison:t061-minimal-v1",
        seed=source.seed,
        cases=(review_case,),
        selection=selection,
    )
    digest = fingerprint(packet_identity_payload(provisional))
    return provisional.model_copy(
        update={
            "packet_id": f"t052-{digest[:20]}",
            "content_sha256": digest,
        }
    )


def _prefilled_state(packet: ReviewPacket) -> AnnotationState:
    case = packet.cases[0]
    suggestion = case.suggestions[0]
    snapshot = DecisionSnapshot(
        pairs=(
            PairDecision(
                decision_id=f"decision-{suggestion.suggestion_id}",
                suggestion_id=suggestion.suggestion_id,
                proposal_kind=suggestion.proposal_kind,
                status="unreviewed",
                short_form=suggestion.short_form,
                long_form=suggestion.long_form,
                origin="assisted",
                notes=(
                    "Mechanical prefill only: exact spans and structural fields; "
                    "support remains the reviewer's decision."
                ),
                relation_kind="abbreviation_expansion",
                evidence_structure="contiguous_shared",
                context_requirement="text_alone",
            ),
        ),
        missed_definition="none",
        notes=(
            "Whole-passage search reused from frozen T057 revision 2; this "
            "minimal supplement asks only about the new exact pair."
        ),
    )
    submission = AnnotationSubmission(
        packet_id=packet.packet_id,
        packet_content_sha256=packet.content_sha256,
        current_case_id=case.case_id,
        annotations={
            case.case_id: CaseSubmission(expected_revision=0, decision=snapshot)
        },
    )
    return apply_submission(
        packet, empty_annotation_state(packet), submission, source="json_import"
    )


def _triage(
    source: ReviewPacket,
    packet: ReviewPacket,
) -> dict[str, object]:
    source_state = read_annotation_state(source, SOURCE_STATE_PATH)
    readiness = review_readiness(
        source, source_state, tuple(case.case_id for case in source.cases)
    )
    t057_payload, t057_cases = _load_t057()
    t057_decisions: dict[str, dict[str, object]] = {}
    for t057_case_value in t057_cases.values():
        relations = t057_case_value.get("relations")
        if not isinstance(relations, list):
            raise ValueError("T057 case relations must be a list")
        for relation in relations:
            if not isinstance(relation, dict) or "decision_id" not in relation:
                raise ValueError("T057 relations must be identified objects")
            t057_decisions[str(relation["decision_id"])] = relation
    for resolution in FROZEN_RESOLUTIONS.values():
        missing = set(resolution.reference_decision_ids) - set(t057_decisions)
        if missing:
            raise ValueError(f"unknown frozen T057 decision references: {missing}")

    items: list[dict[str, object]] = []
    counts = {
        "already_reviewed_by_user": 0,
        "resolved_by_frozen_evidence_or_policy": 0,
        "requires_user_judgment": 0,
    }
    for case in source.cases:
        annotation = source_state.annotations.get(case.case_id)
        decisions = (
            {
                pair.suggestion_id: pair
                for pair in annotation.current.pairs
                if pair.suggestion_id is not None
            }
            if annotation
            else {}
        )
        t057_case = t057_cases.get(case.case_id)
        for suggestion in case.suggestions:
            base: dict[str, object] = {
                "case_id": case.case_id,
                "suggestion_id": suggestion.suggestion_id,
                "short_form": suggestion.short_form.model_dump(mode="json")
                if suggestion.short_form
                else None,
                "long_form": suggestion.long_form.model_dump(mode="json")
                if suggestion.long_form
                else None,
                "method_ids": list(suggestion.method_ids),
            }
            if suggestion.suggestion_id in decisions:
                decision = decisions[suggestion.suggestion_id]
                counts["already_reviewed_by_user"] += 1
                base.update(
                    {
                        "disposition": "already_reviewed_by_user",
                        "requires_user": False,
                        "decision_status": decision.status,
                        "source_revision": annotation.revision if annotation else None,
                    }
                )
            elif suggestion.suggestion_id == TARGET_SUGGESTION_ID:
                counts["requires_user_judgment"] += 1
                base.update(
                    {
                        "disposition": "requires_user_judgment",
                        "requires_user": True,
                        "question": (
                            "Does this passage define SR-BI as scavenger receptor "
                            "class B type 1?"
                        ),
                    }
                )
            else:
                frozen_resolution = FROZEN_RESOLUTIONS.get(suggestion.suggestion_id)
                if frozen_resolution is None:
                    raise ValueError(
                        f"untriaged T061 suggestion {suggestion.suggestion_id}"
                    )
                if t057_case is None or t057_case.get("search_status") != "searched":
                    raise ValueError(
                        f"{case.case_id} lacks the required frozen searched status"
                    )
                counts["resolved_by_frozen_evidence_or_policy"] += 1
                base.update(
                    {
                        "disposition": "resolved_by_frozen_evidence_or_policy",
                        "requires_user": False,
                        "reason_code": frozen_resolution.reason_code,
                        "explanation": frozen_resolution.explanation,
                        "reference_decision_ids": list(
                            frozen_resolution.reference_decision_ids
                        ),
                    }
                )
            items.append(base)

    if counts != {
        "already_reviewed_by_user": 15,
        "resolved_by_frozen_evidence_or_policy": 17,
        "requires_user_judgment": 1,
    }:
        raise ValueError(f"unexpected T061 triage counts: {counts}")
    return {
        "schema_version": "t061-review-triage-v1",
        "purpose": (
            "Preserve completed T061 work and expose only scientific judgments "
            "not already settled by frozen development evidence or policy."
        ),
        "source_packet": {
            "path": "evidence/T060/review-packet-split-v2.json",
            "packet_id": source.packet_id,
            "content_sha256": source.content_sha256,
        },
        "source_annotations": {
            "path": "evidence/T060/review-packet-split-v2.annotations.json",
            "file_sha256": _file_sha256(SOURCE_STATE_PATH),
            "complete_cases": readiness.complete_cases,
            "required_cases": readiness.required_cases,
        },
        "frozen_t057": {
            "path": "evidence/T057/diagnostic-development.json",
            "file_sha256": _file_sha256(T057_PATH),
            "content_sha256": t057_payload.get("content_sha256"),
            "policy": "t057-strict-exact-pair-v1",
        },
        "minimal_packet": {
            "path": "evidence/T061/review-packet-minimal.json",
            "packet_id": packet.packet_id,
            "content_sha256": packet.content_sha256,
        },
        "counts": {**counts, "total": len(items)},
        "items": items,
    }


def main() -> int:
    source = read_review_packet(SOURCE_PACKET_PATH)
    packet = _minimal_packet(source)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PACKET_PATH.write_text(
        packet.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if OUTPUT_STATE_PATH.exists():
        read_annotation_state(packet, OUTPUT_STATE_PATH)
    else:
        write_annotation_state(_prefilled_state(packet), OUTPUT_STATE_PATH)
    triage = _triage(source, packet)
    TRIAGE_PATH.write_text(
        json.dumps(triage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "T061 minimized: 15 prior reviews preserved, 17 proposals resolved "
        "from frozen evidence/policy, 1 user judgment remains."
    )
    print(f"Packet: {OUTPUT_PACKET_PATH}")
    print(f"Working state: {OUTPUT_STATE_PATH}")
    print(f"Triage audit: {TRIAGE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
