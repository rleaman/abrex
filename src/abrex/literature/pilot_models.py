"""Typed interchange models for the random-literature comparison pilot."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PILOT_SCHEMA_VERSION: Literal["random-literature-pilot-v2"] = (
    "random-literature-pilot-v2"
)
Arm = Literal["pmc_cc_by", "pubmed_abstract"]
MethodStatus = Literal["completed", "failed", "unavailable", "not_run"]
CoverageStatus = Literal["complete", "partial", "none"]


class FrozenModel(BaseModel):
    """Strict immutable base for scientific pilot records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PilotConfig(FrozenModel):
    """Validated acquisition and method-execution limits."""

    output_dir: str
    seed: int = 20260908
    pmc_target: int = Field(default=10, ge=1, le=10)
    pubmed_target: int = Field(default=20, ge=1, le=20)
    pmc_max_attempts: int = Field(default=1000, ge=1, le=1000)
    pubmed_max_attempts: int = Field(default=1000, ge=1, le=1000)
    max_metadata_requests: int = Field(default=80, ge=2, le=200)
    max_total_bytes: int = Field(default=200_000_000, ge=1)
    max_response_bytes: int = Field(default=8_000_000, ge=1)
    max_elapsed_seconds: float = Field(default=14_400, gt=0, le=14_400)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    request_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=1.0, ge=0, le=60)
    delay_seconds: float = Field(default=0.34, ge=0, le=60)
    uid_search_ceiling: int = Field(default=100_000_000, ge=1)
    user_agent: str = "abrex-t051-pilot/2.0"
    resume: bool = True
    source_comparison_count: int = Field(default=3, ge=3, le=10)
    abbreviation_heuristic: str = "bounded-scientific-token-v1"
    ab3p: Ab3PRuntimeConfig
    plodv2: PlodRuntimeConfig


class Ab3PRuntimeConfig(FrozenModel):
    """Pinned Ab3P worker and installation inputs."""

    enabled: bool = True
    interpreter: str
    installation_manifest: str
    installation_root: str
    cache_dir: str
    timeout_seconds: float = Field(default=120.0, gt=0, le=600)


class PlodRuntimeConfig(FrozenModel):
    """Pinned PLODv2 worker and model inputs."""

    enabled: bool = True
    interpreter: str
    checkpoint_path: str
    checkpoint_sha256: str
    device: Literal["cpu", "cuda"] = "cpu"
    max_chars_per_window: int = Field(default=4096, ge=256, le=65536)
    window_overlap: int = Field(default=128, ge=0, le=4096)
    timeout_seconds: float = Field(default=7200.0, gt=0, le=14_400)


class SourceArtifact(FrozenModel):
    """Immutable downloaded representation."""

    kind: Literal["jats_xml", "pubmed_xml", "bioc_xml"]
    path: str
    sha256: str
    bytes: int = Field(ge=0)
    source_url: str
    retrieved_at: str


class LicenseEvidence(FrozenModel):
    """Article-level license evidence extracted from the selected JATS article."""

    family: Literal["CC BY"]
    version: str | None = None
    url: str
    text: str
    source_path: str


class AttemptRecord(FrozenModel):
    """One deterministic identifier draw and its observed outcome."""

    arm: Arm
    draw_index: int = Field(ge=0)
    identifier: str
    outcome: Literal["selected", "excluded", "failed"]
    reason: str
    observed_at: str
    response_sha256: str | None = None
    response_bytes: int | None = Field(default=None, ge=0)
    article_group_id: str | None = None


