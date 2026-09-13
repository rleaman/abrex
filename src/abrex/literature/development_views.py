"""Freeze T057 development views from the assisted T052 adjudication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.literature.review_models import (
    AnnotationState,
    PairDecision,
    ReviewCase,
    ReviewPacket,
    ReviewSpan,
    fingerprint,
    validate_annotation_state,
    validate_packet_identity,
    validate_span,
)
from abrex.literature.review_readiness import review_readiness

POLICY_ID = "t057-strict-exact-pair-v1"
SCHEMA_VERSION = "t057-development-views-v1"


class Eligibility(BaseModel):
    """Policy result for one retained relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    disposition: Literal["strict", "diagnostic", "unresolved"]
    reason: str


class MechanicalCorrection(BaseModel):
    """A narrowly scoped, fail-closed repair found during acceptance review."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    correction_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    expected_short_form: ReviewSpan | None = None
    corrected_short_form: ReviewSpan | None = None
    expected_long_form: ReviewSpan | None = None
    corrected_long_form: ReviewSpan | None = None
    expected_evidence_spans: tuple[ReviewSpan, ...] | None = None
    corrected_evidence_spans: tuple[ReviewSpan, ...] | None = None

    @model_validator(mode="after")
    def complete_replacement_pairs(self) -> MechanicalCorrection:
        fields = (
            (self.expected_short_form, self.corrected_short_form, "short form"),
            (self.expected_long_form, self.corrected_long_form, "long form"),
            (
                self.expected_evidence_spans,
                self.corrected_evidence_spans,
                "evidence spans",
            ),
        )
        if not any(corrected is not None for _, corrected, _ in fields):
            raise ValueError("a mechanical correction must replace at least one field")
        for expected, corrected, label in fields:
            if (expected is None) != (corrected is None):
                raise ValueError(f"{label} requires both expected and corrected values")
        return self


class MechanicalCorrections(BaseModel):
    """Content-addressed acceptance corrections for one annotation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["t057-mechanical-corrections-v1"]
    source_annotations_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: str = Field(min_length=1)
    corrections: tuple[MechanicalCorrection, ...]

    @model_validator(mode="after")
    def unique_corrections(self) -> MechanicalCorrections:
        ids = [item.correction_id for item in self.corrections]
        if len(set(ids)) != len(ids):
            raise ValueError("mechanical correction IDs must be unique")
        return self


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relation_eligibility(pair: PairDecision) -> Eligibility:
    """Apply the frozen policy without inferring unset audit fields."""
    if pair.status == "incorrect":
        return Eligibility(disposition="diagnostic", reason="unsupported")
    if pair.status in {"unreviewed", "unsure"}:
        return Eligibility(disposition="unresolved", reason="unresolved_support")
    if pair.short_form is None or pair.long_form is None:
        return Eligibility(disposition="unresolved", reason="incomplete_exact_pair")
    if pair.relation_kind == "uncertain":
        return Eligibility(disposition="unresolved", reason="unresolved_relation_kind")
    if pair.relation_kind == "other_naming_or_code_relation":
        return Eligibility(disposition="diagnostic", reason="outside_strict_target")
    if pair.source_error:
        return Eligibility(disposition="diagnostic", reason="source_error")
    if pair.evidence_structure == "uncertain":
        return Eligibility(
            disposition="unresolved", reason="unresolved_evidence_structure"
        )
    if pair.evidence_structure == "discontinuous":
        return Eligibility(
            disposition="diagnostic", reason="not_representable_as_exact_pair"
        )
    if pair.context_requirement == "uncertain":
        return Eligibility(disposition="unresolved", reason="unresolved_context")
    if pair.context_requirement != "text_alone":
        return Eligibility(disposition="diagnostic", reason="requires_non_text_context")
    return Eligibility(disposition="strict", reason="eligible_strict_exact_pair")


