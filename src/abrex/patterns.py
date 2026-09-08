"""Bounded contextual template induction over explicit weak evidence."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import Document, TextSpan
from abrex.evidence import EvidenceRecord


class PatternInductionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_characters: int = Field(default=60, ge=1, le=500)
    minimum_documents: int = Field(default=2, ge=1)
    minimum_pairs: int = Field(default=2, ge=1)
    maximum_template_length: int = Field(default=180, ge=20, le=1000)


@dataclass(frozen=True, slots=True)
class ContextTemplate:
    template: str
    direction: str

    def __post_init__(self) -> None:
        if not self.template.strip() or len(self.template) > 1000:
            raise ValueError("template is empty or exceeds safe bounds")
        if self.direction not in ("short_before_long", "long_before_short"):
            raise ValueError("unsupported template direction")

    def matches(self, context: str) -> bool:
        if self.template.count("<SF>") != 1 or self.template.count("<LF>") != 1:
            return False
        pattern = re.escape(self.template)
        pattern = pattern.replace(re.escape("<SF>"), r"\S{1,40}")
        pattern = pattern.replace(re.escape("<LF>"), r".{1,240}?")
        return re.fullmatch(pattern, context, flags=re.DOTALL) is not None


@dataclass(frozen=True, slots=True)
class InducedPattern:
    template: ContextTemplate
    distinct_documents: int
    distinct_pairs: int
    evidence_ids: tuple[str, ...]
    status: str


def extract_template(
    document: Document,
    short_form: TextSpan,
    long_form: TextSpan,
    *,
    context_characters: int = 60,
) -> ContextTemplate:
    """Replace exact forms with placeholders and retain bounded local context."""

    document.validate_span(short_form)
    document.validate_span(long_form)
    first, second = sorted(
        ((short_form, "<SF>"), (long_form, "<LF>")), key=lambda item: item[0].start
    )
    start = max(0, first[0].start - context_characters)
    end = min(len(document.text), second[0].end + context_characters)
    text = (
        document.text[start : first[0].start]
        + first[1]
        + document.text[first[0].end : second[0].start]
        + second[1]
        + document.text[second[0].end : end]
    )
    text = re.sub(r"\s+", " ", text).strip()
    direction = (
        "short_before_long"
        if short_form.start < long_form.start
        else "long_before_short"
    )
    return ContextTemplate(text, direction)


def induce_patterns(
    evidence: Iterable[EvidenceRecord],
    documents: dict[str, Document],
    config: PatternInductionConfig,
) -> tuple[InducedPattern, ...]:
    """Group positive evidence into literal templates without pair memorization."""

    groups: dict[ContextTemplate, list[EvidenceRecord]] = defaultdict(list)
    for record in evidence:
        if record.polarity != "positive" or record.document_id not in documents:
            continue
        template = extract_template(
            documents[record.document_id],
            record.short_form,
            record.long_form,
            context_characters=config.context_characters,
        )
        if len(template.template) <= config.maximum_template_length:
            groups[template].append(record)
    promoted: list[InducedPattern] = []
    for template, records in sorted(groups.items(), key=lambda item: item[0].template):
        document_count = len({record.document_id for record in records})
        pair_count = len({(record.short_form, record.long_form) for record in records})
        status = (
            "promoted"
            if document_count >= config.minimum_documents
            and pair_count >= config.minimum_pairs
            else "rejected_insufficient_support"
        )
        promoted.append(
            InducedPattern(
                template,
                document_count,
                pair_count,
                tuple(record.evidence_id for record in records),
                status,
            )
        )
    return tuple(promoted)


def validate_pattern(
    pattern: InducedPattern,
    evidence: Iterable[EvidenceRecord],
    documents: dict[str, Document],
) -> dict[str, int]:
    """Measure a promoted template on supplied held-out evidence."""

    records = [
        record
        for record in evidence
        if record.document_id in documents and record.polarity == "positive"
    ]
    matched = sum(
        pattern.template.matches(
            extract_template(
                documents[record.document_id], record.short_form, record.long_form
            ).template
        )
        for record in records
    )
    return {
        "held_out_positive_records": len(records),
        "matched_records": matched,
        "missed_records": len(records) - matched,
    }


__all__ = [
    "ContextTemplate",
    "InducedPattern",
    "PatternInductionConfig",
    "extract_template",
    "induce_patterns",
    "validate_pattern",
]