class CanonicalSpan(FrozenModel):
    """One section-local Unicode half-open span with captured text."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def _ordered(self) -> CanonicalSpan:
        if self.end <= self.start:
            raise ValueError("prediction spans must be nonempty")
        return self


class PredictionPair(FrozenModel):
    """One occurrence-level SF/LF relation."""

    pair_id: str
    short_form: CanonicalSpan
    long_form: CanonicalSpan
    score: float | None = None
    provenance: dict[str, object] = Field(default_factory=dict)


class PredictionSpan(FrozenModel):
    """One independent detector span, including unpaired PLOD output."""

    span_id: str
    label: Literal["SF", "LF"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    score: float | None = None
    provenance: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ordered(self) -> PredictionSpan:
        if self.end <= self.start:
            raise ValueError("prediction spans must be nonempty")
        return self


class MethodOutput(FrozenModel):
    """Complete status and section-local output for one method."""

    method_id: str
    identity: str
    version: str
    config_sha256: str
    runtime: dict[str, object] = Field(default_factory=dict)
    status: MethodStatus
    coverage: CoverageStatus
    elapsed_seconds: float = Field(default=0.0, ge=0)
    pairs: tuple[PredictionPair, ...] = ()
    spans: tuple[PredictionSpan, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _coverage_matches_status(self) -> MethodOutput:
        if self.status != "completed" and self.coverage == "complete":
            raise ValueError("only completed methods may claim complete coverage")
        return self


class CandidateProposal(FrozenModel):
    """Separately labeled structural or lexical proposal."""

    candidate_id: str
    generator: str
    short_form: CanonicalSpan
    long_form: CanonicalSpan
    provenance: dict[str, object] = Field(default_factory=dict)


class PilotSection(FrozenModel):
    """Immutable review passage and all outputs scoped to it."""

    section_id: str
    document_id: str
    heading: str
    source_kind: str
    canonical_text: str
    canonical_text_sha256: str
    source_locator: str
    previous_section_id: str | None = None
    next_section_id: str | None = None
    method_outputs: dict[str, MethodOutput] = Field(default_factory=dict)
    structural_candidates: tuple[CandidateProposal, ...] = ()
    lexical_candidates: tuple[CandidateProposal, ...] = ()

    @model_validator(mode="after")
    def _validate_identity_and_spans(self) -> PilotSection:
        digest = hashlib.sha256(self.canonical_text.encode("utf-8")).hexdigest()
        if digest != self.canonical_text_sha256:
            raise ValueError("canonical_text_sha256 does not match canonical_text")
        if any(key != output.method_id for key, output in self.method_outputs.items()):
            raise ValueError("method output mapping keys must equal method_id")
        identifiers: list[str] = []
        for output in self.method_outputs.values():
            for pair in output.pairs:
                _validate_slice(self.canonical_text, pair.short_form)
                _validate_slice(self.canonical_text, pair.long_form)
                identifiers.append(pair.pair_id)
            for span in output.spans:
                _validate_bounds(self.canonical_text, span.start, span.end, span.text)
                identifiers.append(span.span_id)
        for candidate in self.structural_candidates + self.lexical_candidates:
            _validate_slice(self.canonical_text, candidate.short_form)
            _validate_slice(self.canonical_text, candidate.long_form)
            identifiers.append(candidate.candidate_id)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("prediction and candidate IDs must be unique in a section")
        return self


class StructureRecord(FrozenModel):
    """Source structure retained without inventing canonical offsets."""

    structure_id: str
    kind: str
    text: str
    source_path: str
    section_id: str | None = None
    parent_id: str | None = None


class PilotRecord(FrozenModel):
    """Selected article group with immutable source and canonical sections."""

    article_id: str
    article_group_id: str
    arm: Arm
    title: str
    pmid: str | None = None
    pmcid: str | None = None
    source_url: str
    license: LicenseEvidence | None = None
    source_artifacts: tuple[SourceArtifact, ...]
    sections: tuple[PilotSection, ...]
    structures: tuple[StructureRecord, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_sections(self) -> PilotRecord:
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section IDs must be unique within an article")
        document_ids = [section.document_id for section in self.sections]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("document IDs must be unique within an article")
        return self


class FrameRecord(FrozenModel):
    """Verified numeric UID frame used for equal-probability rejection draws."""

    database: Literal["pmc", "pubmed"]
    lower_bound: int = 1
    upper_bound: int = Field(ge=1)
    population_count: int = Field(ge=1)
    verified_at: str
    verification_query: str
    response_hashes: tuple[str, ...]


class LimitReport(FrozenModel):
    """Observed bounded-resource accounting."""

    metadata_requests: int = Field(ge=0)
    pmc_attempts: int = Field(ge=0)
    pubmed_attempts: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    reached: tuple[str, ...] = ()


class HeuristicEvidence(FrozenModel):
    """Review-only abbreviation-likelihood evidence."""

    name: str
    tokens: tuple[str, ...]
    enriched: bool


class InventoryRecord(FrozenModel):
    """One section-level agreement or diagnostic inventory entry."""

    inventory_id: str
    article_id: str
    section_id: str
    canonical_text_sha256: str
    category: Literal[
        "exact_agreement",
        "relation_disagreement",
        "boundary_disagreement",
        "unpaired_span",
        "all_primary_zero",
        "method_failure",
    ]
    pair_ids: tuple[str, ...] = ()
    span_ids: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    eligible_for_review: bool
    heuristic: HeuristicEvidence | None = None


class SourceComparison(FrozenModel):
    """Representation audit for JATS and BioC without shared-offset claims."""

    article_id: str
    jats_sha256: str
    bioc_sha256: str
    jats_section_count: int = Field(ge=0)
    bioc_passage_count: int = Field(ge=0)
    exact_text_matches: int = Field(ge=0)
    normalized_text_matches: int = Field(ge=0)
    unmatched_jats_sections: tuple[str, ...]
    unmatched_bioc_passages: tuple[str, ...]
    jats_structure_counts: dict[str, int]
    observations: tuple[str, ...]


class PilotManifest(FrozenModel):
    """Complete machine-readable T051 result."""

    schema_version: Literal["random-literature-pilot-v2"] = PILOT_SCHEMA_VERSION
    run_id: str
    started_at: str
    finished_at: str
    config_sha256: str
    protocol: dict[str, object]
    frames: tuple[FrameRecord, ...]
    limits: LimitReport
    counts: dict[str, int]
    attempts: tuple[AttemptRecord, ...]
    records: tuple[PilotRecord, ...]
    inventories: tuple[InventoryRecord, ...]
    source_comparisons: tuple[SourceComparison, ...]
    limitations: tuple[str, ...]


def stable_id(prefix: str, *parts: object) -> str:
    """Return a compact stable identifier from immutable JSON values."""

    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def config_fingerprint(config: BaseModel | dict[str, object]) -> str:
    """Fingerprint a resolved typed configuration deterministically."""

    data = config.model_dump(mode="json") if isinstance(config, BaseModel) else config
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_slice(text: str, span: CanonicalSpan) -> None:
    _validate_bounds(text, span.start, span.end, span.text)


def _validate_bounds(text: str, start: int, end: int, captured: str) -> None:
    if start < 0 or end > len(text) or start >= end:
        raise ValueError(f"span [{start}, {end}) is outside canonical text")
    if text[start:end] != captured:
        raise ValueError(f"span [{start}, {end}) does not slice canonical text")


PilotConfig.model_rebuild()


__all__ = [
    "PILOT_SCHEMA_VERSION",
    "Ab3PRuntimeConfig",
    "AttemptRecord",
    "CandidateProposal",
    "CanonicalSpan",
    "FrameRecord",
    "HeuristicEvidence",
    "InventoryRecord",
    "LicenseEvidence",
    "LimitReport",
    "MethodOutput",
    "PilotConfig",
    "PilotManifest",
    "PilotRecord",
    "PilotSection",
    "PlodRuntimeConfig",
    "PredictionPair",
    "PredictionSpan",
    "SourceArtifact",
    "SourceComparison",
    "StructureRecord",
    "config_fingerprint",
    "stable_id",
]