def validate_relation_evidence(pair: PairDecision) -> None:
    """Reject overlapping fragments in a discontinuous relation."""
    if pair.evidence_structure != "discontinuous":
        return
    spans = [
        ("short form", pair.short_form),
        ("long form", pair.long_form),
        *(
            (f"evidence fragment {index}", span)
            for index, span in enumerate(pair.evidence_spans, start=1)
        ),
    ]
    present = [(label, span) for label, span in spans if span is not None]
    for index, (left_label, left) in enumerate(present):
        for right_label, right in present[index + 1 :]:
            if left.start < right.end and right.start < left.end:
                raise ValueError(
                    f"discontinuous {left_label} overlaps {right_label}: "
                    f"[{left.start}, {left.end}) and [{right.start}, {right.end})"
                )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _apply_correction(
    case: ReviewCase, pair: PairDecision, correction: MechanicalCorrection
) -> PairDecision:
    replacements: dict[str, object] = {}
    for field in ("short_form", "long_form", "evidence_spans"):
        expected = getattr(correction, f"expected_{field}")
        corrected = getattr(correction, f"corrected_{field}")
        if corrected is None:
            continue
        if getattr(pair, field) != expected:
            raise ValueError(
                f"correction {correction.correction_id} expected {field} does not "
                f"match {case.case_id}/{pair.decision_id}"
            )
        replacements[field] = corrected
    result = pair.model_copy(update=replacements)
    validate_span(result.short_form, case.text, "corrected short form")
    validate_span(result.long_form, case.text, "corrected long form")
    for span in result.evidence_spans:
        validate_span(span, case.text, "corrected evidence fragment")
    return result


def _relation_row(
    case: ReviewCase,
    pair: PairDecision,
    corrections: tuple[MechanicalCorrection, ...],
) -> dict[str, Any]:
    source_decision_sha256 = fingerprint(pair.model_dump(mode="json"))
    for correction in corrections:
        pair = _apply_correction(case, pair, correction)
    validate_span(pair.short_form, case.text, "short form")
    validate_span(pair.long_form, case.text, "long form")
    for span in pair.evidence_spans:
        validate_span(span, case.text, "evidence fragment")
    validate_relation_evidence(pair)
    eligibility = relation_eligibility(pair)
    return {
        "case_id": case.case_id,
        "decision_id": pair.decision_id,
        "suggestion_id": pair.suggestion_id,
        "status": pair.status,
        "origin": pair.origin,
        "short_form": pair.short_form.model_dump(mode="json")
        if pair.short_form
        else None,
        "long_form": pair.long_form.model_dump(mode="json") if pair.long_form else None,
        "relation_kind": pair.relation_kind,
        "evidence_structure": pair.evidence_structure,
        "context_requirement": pair.context_requirement,
        "evidence_spans": [
            span.model_dump(mode="json") for span in pair.evidence_spans
        ],
        "reconstructed_interpretation": (
            {"text": pair.interpretation, "label": "reconstructed"}
            if pair.interpretation
            else None
        ),
        "source_error": pair.source_error,
        "notes": pair.notes,
        "disposition": eligibility.disposition,
        "eligibility_reason": eligibility.reason,
        "source_decision_sha256": source_decision_sha256,
        "mechanical_corrections": [
            {"correction_id": item.correction_id, "reason": item.reason}
            for item in corrections
        ],
    }


