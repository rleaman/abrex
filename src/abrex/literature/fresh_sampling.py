"""Pure contracts and deterministic sampling for the T065 blind packet."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.literature.blind_review import (
    BlindReviewCase,
    BlindReviewPacket,
    create_blind_packet,
)
from abrex.literature.review_models import ReviewStructure

FRESH_SAMPLE_SCHEMA = "abrex-fresh-sample-v1"
_PMC_ID = re.compile(r"PMC\d+", re.IGNORECASE)
_NUMERIC_ID = re.compile(r"\d{6,10}")


class FreshSamplingError(ValueError):
    """Raised when a source-only sample cannot satisfy the frozen protocol."""


class FrozenFreshConfig(BaseModel):
    """Scientific and operational limits frozen before T065 acquisition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = FRESH_SAMPLE_SCHEMA
    protocol_path: str
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_dir: str
    delivery_dir: str
    seed: int = 20261002
    article_groups: int = Field(default=8, ge=1)
    pmc_prose_passages: int = Field(default=12, ge=1)
    pubmed_abstract_passages: int = Field(default=12, ge=1)
    table_or_list_sections: int = Field(default=8, ge=1)
    maximum_items_per_group: int = Field(default=4, ge=1)
    maximum_attempts: int = Field(default=1000, ge=1, le=1000)
    maximum_download_bytes: int = Field(default=134_217_728, ge=1)
    maximum_elapsed_seconds: float = Field(default=7200.0, gt=0, le=7200)
    maximum_response_bytes: int = Field(default=8_000_000, ge=1)
    maximum_metadata_requests: int = Field(default=80, ge=1, le=200)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    request_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=1.0, ge=0, le=60)
    delay_seconds: float = Field(default=0.34, ge=0, le=60)
    uid_search_ceiling: int = Field(default=100_000_000, ge=1)
    prose_target_chars: int = Field(default=700, ge=100)
    prose_maximum_chars: int = Field(default=1800, ge=200)
    prose_minimum_chars: int = Field(default=80, ge=1)
    structured_maximum_chars: int = Field(default=8000, ge=200)
    user_agent: str = "abrex-t065-fresh-sample/1.0"
    exclusion_paths: tuple[str, ...]

    @property
    def max_total_bytes(self) -> int:
        """Expose the shared bounded-client configuration contract."""

        return self.maximum_download_bytes

    @property
    def max_elapsed_seconds(self) -> float:
        """Expose the shared bounded-client configuration contract."""

        return self.maximum_elapsed_seconds

    @property
    def max_response_bytes(self) -> int:
        """Expose the shared bounded-client configuration contract."""

        return self.maximum_response_bytes

    @property
    def max_metadata_requests(self) -> int:
        """Expose the shared bounded-client configuration contract."""

        return self.maximum_metadata_requests

    @model_validator(mode="after")
    def frozen_totals(self) -> FrozenFreshConfig:
        total = (
            self.pmc_prose_passages
            + self.pubmed_abstract_passages
            + self.table_or_list_sections
        )
        if total != self.article_groups * self.maximum_items_per_group:
            raise ValueError("frozen item totals must fill every article-group slot")
        if self.table_or_list_sections != self.article_groups:
            raise ValueError(
                "the frozen protocol requires one structured case per group"
            )
        if self.prose_minimum_chars > self.prose_target_chars:
            raise ValueError("minimum prose length exceeds target length")
        if self.prose_target_chars > self.prose_maximum_chars:
            raise ValueError("target prose length exceeds maximum length")
        return self


class SourcePassage(BaseModel):
    """One source-derived passage candidate without predictions or labels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    text: str = Field(min_length=1)
    structures: tuple[ReviewStructure, ...] = ()


class FreshArticleGroup(BaseModel):
    """All source-only candidates from one linked PMID/PMCID article group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(pattern=r"^\d+$")
    pmid: str = Field(pattern=r"^\d+$")
    pmcid: str = Field(pattern=r"^PMC\d+$")
    title: str = Field(min_length=1)
    pmc_source_url: str = Field(min_length=1)
    pubmed_source_url: str = Field(min_length=1)
    pmc_prose: tuple[SourcePassage, ...]
    pubmed_abstract: tuple[SourcePassage, ...]
    structured: tuple[SourcePassage, ...]


