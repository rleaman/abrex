"""Typed source-only sampling contracts for campaign Milestone C."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.literature.blind_review import (
    BlindReviewCase,
    BlindReviewPacket,
    create_blind_packet,
)
from abrex.literature.fresh_sampling import (
    FreshArticleGroup,
    FreshSamplingError,
    SourcePassage,
    assert_prediction_free,
)

MILESTONE_C_SAMPLE_SCHEMA = "campaign-2026-10-milestone-c-sample-v1"


class MilestoneCSampleConfig(BaseModel):
    """Frozen scientific design and bounded NCBI acquisition limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = MILESTONE_C_SAMPLE_SCHEMA
    protocol_path: str
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_dir: str
    delivery_dir: str
    seed: int = 20261006
    representative_groups: int = Field(default=48, ge=1)
    structural_groups: int = Field(default=24, ge=1)
    maximum_attempts_per_stratum: int = Field(default=1200, ge=1, le=5000)
    maximum_download_bytes: int = Field(default=536_870_912, ge=1)
    maximum_elapsed_seconds: float = Field(default=7200.0, gt=0, le=7200)
    maximum_response_bytes: int = Field(default=8_000_000, ge=1)
    maximum_metadata_requests: int = Field(default=80, ge=1, le=200)
    maximum_http_attempts: int = Field(default=750, ge=1, le=5000)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    request_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=1.0, ge=0, le=60)
    delay_seconds: float = Field(default=0.34, ge=0, le=60)
    uid_search_ceiling: int = Field(default=100_000_000, ge=1)
    prose_target_chars: int = Field(default=700, ge=100)
    prose_maximum_chars: int = Field(default=1800, ge=200)
    prose_minimum_chars: int = Field(default=80, ge=1)
    structured_maximum_chars: int = Field(default=8000, ge=200)
    user_agent: str = "abrex-campaign-2026-10-milestone-c/1.0"
    exclusion_paths: tuple[str, ...]

    @property
    def max_total_bytes(self) -> int:
        return self.maximum_download_bytes

    @property
    def max_elapsed_seconds(self) -> float:
        return self.maximum_elapsed_seconds

    @property
    def max_response_bytes(self) -> int:
        return self.maximum_response_bytes

    @property
    def max_metadata_requests(self) -> int:
        return self.maximum_metadata_requests

    @property
    def max_total_requests(self) -> int:
        return self.maximum_http_attempts

    @model_validator(mode="after")
    def validate_lengths(self) -> MilestoneCSampleConfig:
        if self.prose_minimum_chars > self.prose_target_chars:
            raise ValueError("minimum prose length exceeds target length")
        if self.prose_target_chars > self.prose_maximum_chars:
            raise ValueError("target prose length exceeds maximum length")
        return self


def build_milestone_c_packet(
    representative: Sequence[FreshArticleGroup],
    structural: Sequence[FreshArticleGroup],
    config: MilestoneCSampleConfig,
) -> BlindReviewPacket:
    """Create the frozen 120-case packet from two disjoint source-only strata."""

    if len(representative) != config.representative_groups:
        raise FreshSamplingError(
            "representative sample needs "
            f"{config.representative_groups} groups; received {len(representative)}"
        )
    if len(structural) != config.structural_groups:
        raise FreshSamplingError(
            f"structural sample needs {config.structural_groups} groups; "
            f"received {len(structural)}"
        )
    representative_ids = {group.group_id for group in representative}
    structural_ids = {group.group_id for group in structural}
    overlap = sorted(representative_ids & structural_ids)
    if overlap:
        raise FreshSamplingError(f"Milestone C strata overlap: {overlap}")

    cases: list[BlindReviewCase] = []
    for group in representative:
        pmc = _choose(group.pmc_prose, config.seed, group.group_id, "pmc")
        abstract = _choose(
            group.pubmed_abstract, config.seed, group.group_id, "abstract"
        )
        cases.extend(
            (
                _case(group, pmc, "pmc_prose", config.seed),
                _case(group, abstract, "pubmed_abstract", config.seed),
            )
        )
    for group in structural:
        passage = _choose(group.structured, config.seed, group.group_id, "structural")
        cases.append(_case(group, passage, "table_or_list", config.seed))
    cases.sort(key=lambda item: _stable_key(config.seed, "case-order", item.case_id))

    counts = {
        kind: sum(case.source_kind == kind for case in cases)
        for kind in ("pmc_prose", "pubmed_abstract", "table_or_list")
    }
    expected = {
        "pmc_prose": config.representative_groups,
        "pubmed_abstract": config.representative_groups,
        "table_or_list": config.structural_groups,
    }
    if counts != expected:
        raise FreshSamplingError(f"Milestone C source mix differs: {counts}")
    packet = create_blind_packet(
        tuple(cases),
        protocol_id=f"campaign-2026-10-milestone-c-{config.protocol_sha256[:20]}",
        seed=config.seed,
    )
    assert_prediction_free(packet)
    return packet


def selected_passage(
    group: FreshArticleGroup,
    config: MilestoneCSampleConfig,
    role: str,
) -> SourcePassage:
    """Return the deterministic passage selected for a group and role."""

    candidates = {
        "pmc": group.pmc_prose,
        "abstract": group.pubmed_abstract,
        "structural": group.structured,
    }.get(role)
    if candidates is None:
        raise ValueError(f"unknown passage role: {role}")
    return _choose(candidates, config.seed, group.group_id, role)


def _case(
    group: FreshArticleGroup,
    passage: SourcePassage,
    source_kind: str,
    seed: int,
) -> BlindReviewCase:
    is_pubmed = source_kind == "pubmed_abstract"
    case_key = _stable_key(seed, group.group_id, source_kind, passage.source_ref)
    return BlindReviewCase(
        case_id=f"milestone-c-{case_key[:20]}",
        article_id=group.pmid if is_pubmed else group.pmcid,
        article_group_id=group.group_id,
        title=group.title,
        arm="pubmed_abstract" if is_pubmed else "pmc_cc_by",
        source_url=group.pubmed_source_url if is_pubmed else group.pmc_source_url,
        source_kind=source_kind,
        section_id=passage.source_ref,
        section_heading=passage.heading,
        canonical_text_sha256=hashlib.sha256(passage.text.encode("utf-8")).hexdigest(),
        passage_start=0,
        passage_end=len(passage.text),
        text=passage.text,
        structures=passage.structures,
    )


def _choose(
    candidates: Sequence[SourcePassage], seed: int, group_id: str, role: str
) -> SourcePassage:
    if not candidates:
        raise FreshSamplingError(f"group {group_id} has no {role} candidates")
    return min(
        candidates,
        key=lambda item: _stable_key(seed, group_id, role, item.source_ref),
    )


def _stable_key(*parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def config_fingerprint(config: MilestoneCSampleConfig) -> str:
    """Return the stable fingerprint recorded with the frozen sample."""

    payload = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mapping_keys(value: object) -> set[str]:
    """Collect recursive object keys for prediction-leakage audits."""

    if isinstance(value, Mapping):
        return set(value) | {
            key for item in value.values() for key in mapping_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in mapping_keys(item)}
    return set()


__all__ = [
    "MILESTONE_C_SAMPLE_SCHEMA",
    "MilestoneCSampleConfig",
    "build_milestone_c_packet",
    "config_fingerprint",
    "mapping_keys",
    "selected_passage",
]
