"""Build the bounded, source-traceable T053 audit inventory."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from abrex.literature.review_models import (
    AnnotationState,
    ReviewPacket,
    fingerprint,
    validate_annotation_state,
    validate_packet_identity,
)

SCHEMA_VERSION = "t053-audit-inventory-v1"
SEED = 20260908


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _current_decisions(
    packet: ReviewPacket, state: AnnotationState
) -> list[dict[str, Any]]:
    cases = {case.case_id: case for case in packet.cases}
    decisions: list[dict[str, Any]] = []
    for case_id, annotation in state.annotations.items():
        case = cases[case_id]
        for pair in annotation.current.pairs:
            decisions.append(
                {
                    "case_id": case_id,
                    "inventory_id": case.inventory_id,
                    "article_id": case.article_id,
                    "article_group_id": case.article_group_id,
                    "decision_id": pair.decision_id,
                    "suggestion_id": pair.suggestion_id,
                    "status": pair.status,
                    "origin": pair.origin,
                    "proposal_kind": pair.proposal_kind,
                    "short_form": pair.short_form.model_dump(mode="json")
                    if pair.short_form
                    else None,
                    "long_form": pair.long_form.model_dump(mode="json")
                    if pair.long_form
                    else None,
                    "notes": pair.notes,
                }
            )
    return decisions


def _selection(
    packet: ReviewPacket, state: AnnotationState, seed: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_case = {case.case_id: case for case in packet.cases}
    current = _current_decisions(packet, state)
    reasons: dict[str, set[str]] = {case.case_id: set() for case in packet.cases}
    for decision in current:
        if decision["origin"] == "added":
            reasons[decision["case_id"]].add("added_pair")
        if decision["origin"] == "corrected":
            reasons[decision["case_id"]].add("corrected_suggestion")
        if decision["status"] == "incorrect":
            reasons[decision["case_id"]].add("rejected_suggestion")
    targeted_ids = [case.case_id for case in packet.cases if reasons[case.case_id]]
    controls = [
        case
        for case in packet.cases
        if not reasons[case.case_id]
        and (annotation := state.annotations.get(case.case_id)) is not None
        and annotation.current.missed_definition == "none"
        and annotation.current.pairs
        and all(
            pair.origin == "assisted" and pair.status == "correct"
            for pair in annotation.current.pairs
        )
    ]
    # A seeded shuffle, followed by one-per-article-group selection, maximizes
    # diversity while remaining replayable across Python versions.
    rng = random.Random(seed)
    controls = sorted(controls, key=lambda case: case.case_id)
    rng.shuffle(controls)
    chosen_controls: list[str] = []
    groups: set[str] = set()
    for case in controls:
        if case.article_group_id not in groups and len(chosen_controls) < 8:
            chosen_controls.append(case.case_id)
            groups.add(case.article_group_id)
    if len(chosen_controls) < 8:
        for case in controls:
            if case.case_id not in chosen_controls and len(chosen_controls) < 8:
                chosen_controls.append(case.case_id)
    selected_ids = targeted_ids + chosen_controls
    selected = []
    for case_id in selected_ids:
        case = by_case[case_id]
        selected.append(
            {
                "case_id": case_id,
                "inventory_id": case.inventory_id,
                "article_id": case.article_id,
                "article_group_id": case.article_group_id,
                "arm": case.arm,
                "category": case.category,
                "selection_reasons": sorted(reasons[case_id])
                or ["unchanged_accepted_control"],
                "passage_start": case.passage_start,
                "passage_end": case.passage_end,
                "canonical_text_sha256": case.canonical_text_sha256,
                "current_decision_ids": [
                    item["decision_id"]
                    for item in current
                    if item["case_id"] == case_id
                ],
            }
        )
    metadata = {
        "targeted_case_count": len(targeted_ids),
        "targeted_denominator_cases": len(packet.cases),
        "control_candidate_denominator": len(controls),
        "control_target": 8,
        "control_selected": len(chosen_controls),
        "control_shortage": max(0, 8 - len(chosen_controls)),
        "control_article_groups": len(groups),
        "seed": seed,
        "deduplication": "case level; all applicable reasons retained",
    }
    return selected, metadata


def _question(
    case: Any, question_id: str, prompt: str, needles: tuple[str, ...]
) -> dict[str, Any]:
    refs = []
    for needle in needles:
        start = case.text.find(needle)
        if start >= 0:
            refs.append(
                {
                    "needle": needle,
                    "start": start,
                    "end": start + len(needle),
                    "text": needle,
                }
            )
    if not refs:
        raise ValueError(
            f"question {question_id} has no source trace in {case.case_id}"
        )
    return {
        "question_id": question_id,
        "case_id": case.case_id,
        "article_id": case.article_id,
        "prompt": prompt,
        "source_references": refs,
    }


def build_audit_inventory(
    packet_path: Path,
    annotations_path: Path,
    bundle_manifest_path: Path,
    output_dir: Path,
    *,
    seed: int = SEED,
) -> dict[str, Any]:
    packet = ReviewPacket.model_validate(_read(packet_path))
    validate_packet_identity(packet)
    state = AnnotationState.model_validate(_read(annotations_path))
    validate_annotation_state(packet, state)
    bundle = _read(bundle_manifest_path)
    bundle_dir = bundle_manifest_path.parent
    for item in bundle.get("files", []):
        if not isinstance(item, dict):
            raise ValueError("bundle manifest files must be objects")
        path = bundle_dir / str(item["path"])
        if _sha256(path) != item["sha256"]:
            raise ValueError(f"frozen bundle hash mismatch: {path}")
    if _sha256(packet_path) != next(
        item["sha256"] for item in bundle["files"] if item["path"] == packet_path.name
    ):
        raise ValueError("packet hash does not match frozen bundle manifest")
    if packet.source_manifest_sha256 != bundle["packet"]["source_manifest_sha256"]:
        raise ValueError("packet/source manifest identity mismatch")
    selected, selection = _selection(packet, state, seed)
    by_id = {case.case_id: case for case in packet.cases}
    questions = [
        _question(
            by_id["case-474f458c08d3bd7a9bf8"],
            "q-2a",
            (
                "Is the 2A relation intended to be agonist-bound A, and what "
                "relation kind should it represent?"
            ),
            ("agonist-bound A(2A) adenosine receptor (AR)",),
        ),
        _question(
            by_id["case-8deab3bbe026a86e6b5c"],
            "q-hdl-apoai",
            (
                "Are the HDL2-apoA-I and HDL4-apoA-I occurrences supported "
                "definitions that were not recorded as current decisions?"
            ),
            ("HDL2-apoA-I", "HDL4-apoA-I"),
        ),
        _question(
            by_id["case-06c9ebb850190d98a90b"],
            "q-tcpo",
            (
                "Should shared material and trailing ‘tensions’ be treated as "
                "evidence for tcPO2/tcPCO2, or as separate components?"
            ),
            ("Transcutaneous oxygen (tcPO2) and carbon dioxide (tcPCO2) tensions",),
        ),
        _question(
            by_id["case-1a4f2e3443392fdca836"],
            "q-ratios",
            "Should ratio components be represented separately from the whole "
            "ratio definitions?",
            ("LDL-PL/LDL-apoB", "VLDL3-C, VLDL4-C"),
        ),
        _question(
            by_id["case-8deab3bbe026a86e6b5c"],
            "q-hdl1-typo",
            (
                "Is the repeated HDL1-PL text a source typo for HDL2-PL, and "
                "how should the source error be recorded?"
            ),
            ("subclasses 1 (HDL1-PL) and 2 (HDL1-PL)",),
        ),
        _question(
            by_id["case-1a4f2e3443392fdca836"],
            "q-vldl-mapping",
            (
                "Is VLDL3-C/VLDL4-C one long-form occurrence mapping to two "
                "short forms, or two separate definitions?"
            ),
            ("VLDL3-C, VLDL4-C",),
        ),
        _question(
            by_id["case-bb7cec40d4228dda23e5"],
            "q-d-group",
            (
                "Should D-group and the component mnemonics be represented as "
                "abbreviations, labels, or another relation kind?"
            ),
            ("D-group", "(C-group)", "(H-group)"),
        ),
    ]
    decisions = _current_decisions(packet, state)
    additions = [d for d in decisions if d["origin"] == "added"]
    all_cases = [
        {
            "case_id": case.case_id,
            "inventory_id": case.inventory_id,
            "article_id": case.article_id,
            "article_group_id": case.article_group_id,
            "arm": case.arm,
            "category": case.category,
            "source_kind": case.source_kind,
            "section_id": case.section_id,
            "passage_start": case.passage_start,
            "passage_end": case.passage_end,
            "canonical_text_sha256": case.canonical_text_sha256,
            "current_decision_count": sum(
                decision["case_id"] == case.case_id for decision in decisions
            ),
        }
        for case in packet.cases
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "task": "T053",
        "source": {
            "packet": str(packet_path),
            "annotations": str(annotations_path),
            "bundle_manifest": str(bundle_manifest_path),
            "packet_sha256": _sha256(packet_path),
            "annotations_sha256": _sha256(annotations_path),
            "bundle_manifest_sha256": _sha256(bundle_manifest_path),
            "packet_id": packet.packet_id,
            "packet_content_sha256": packet.content_sha256,
            "source_manifest_sha256": packet.source_manifest_sha256,
        },
        "counts": {
            "cases": len(packet.cases),
            "annotated_cases": len(state.annotations),
            "current_decisions": len(decisions),
            "additions": len(additions),
            "corrected_origins": sum(d["origin"] == "corrected" for d in decisions),
            "rejections": sum(d["status"] == "incorrect" for d in decisions),
        },
        "all_cases": all_cases,
        "selection": selection,
        "selected_cases": selected,
        "current_decisions": decisions,
        "additions_by_article_and_passage": [
            {
                "article_id": case.article_id,
                "case_id": case.case_id,
                "passage_start": case.passage_start,
                "passage_end": case.passage_end,
                "addition_count": sum(d["case_id"] == case.case_id for d in additions),
            }
            for case in packet.cases
            if any(d["case_id"] == case.case_id for d in additions)
        ],
        "questions": questions,
        "scientific_status": (
            "questions for human audit; no automatic corrections or adjudicated facts"
        ),
    }
    inventory["inventory_sha256"] = fingerprint(inventory)
    (output_dir / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    audit_packet = {
        "schema_version": "t053-audit-packet-v1",
        "inventory_sha256": inventory["inventory_sha256"],
        "source": inventory["source"],
        "selection": selection,
        "cases": [by_id[item["case_id"]].model_dump(mode="json") for item in selected],
        "questions": questions,
    }
    audit_packet["packet_sha256"] = fingerprint(audit_packet)
    (output_dir / "audit-packet.json").write_text(
        json.dumps(audit_packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# T053 audit questions",
        "",
        "These are questions for human review, not automatic corrections or "
        "adjudicated facts.",
        "",
        "## Questions",
        "",
    ]
    for item in questions:
        refs = ", ".join(
            f"{ref['text']!r} [{ref['start']}, {ref['end']})"
            for ref in item["source_references"]
        )
        lines.append(
            f"- **{item['question_id']} — case {item['case_id']}**: "
            f"{item['prompt']} Source text: {refs}."
        )
    lines += [
        "",
        "The full reviewed passages and all current decisions are in "
        "`audit-packet.json` and `inventory.json`.",
        "",
        "Reproduction:",
        "",
        "```powershell",
        ".\\env313\\Scripts\\python.exe scripts\\build_t053_audit_inventory.py",
        "```",
        "",
    ]
    (output_dir / "question-sheet.md").write_text("\n".join(lines), encoding="utf-8")
    return inventory


__all__ = ["SCHEMA_VERSION", "SEED", "build_audit_inventory"]