def _case_row(
    case: ReviewCase,
    state: AnnotationState,
    corrections: dict[tuple[str, str], tuple[MechanicalCorrection, ...]],
    *,
    selected: bool,
) -> dict[str, Any]:
    annotation = state.annotations.get(case.case_id)
    if annotation is None:
        return {
            "case_id": case.case_id,
            "selected_for_challenge": selected,
            "metric_eligible": False,
            "eligibility_reasons": ["case_unreviewed"],
            "search_status": "not_searched",
            "relations": [],
        }
    rows = [
        _relation_row(
            case,
            pair,
            corrections.get((case.case_id, pair.decision_id), ()),
        )
        for pair in annotation.current.pairs
    ]
    reasons: list[str] = []
    if annotation.current.missed_definition != "none":
        reasons.append("passage_search_incomplete")
    if any(row["disposition"] == "unresolved" for row in rows):
        reasons.append("contains_unresolved_relation")
    return {
        "case_id": case.case_id,
        "article_id": case.article_id,
        "article_group_id": case.article_group_id,
        "arm": case.arm,
        "canonical_text_sha256": case.canonical_text_sha256,
        "selected_for_challenge": selected,
        "search_status": (
            "searched"
            if annotation.current.missed_definition == "none"
            else "incomplete"
        ),
        "metric_eligible": not reasons,
        "eligibility_reasons": reasons or ["eligible_complete_case"],
        "revision": annotation.revision,
        "relations": rows,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_development_views(
    packet_path: Path,
    baseline_annotations_path: Path,
    adjudicated_annotations_path: Path,
    accepted_corrections_path: Path,
    t053_inventory_path: Path,
    t053_audit_packet_path: Path,
    guideline_path: Path,
    scientific_model_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate inputs and materialize the immutable T057 evidence bundle."""
    packet = ReviewPacket.model_validate(_read_object(packet_path))
    validate_packet_identity(packet)
    baseline = AnnotationState.model_validate(_read_object(baseline_annotations_path))
    adjudicated = AnnotationState.model_validate(
        _read_object(adjudicated_annotations_path)
    )
    validate_annotation_state(packet, baseline)
    validate_annotation_state(packet, adjudicated)
    corrections_state = MechanicalCorrections.model_validate(
        _read_object(accepted_corrections_path)
    )
    adjudicated_sha256 = sha256_file(adjudicated_annotations_path)
    if corrections_state.source_annotations_sha256 != adjudicated_sha256:
        raise ValueError(
            "accepted corrections refer to a different adjudicated annotation file"
        )
    corrections: dict[tuple[str, str], list[MechanicalCorrection]] = {}
    for correction in corrections_state.corrections:
        corrections.setdefault((correction.case_id, correction.decision_id), []).append(
            correction
        )
    correction_map = {key: tuple(value) for key, value in corrections.items()}
    inventory = _read_object(t053_inventory_path)
    audit_packet = _read_object(t053_audit_packet_path)
    if audit_packet.get("inventory_sha256") != inventory.get("inventory_sha256"):
        raise ValueError("T053 inventory/audit packet identity mismatch")
    selected_case_ids = tuple(
        str(item["case_id"]) for item in inventory.get("selected_cases", [])
    )
    selected_ids = set(selected_case_ids)
    packet_ids = {case.case_id for case in packet.cases}
    if not selected_ids or not selected_ids <= packet_ids:
        raise ValueError("T053 challenge selection is empty or contains unknown cases")
    readiness = review_readiness(packet, adjudicated, selected_case_ids)

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_cases = [
        _case_row(
            case,
            adjudicated,
            correction_map,
            selected=case.case_id in selected_ids,
        )
        for case in packet.cases
    ]
    known_targets = {
        (case["case_id"], relation["decision_id"])
        for case in ledger_cases
        for relation in case["relations"]
    }
    unknown_targets = sorted(set(correction_map) - known_targets)
    if unknown_targets:
        raise ValueError(
            f"mechanical corrections target unknown decisions: {unknown_targets}"
        )
    ledger_relations = [
        relation for case in ledger_cases for relation in case["relations"]
    ]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "cases": ledger_cases,
        "counts": {
            "cases": len(ledger_cases),
            "challenge_cases": len(selected_ids),
            "relations": len(ledger_relations),
            "strict_relations": sum(
                row["disposition"] == "strict" for row in ledger_relations
            ),
            "diagnostic_relations": sum(
                row["disposition"] == "diagnostic" for row in ledger_relations
            ),
            "unresolved_relations": sum(
                row["disposition"] == "unresolved" for row in ledger_relations
            ),
            "metric_eligible_cases": sum(
                bool(case["metric_eligible"]) for case in ledger_cases
            ),
        },
    }
    ledger["content_sha256"] = fingerprint(ledger)
    _write_json(output_dir / "eligibility-ledger.json", ledger)

    challenge = [case for case in ledger_cases if case["selected_for_challenge"]]
    strict_cases = []
    for case in challenge:
        strict_cases.append(
            {
                key: case[key]
                for key in (
                    "case_id",
                    "article_id",
                    "article_group_id",
                    "arm",
                    "canonical_text_sha256",
                    "metric_eligible",
                    "eligibility_reasons",
                )
            }
            | {
                "exact_pairs": [
                    {
                        "decision_id": row["decision_id"],
                        "short_form": row["short_form"],
                        "long_form": row["long_form"],
                    }
                    for row in case["relations"]
                    if row["disposition"] == "strict"
                ]
            }
        )
    strict_view = {
        "schema_version": SCHEMA_VERSION,
        "view_id": POLICY_ID,
        "status": "frozen" if readiness.complete else "human_review_incomplete",
        "ordinary_metrics_authorized": readiness.complete,
        "metric": "exact_pair",
        "offset_semantics": "half-open Unicode code-point intervals",
        "prediction_policy": {
            "in_scope_complete_case": "unmatched predictions count as false positives",
            "explicit_outside_target": "classify and report outside_strict_target",
            "incomplete_or_unresolved_case": (
                "do not form ordinary precision/recall denominators"
            ),
        },
        "cases": strict_cases,
    }
    strict_view["content_sha256"] = fingerprint(strict_view)
    _write_json(output_dir / "strict-exact-pair-development.json", strict_view)

    diagnostic_view = {
        "schema_version": SCHEMA_VERSION,
        "view_id": "t057-diagnostic-grounding-v1",
        "metric_eligible": False,
        "purpose": (
            "preserve broader, unsupported, unresolved, and unrepresentable evidence"
        ),
        "cases": challenge,
    }
    diagnostic_view["content_sha256"] = fingerprint(diagnostic_view)
    _write_json(output_dir / "diagnostic-development.json", diagnostic_view)

    baseline_pairs = sum(
        len(item.current.pairs) for item in baseline.annotations.values()
    )
    adjudicated_pairs = sum(
        len(item.current.pairs) for item in adjudicated.annotations.values()
    )
    repository_root = packet_path.resolve().parents[2]

    def source_name(path: Path) -> str:
        try:
            return path.resolve().relative_to(repository_root).as_posix()
        except ValueError:
            return str(path.resolve())

    manifest: dict[str, Any] = {
        "schema_version": "abrex-evidence-bundle-v1",
        "bundle_id": (
            "T057-development-guidelines-v1"
            if readiness.complete
            else "T057-development-progress-v1"
        ),
        "status": "frozen" if readiness.complete else "human_review_incomplete",
        "materialized_date": "2026-09-13",
        "policy_id": POLICY_ID,
        "provenance": {
            "reviewer_role": "user scientific lead",
            "assisted_exposure": True,
            "reviewer_identity_limitation": "legacy T052 state records no reviewer ID",
            "t052_packet_id": packet.packet_id,
            "t052_packet_content_sha256": packet.content_sha256,
        },
        "sources": {
            "packet": {
                "path": source_name(packet_path),
                "sha256": sha256_file(packet_path),
            },
            "baseline_annotations": {
                "path": source_name(baseline_annotations_path),
                "sha256": sha256_file(baseline_annotations_path),
                "relations": baseline_pairs,
            },
            "user_adjudication": {
                "path": source_name(adjudicated_annotations_path),
                "sha256": sha256_file(adjudicated_annotations_path),
                "relations": adjudicated_pairs,
            },
            "accepted_mechanical_corrections": {
                "path": source_name(accepted_corrections_path),
                "sha256": sha256_file(accepted_corrections_path),
                "source_annotations_sha256": (
                    corrections_state.source_annotations_sha256
                ),
                "corrections": len(corrections_state.corrections),
                "authority": corrections_state.authority,
            },
            "t053_inventory": {
                "path": source_name(t053_inventory_path),
                "sha256": sha256_file(t053_inventory_path),
            },
            "t053_audit_packet": {
                "path": source_name(t053_audit_packet_path),
                "sha256": sha256_file(t053_audit_packet_path),
            },
        },
        "documents": {
            "guideline": {
                "path": source_name(guideline_path),
                "sha256": sha256_file(guideline_path),
            },
            "scientific_model": {
                "path": source_name(scientific_model_path),
                "sha256": sha256_file(scientific_model_path),
            },
        },
        "outputs": {},
        "counts": ledger["counts"],
        "human_review": {
            "complete": readiness.complete,
            "required_cases": readiness.required_cases,
            "complete_cases": readiness.complete_cases,
            "remaining_cases": readiness.remaining_cases,
            "remaining_items": readiness.remaining_items,
        },
        "limitations": [
            "assisted development evidence; not independent gold",
            "diagnostically selected T052 material; no population estimate",
            "unresolved relations and incomplete cases are outside scored claims",
            "no relaxed metric is defined by this bundle",
            (
                "one source-error relation preserves the literal printed text; "
                "an intended scientific correction was not inferred"
            ),
        ],
    }
    for name in (
        "eligibility-ledger.json",
        "strict-exact-pair-development.json",
        "diagnostic-development.json",
    ):
        path = output_dir / name
        manifest["outputs"][name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    manifest["content_sha256"] = fingerprint(manifest)
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


__all__ = [
    "POLICY_ID",
    "SCHEMA_VERSION",
    "Eligibility",
    "MechanicalCorrection",
    "MechanicalCorrections",
    "build_development_views",
    "relation_eligibility",
    "validate_relation_evidence",
]