class ExclusionLedger(BaseModel):
    """Traceable linked-identity exclusions assembled from frozen evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pmids: tuple[str, ...]
    pmcids: tuple[str, ...]
    source_hashes: dict[str, str]

    def excludes(self, *, pmid: str | None = None, pmcid: str | None = None) -> bool:
        """Return whether either linked identifier is in prior evidence."""

        normalized_pmcid = pmcid.upper() if pmcid else None
        return bool(
            (pmid is not None and pmid in self.pmids)
            or (normalized_pmcid is not None and normalized_pmcid in self.pmcids)
        )


def load_exclusion_ledger(paths: Iterable[Path]) -> ExclusionLedger:
    """Collect linked IDs and hashes without inspecting scientific text."""

    pmids: set[str] = set()
    pmcids: set[str] = set()
    hashes: dict[str, str] = {}
    for path in paths:
        payload = path.read_bytes()
        hashes[path.as_posix()] = hashlib.sha256(payload).hexdigest()
        if path.suffix == ".jsonl":
            values = [json.loads(line) for line in payload.decode("utf-8").splitlines()]
        else:
            values = [json.loads(payload)]
        for value in values:
            _collect_identifiers(value, pmids, pmcids)
    return ExclusionLedger(
        pmids=tuple(sorted(pmids, key=int)),
        pmcids=tuple(sorted(pmcids, key=lambda value: int(value[3:]))),
        source_hashes=dict(sorted(hashes.items())),
    )


def segment_prose(
    text: str,
    *,
    source_ref: str,
    heading: str,
    source_kind: str,
    minimum_chars: int,
    target_chars: int,
    maximum_chars: int,
) -> tuple[SourcePassage, ...]:
    """Segment prose by sentence boundaries using only source structure and length."""

    normalized = " ".join(text.split())
    if len(normalized) < minimum_chars:
        return ()
    sentences = [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized)
        if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        proposed = sentence if not current else f"{current} {sentence}"
        if current and len(proposed) > target_chars:
            chunks.append(current)
            current = sentence
        else:
            current = proposed
    if current:
        chunks.append(current)
    result: list[SourcePassage] = []
    for index, chunk in enumerate(chunks, 1):
        if len(chunk) < minimum_chars:
            if result:
                previous = result.pop()
                chunk = f"{previous.text} {chunk}"
                index -= 1
            else:
                continue
        if len(chunk) > maximum_chars:
            # Preserve an overlong source sentence rather than severing a relation.
            continue
        result.append(
            SourcePassage(
                source_ref=f"{source_ref}#segment-{index}",
                heading=heading,
                source_kind=source_kind,
                text=chunk,
            )
        )
    return tuple(result)


def build_fresh_packet(
    groups: Sequence[FreshArticleGroup], config: FrozenFreshConfig
) -> BlindReviewPacket:
    """Select the approved 32 source-only cases in a deterministic order."""

    if len(groups) != config.article_groups:
        raise FreshSamplingError(
            f"fresh sample needs {config.article_groups} groups; received {len(groups)}"
        )
    cases: list[BlindReviewCase] = []
    for index, group in enumerate(groups):
        pmc_count = 2 if index < config.article_groups // 2 else 1
        abstract_count = config.maximum_items_per_group - pmc_count - 1
        selected = (
            _choose(group.pmc_prose, pmc_count, config.seed, group.group_id, "pmc"),
            _choose(
                group.pubmed_abstract,
                abstract_count,
                config.seed,
                group.group_id,
                "abstract",
            ),
            _choose(group.structured, 1, config.seed, group.group_id, "structured"),
        )
        for arm_name, passages in zip(
            ("pmc_prose", "pubmed_abstract", "table_or_list"),
            selected,
            strict=True,
        ):
            for passage in passages:
                is_pubmed = arm_name == "pubmed_abstract"
                case_key = _stable_key(
                    config.seed, group.group_id, arm_name, passage.source_ref
                )
                cases.append(
                    BlindReviewCase(
                        case_id=f"fresh-{case_key[:20]}",
                        article_id=group.pmid if is_pubmed else group.pmcid,
                        article_group_id=group.group_id,
                        title=group.title,
                        arm="pubmed_abstract" if is_pubmed else "pmc_cc_by",
                        source_url=(
                            group.pubmed_source_url
                            if is_pubmed
                            else group.pmc_source_url
                        ),
                        source_kind=arm_name,
                        section_id=passage.source_ref,
                        section_heading=passage.heading,
                        canonical_text_sha256=hashlib.sha256(
                            passage.text.encode("utf-8")
                        ).hexdigest(),
                        passage_start=0,
                        passage_end=len(passage.text),
                        text=passage.text,
                        structures=passage.structures,
                    )
                )
    counts = {
        kind: sum(case.source_kind == kind for case in cases)
        for kind in ("pmc_prose", "pubmed_abstract", "table_or_list")
    }
    expected = {
        "pmc_prose": config.pmc_prose_passages,
        "pubmed_abstract": config.pubmed_abstract_passages,
        "table_or_list": config.table_or_list_sections,
    }
    if counts != expected:
        raise FreshSamplingError(f"fresh source mix differs from protocol: {counts}")
    group_counts = {
        group.group_id: sum(case.article_group_id == group.group_id for case in cases)
        for group in groups
    }
    if any(value > config.maximum_items_per_group for value in group_counts.values()):
        raise FreshSamplingError("fresh sample exceeds per-group cap")
    return create_blind_packet(
        tuple(cases),
        protocol_id=f"t063-{config.protocol_sha256[:20]}",
        seed=config.seed,
    )


def assert_prediction_free(packet: BlindReviewPacket) -> None:
    """Reject detector/model fields if a future serializer accidentally adds them."""

    forbidden = {
        "suggestions",
        "method_ids",
        "method_diagnostics",
        "confidence",
        "prediction",
        "candidate",
    }
    present = sorted(_mapping_keys(packet.model_dump(mode="json")) & forbidden)
    if present:
        raise FreshSamplingError(f"blind packet contains forbidden fields: {present}")


def _choose(
    candidates: Sequence[SourcePassage],
    count: int,
    seed: int,
    group_id: str,
    role: str,
) -> tuple[SourcePassage, ...]:
    ordered = sorted(
        candidates,
        key=lambda item: _stable_key(seed, group_id, role, item.source_ref),
    )
    if len(ordered) < count:
        raise FreshSamplingError(
            f"group {group_id} has {len(ordered)} {role} candidates; needs {count}"
        )
    return tuple(ordered[:count])


def _stable_key(*parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {
            key for item in value.values() for key in _mapping_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _mapping_keys(item)}
    return set()


def _collect_identifiers(
    value: object, pmids: set[str], pmcids: set[str], parent_key: str = ""
) -> None:
    if isinstance(value, Mapping):
        arm = value.get("arm")
        for key, item in value.items():
            if isinstance(item, str):
                normalized = item.strip()
                pmc_match = _PMC_ID.fullmatch(normalized)
                if pmc_match and key in {"pmcid", "article_id", "identifier"}:
                    pmcids.add(pmc_match.group(0).upper())
                if _NUMERIC_ID.fullmatch(normalized) and key in {
                    "pmid",
                    "article_group_id",
                    "source_document_id",
                    "article_id",
                }:
                    pmids.add(normalized)
                if (
                    _NUMERIC_ID.fullmatch(normalized)
                    and key == "identifier"
                    and arm == "pubmed_abstract"
                ):
                    pmids.add(normalized)
            _collect_identifiers(item, pmids, pmcids, key)
    elif isinstance(value, list):
        for item in value:
            _collect_identifiers(item, pmids, pmcids, parent_key)
    elif isinstance(value, str) and parent_key == "identifiers":
        normalized = value.strip()
        if _NUMERIC_ID.fullmatch(normalized):
            pmids.add(normalized)
        elif _PMC_ID.fullmatch(normalized):
            pmcids.add(normalized.upper())


__all__ = [
    "FRESH_SAMPLE_SCHEMA",
    "ExclusionLedger",
    "FreshArticleGroup",
    "FreshSamplingError",
    "FrozenFreshConfig",
    "SourcePassage",
    "assert_prediction_free",
    "build_fresh_packet",
    "load_exclusion_ledger",
    "segment_prose",
]
