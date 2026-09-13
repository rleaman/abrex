"""Human-readable completeness checks for the T057 policy review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from abrex.literature.review_models import (
    AnnotationState,
    DecisionSnapshot,
    PairDecision,
    ReviewCase,
    ReviewPacket,
)

IssueKind = Literal[
    "passage_search",
    "support",
    "relation_kind",
    "evidence_structure",
    "evidence_fragments",
    "context_requirement",
    "missing_suggestion",
]


class ReadinessIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    decision_id: str | None = None
    kind: IssueKind
    message: str


class CaseReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    title: str
    complete: bool
    issues: tuple[ReadinessIssue, ...]


class ReviewReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    complete: bool
    required_cases: int
    complete_cases: int
    remaining_cases: int
    remaining_items: int
    cases: tuple[CaseReadiness, ...]


def pair_readiness_issues(case_id: str, pair: PairDecision) -> list[ReadinessIssue]:
    issues: list[ReadinessIssue] = []

    def add(kind: IssueKind, message: str) -> None:
        issues.append(
            ReadinessIssue(
                case_id=case_id,
                decision_id=pair.decision_id,
                kind=kind,
                message=message,
            )
        )

    if pair.status in {"unreviewed", "unsure"}:
        add("support", "Choose Supported or Unsupported.")
        return issues
    if pair.status == "incorrect":
        return issues
    if pair.relation_kind == "uncertain":
        add(
            "relation_kind",
            "Choose Abbreviation expansion or Other naming/code relation.",
        )
    if pair.evidence_structure == "uncertain":
        add("evidence_structure", "Choose Contiguous/shared or Discontinuous.")
    elif pair.evidence_structure == "discontinuous" and not pair.evidence_spans:
        add(
            "evidence_fragments",
            "Add the exact additional fragment(s) used by this discontinuous relation.",
        )
    if pair.context_requirement == "uncertain":
        add(
            "context_requirement",
            "Choose Text alone, Document structure, or Image.",
        )
    return issues


def case_readiness(
    case: ReviewCase, snapshot: DecisionSnapshot | None
) -> CaseReadiness:
    issues: list[ReadinessIssue] = []
    if snapshot is None or snapshot.missed_definition != "none":
        issues.append(
            ReadinessIssue(
                case_id=case.case_id,
                kind="passage_search",
                message="Search the whole passage, then choose Searched.",
            )
        )
    pairs = snapshot.pairs if snapshot else ()
    reviewed_suggestions = {pair.suggestion_id for pair in pairs if pair.suggestion_id}
    for suggestion in case.suggestions:
        if suggestion.suggestion_id not in reviewed_suggestions:
            issues.append(
                ReadinessIssue(
                    case_id=case.case_id,
                    decision_id=f"decision-{suggestion.suggestion_id}",
                    kind="missing_suggestion",
                    message="Review the packet suggestion as Supported or Unsupported.",
                )
            )
    for pair in pairs:
        issues.extend(pair_readiness_issues(case.case_id, pair))
    return CaseReadiness(
        case_id=case.case_id,
        title=case.title,
        complete=not issues,
        issues=tuple(issues),
    )


def review_readiness(
    packet: ReviewPacket,
    state: AnnotationState,
    required_case_ids: tuple[str, ...],
) -> ReviewReadiness:
    by_id = {case.case_id: case for case in packet.cases}
    unknown = sorted(set(required_case_ids) - set(by_id))
    if unknown:
        raise ValueError(f"unknown required case IDs: {unknown}")
    snapshots = {
        case_id: annotation.current for case_id, annotation in state.annotations.items()
    }
    cases = tuple(
        case_readiness(by_id[case_id], snapshots.get(case_id))
        for case_id in required_case_ids
    )
    complete_cases = sum(case.complete for case in cases)
    return ReviewReadiness(
        complete=complete_cases == len(cases),
        required_cases=len(cases),
        complete_cases=complete_cases,
        remaining_cases=len(cases) - complete_cases,
        remaining_items=sum(len(case.issues) for case in cases),
        cases=cases,
    )


def required_case_ids_from_t053(path: Path) -> tuple[str, ...]:
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = value.get("selected_cases") if isinstance(value, dict) else None
    if not isinstance(selected, list) or not selected:
        raise ValueError("T053 inventory has no selected cases")
    ids = tuple(
        str(item.get("case_id", "")) for item in selected if isinstance(item, dict)
    )
    if not all(ids) or len(ids) != len(selected) or len(set(ids)) != len(ids):
        raise ValueError("T053 selected case IDs are missing or duplicated")
    return ids


def readiness_text(value: ReviewReadiness, working_file: Path) -> str:
    lines = [
        f"Working file: {working_file}",
        (
            f"Progress: {value.complete_cases}/{value.required_cases} passages "
            "complete; "
            f"{value.remaining_items} required decisions remain."
        ),
    ]
    if value.complete:
        lines.append("READY: the required T057 policy review is complete.")
    else:
        lines.append(
            "NOT READY: reopen the passages below with the Needs attention filter."
        )
        for case in value.cases:
            if not case.complete:
                lines.append(f"- {case.title} ({len(case.issues)} items)")
    return "\n".join(lines)


__all__ = [
    "CaseReadiness",
    "ReadinessIssue",
    "ReviewReadiness",
    "case_readiness",
    "pair_readiness_issues",
    "readiness_text",
    "required_case_ids_from_t053",
    "review_readiness",
]
