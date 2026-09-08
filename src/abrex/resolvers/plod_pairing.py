"""Explicit pairing strategies for independent PLODv2 spans."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
)
from abrex.resolvers.plod import (
    PlodConfig,
    PlodSpanDetector,
    PlodSpanRecord,
    ValidatedPlodSpan,
)

PairingStrategyName = Literal["pattern_greedy", "position_anchored"]
PairSelectionName = Literal["one_to_one", "shared_long_form"]
PAIRING_VERSION = "plodv2-pairing-v1"


class PlodPairingConfig(BaseModel):
    """Typed policy for converting independent spans to local definitions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: PlodConfig
    strategy: PairingStrategyName = "position_anchored"
    selection: PairSelectionName = "one_to_one"
    allow_reverse_order: bool = True
    max_gap: int = Field(default=160, ge=0)
    require_local_pattern: bool = False
    pair_score_decay: float = Field(default=1.0, gt=0)


class PlodPairingResolverConfig(BaseModel):
    """Registry-facing flattened configuration for the composed resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_path: str
    checkpoint_sha256: str | None = None
    device: Literal["auto", "cpu", "cuda"] = "cpu"
    batch_size: int = Field(default=1, ge=1)
    max_chars_per_window: int | None = Field(default=None, ge=1)
    window_overlap: int = Field(default=0, ge=0)
    duplicate_policy: Literal["deduplicate", "retain"] = "deduplicate"
    runtime_version: str = "flair-optional"
    strategy: PairingStrategyName = "position_anchored"
    selection: PairSelectionName = "one_to_one"
    allow_reverse_order: bool = True
    max_gap: int = Field(default=160, ge=0)
    require_local_pattern: bool = False
    pair_score_decay: float = Field(default=1.0, gt=0)


@dataclass(frozen=True, slots=True)
class PairCandidate:
    """One eligible local pair and its independently computed cost."""

    short_form: ValidatedPlodSpan
    long_form: ValidatedPlodSpan
    cost: float
    pattern: str | None


@dataclass(frozen=True, slots=True)
class PairingResult:
    """Selected pairs plus auditable candidate/rejection diagnostics."""

    document_id: str
    candidates: tuple[PairCandidate, ...]
    selected: tuple[PairCandidate, ...]
    diagnostics: tuple[str, ...] = ()


class PairingStrategy(Protocol):
    identity: str
    version: str

    def pair(
        self,
        document: Document,
        spans: Sequence[ValidatedPlodSpan],
        config: PlodPairingConfig,
    ) -> PairingResult: ...


class SpanDetector(Protocol):
    cache_identity: dict[str, object]

    def detect(self, document: Document) -> PlodSpanRecord:
        """Return a T023 span record."""


class PositionAnchoredPairing:
    """Pair candidates using only text at the two candidate positions."""

    identity = "position_anchored"
    version = PAIRING_VERSION

    def pair(
        self,
        document: Document,
        spans: Sequence[ValidatedPlodSpan],
        config: PlodPairingConfig,
    ) -> PairingResult:
        candidates, diagnostics = _eligible_candidates(document, spans, config)
        ordered = sorted(candidates, key=_candidate_key)
        selected: list[PairCandidate] = []
        used_short: set[tuple[int, int]] = set()
        used_long: set[tuple[int, int]] = set()
        for candidate in ordered:
            sf_key = _span_key(candidate.short_form)
            lf_key = _span_key(candidate.long_form)
            if sf_key in used_short or (
                config.selection == "one_to_one" and lf_key in used_long
            ):
                diagnostics.append("rejected_selection_conflict")
                continue
            selected.append(candidate)
            used_short.add(sf_key)
            used_long.add(lf_key)
        return PairingResult(
            document.document_id, tuple(ordered), tuple(selected), tuple(diagnostics)
        )


class PatternGreedyPairing(PositionAnchoredPairing):
    """Compatibility strategy: pattern/cost sorted greedy selection."""

    identity = "pattern_greedy"

    def pair(
        self,
        document: Document,
        spans: Sequence[ValidatedPlodSpan],
        config: PlodPairingConfig,
    ) -> PairingResult:
        # The base implementation is deliberately deterministic but not
        # presented as a globally optimal assignment algorithm.
        return super().pair(document, spans, config)


PAIRING_STRATEGIES: dict[PairingStrategyName, PairingStrategy] = {
    "position_anchored": PositionAnchoredPairing(),
    "pattern_greedy": PatternGreedyPairing(),
}


class PlodPairingResolver:
    """Compose T023 detection with an explicit, inspectable pairing policy."""

    identity = "plodv2_pairing"
    version = PAIRING_VERSION

    def __init__(
        self,
        *,
        detector: SpanDetector | None = None,
        detector_config: PlodConfig | None = None,
        strategy: PairingStrategyName = "position_anchored",
        selection: PairSelectionName = "one_to_one",
        allow_reverse_order: bool = True,
        max_gap: int = 160,
        require_local_pattern: bool = False,
        pair_score_decay: float = 1.0,
        detector_config_path: str | None = None,
        checkpoint_path: str | None = None,
        checkpoint_sha256: str | None = None,
        device: Literal["auto", "cpu", "cuda"] = "cpu",
        batch_size: int = 1,
        max_chars_per_window: int | None = None,
        window_overlap: int = 0,
        duplicate_policy: Literal["deduplicate", "retain"] = "deduplicate",
        runtime_version: str = "flair-optional",
    ) -> None:
        del detector_config_path
        selected_detector_config = detector_config or PlodConfig(
            checkpoint_path=checkpoint_path or "",
            checkpoint_sha256=checkpoint_sha256,
            device=device,
            batch_size=batch_size,
            max_chars_per_window=max_chars_per_window,
            window_overlap=window_overlap,
            duplicate_policy=duplicate_policy,
            runtime_version=runtime_version,
        )
        self.detector = detector or PlodSpanDetector(config=selected_detector_config)
        self.config = PlodPairingConfig(
            detector=selected_detector_config,
            strategy=strategy,
            selection=selection,
            allow_reverse_order=allow_reverse_order,
            max_gap=max_gap,
            require_local_pattern=require_local_pattern,
            pair_score_decay=pair_score_decay,
        )

    @property
    def cache_identity(self) -> dict[str, object]:
        return {
            "resolver": self.identity,
            "version": self.version,
            "detector": self.detector.cache_identity,
            "pairing": self.config.model_dump(mode="json"),
        }

    def pair_record(self, document: Document) -> PairingResult:
        spans = self.detector.detect(document).validated_spans
        strategy = PAIRING_STRATEGIES[self.config.strategy]
        return strategy.pair(document, spans, self.config)

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        result = self.pair_record(document)
        for candidate in result.selected:
            pair_score = _pair_score(candidate.cost, self.config.pair_score_decay)
            notes = [
                f"pairing_strategy:{self.config.strategy}",
                f"pair_cost:{candidate.cost:g}",
                f"short_span_score:{candidate.short_form.score}",
                f"long_span_score:{candidate.long_form.score}",
            ]
            if candidate.pattern is not None:
                notes.append(f"local_pattern:{candidate.pattern}")
            yield AbbreviationDefinition(
                document.document_id,
                short_form=candidate.short_form.span,
                long_form=candidate.long_form.span,
                short_form_text=candidate.short_form.text,
                long_form_text=candidate.long_form.text,
                provenance=AnnotationProvenance(
                    source_record_id=document.document_id,
                    adapter_identity=self.identity,
                    adapter_version=self.version,
                    transformation_notes=tuple(notes),
                ),
                prediction=PredictionMetadata(
                    score=pair_score,
                    component=self.identity,
                    component_version=self.version,
                    model_artifact_fingerprint=str(
                        self.detector.cache_identity["checkpoint_sha256"]
                    )
                    if "checkpoint_sha256" in self.detector.cache_identity
                    else None,
                    feature_config_fingerprint=_fingerprint(
                        self.config.model_dump(mode="json")
                    ),
                ),
            )


def _eligible_candidates(
    document: Document,
    spans: Sequence[ValidatedPlodSpan],
    config: PlodPairingConfig,
) -> tuple[list[PairCandidate], list[str]]:
    shorts = [item for item in spans if item.label == "SF"]
    longs = [item for item in spans if item.label == "LF"]
    candidates: list[PairCandidate] = []
    diagnostics: list[str] = []
    for short in shorts:
        for long in longs:
            if short.span == long.span or _overlaps(short, long):
                diagnostics.append("rejected_overlapping_spans")
                continue
            if long.span.end <= short.span.start:
                first, second = long, short
                order = "lf_before_sf"
            elif short.span.end <= long.span.start and config.allow_reverse_order:
                first, second = short, long
                order = "sf_before_lf"
            else:
                diagnostics.append("rejected_reverse_order")
                continue
            gap = second.span.start - first.span.end
            if gap > config.max_gap:
                diagnostics.append("rejected_distance")
                continue
            pattern = _local_pattern(document.text, first, second, order)
            if config.require_local_pattern and pattern is None:
                diagnostics.append("rejected_missing_local_pattern")
                continue
            cost = 0.0 if pattern is not None else float(gap)
            candidates.append(PairCandidate(short, long, cost, pattern))
    return candidates, diagnostics


def _local_pattern(
    text: str,
    first: ValidatedPlodSpan,
    second: ValidatedPlodSpan,
    order: str,
) -> str | None:
    between = text[first.span.end : second.span.start]
    after = text[second.span.end : second.span.end + 2]
    if order == "lf_before_sf":
        if re.fullmatch(r"\s*\(\s*", between) and re.match(r"\s*[),;]", after):
            return "lf_parenthetical_sf"
        if re.fullmatch(r"\s*\[\s*", between) and re.match(r"\s*\]", after):
            return "lf_bracketed_sf"
    else:
        if re.fullmatch(r"\s*[,;:]\s*", between):
            return "sf_separator_lf"
        if re.fullmatch(r"\s*\(\s*[,;]?\s*", between):
            return "sf_parenthetical_lf"
    return None


def _candidate_key(candidate: PairCandidate) -> tuple[float, int, int, int, int]:
    return (
        candidate.cost,
        candidate.short_form.span.start,
        candidate.long_form.span.start,
        candidate.short_form.span.end,
        candidate.long_form.span.end,
    )


def _span_key(item: ValidatedPlodSpan) -> tuple[int, int]:
    return item.span.start, item.span.end


def _overlaps(first: ValidatedPlodSpan, second: ValidatedPlodSpan) -> bool:
    return first.span.start < second.span.end and second.span.start < first.span.end


def _pair_score(cost: float, decay: float) -> float:
    return 1.0 if cost == 0 else 1.0 / (1.0 + decay * cost)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "PAIRING_VERSION",
    "PAIRING_STRATEGIES",
    "PairCandidate",
    "PairingResult",
    "PlodPairingConfig",
    "PlodPairingResolverConfig",
    "PlodPairingResolver",
    "PairingStrategy",
    "SpanDetector",
    "PositionAnchoredPairing",
    "PatternGreedyPairing",
]
