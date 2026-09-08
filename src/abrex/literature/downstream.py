"""Narrow downstream adapter and impact-comparison contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from abrex.literature.mentions import MentionLink
from abrex.literature.models import ArticleDocument


@dataclass(frozen=True, slots=True)
class DownstreamEntity:
    """Stable downstream entity key with its originating mention."""

    entity_id: str
    mention: MentionLink


class DownstreamAdapter(Protocol):
    """User-pipeline boundary; non-abbreviation settings remain caller-owned."""

    identity: str
    version: str

    def extract(
        self, source: ArticleDocument, mentions: Sequence[MentionLink]
    ) -> Sequence[DownstreamEntity]:
        """Extract entities from unchanged source text and chosen mentions."""


@dataclass(frozen=True, slots=True)
class DownstreamImpactResult:
    """Separate baseline/propagated entity counts and exact-set metrics."""

    baseline_count: int
    propagated_count: int
    introduced_entity_ids: tuple[str, ...]
    removed_entity_ids: tuple[str, ...]
    precision: float | None
    recall: float | None
    false_expansions: int


def compare_downstream_entities(
    gold_entity_ids: Sequence[str] | None,
    baseline_entity_ids: Sequence[str],
    propagated_entity_ids: Sequence[str],
) -> DownstreamImpactResult:
    """Compare two frozen downstream outputs without biological assumptions."""

    baseline = set(baseline_entity_ids)
    propagated = set(propagated_entity_ids)
    gold = set(gold_entity_ids) if gold_entity_ids is not None else None
    precision = recall = None
    false_expansions = 0
    if gold is not None:
        true_positive = len(propagated & gold)
        precision = true_positive / len(propagated) if propagated else 0.0
        recall = true_positive / len(gold) if gold else 0.0
        false_expansions = len(propagated - gold)
    return DownstreamImpactResult(
        len(baseline),
        len(propagated),
        tuple(sorted(propagated - baseline)),
        tuple(sorted(baseline - propagated)),
        precision,
        recall,
        false_expansions,
    )


__all__ = [
    "DownstreamAdapter",
    "DownstreamEntity",
    "DownstreamImpactResult",
    "compare_downstream_entities",
]
