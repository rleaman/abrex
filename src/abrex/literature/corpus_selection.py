"""Deterministic, leakage-safe selection of a bounded literature corpus frame."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.config import load_config_layer

CORPUS_SELECTION_SCHEMA_VERSION = "large-scale-corpus-selection-v1"
_WHITESPACE = re.compile(r"\s+")


class CorpusSelectionError(ValueError):
    """Raised when a corpus-selection frame or policy is invalid."""


class WorkScaleLimits(BaseModel):
    """Conservative limits to carry from the pilot to a work host."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_documents: int = Field(default=100_000, ge=1)
    max_raw_bytes: int = Field(default=50_000_000_000, ge=1)
    max_runtime_minutes: float = Field(default=24 * 60, gt=0)
    estimated_documents_per_minute: float = Field(default=30.0, gt=0)


class CorpusFrameRecord(BaseModel):
    """One metadata candidate; text is optional and never fetched here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    text: str = ""
    pmid: str | None = None
    pmcid: str | None = None
    source_uri: str | None = None
    source_sha256: str | None = None
    source_version: str | None = None
    source_kind: Literal["abstract", "full_text", "unknown"] = "unknown"
    language: str = "en"
    document_type: str = "journal-article"
    reuse_class: str = "unknown"
    year: int | None = None
    available: bool = True
    challenge_tags: tuple[str, ...] = ()
    occurrence_keys: tuple[str, ...] = ()
    official_split: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> CorpusFrameRecord:
        if self.pmid is None and self.pmcid is None and not self.text.strip():
            raise ValueError("frame records need an identifier or text")
        if self.source_sha256 is not None and (
            len(self.source_sha256) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a 64-character hexadecimal digest")
        if any(not tag.strip() for tag in self.challenge_tags):
            raise ValueError("challenge_tags must not contain empty values")
        return self


class CorpusSelectionConfig(BaseModel):
    """YAML-selected universe, pools, protected records and cost envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_path: Path
    manifest_path: Path = Path(".artifacts/T047/corpus-selection.json")
    seed: int = Field(ge=0)
    snapshot_cutoff: str = Field(min_length=1)
    selection_rationale: str = Field(min_length=1)
    min_year: int = Field(ge=1900)
    max_year: int = Field(ge=1900)
    allowed_languages: tuple[str, ...] = ("en",)
    allowed_document_types: tuple[str, ...] = ("journal-article",)
    allowed_reuse_classes: tuple[str, ...] = ("open", "unknown")
    enriched_tags: tuple[str, ...] = (
        "ambiguous",
        "caption",
        "nested",
        "overlap",
        "rare-form",
        "table",
    )
    broad_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    broad_max_groups: int | None = Field(default=None, ge=1)
    enriched_max_groups: int = Field(default=0, ge=0)
    protected_record_ids: tuple[str, ...] = ()
    final_release_includes_selected: bool = True
    near_duplicate_jaccard: float = Field(default=0.98, ge=0.0, le=1.0)
    work_scale_limits: WorkScaleLimits = WorkScaleLimits()

    @model_validator(mode="after")
    def validate_policy(self) -> CorpusSelectionConfig:
        if self.max_year < self.min_year:
            raise ValueError("max_year must not be less than min_year")
        if not self.allowed_languages:
            raise ValueError("allowed_languages must not be empty")
        if self.broad_fraction == 0.0 and self.broad_max_groups is None:
            raise ValueError("broad selection requires a fraction or max_groups")
        if len(set(self.protected_record_ids)) != len(self.protected_record_ids):
            raise ValueError("protected_record_ids must be unique")
        return self


@dataclass(frozen=True, slots=True)
class CorpusArticleGroup:
    group_id: str
    records: tuple[CorpusFrameRecord, ...]


@dataclass(frozen=True, slots=True)
class CorpusSelectionResult:
    config: CorpusSelectionConfig
    frame_fingerprint: str
    groups: tuple[CorpusArticleGroup, ...]
    assignments: tuple[dict[str, object], ...]
    summary: dict[str, object]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CORPUS_SELECTION_SCHEMA_VERSION,
            "config": self.config.model_dump(mode="json"),
            "frame_fingerprint": self.frame_fingerprint,
            "groups": [
                {
                    "group_id": group.group_id,
                    "record_ids": [record.record_id for record in group.records],
                    "pmids": sorted({r.pmid for r in group.records if r.pmid}),
                    "pmcids": sorted({r.pmcid for r in group.records if r.pmcid}),
                    "source_versions": sorted(
                        {
                            value
                            for record in group.records
                            for value in (record.source_version, record.source_sha256)
                            if value
                        }
                    ),
                    "source_kinds": sorted({r.source_kind for r in group.records}),
                }
                for group in self.groups
            ],
            "assignments": list(self.assignments),
            "summary": self.summary,
            "limitations": list(self.limitations),
        }


def _normalized(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _key(record: CorpusFrameRecord) -> tuple[str, ...]:
    keys = []
    if record.pmid:
        keys.append("pmid:" + record.pmid.strip().casefold())
    if record.pmcid:
        value = record.pmcid.strip().casefold()
        keys.append("pmcid:" + value.removeprefix("pmc"))
    if record.text.strip():
        keys.append(
            "content:" + hashlib.sha256(_normalized(record.text).encode()).hexdigest()
        )
    return tuple(keys)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", _normalized(text)))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _group_records(
    records: Sequence[CorpusFrameRecord], threshold: float
) -> tuple[CorpusArticleGroup, ...]:
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    seen: dict[str, int] = {}
    token_sets = [_tokens(record.text) for record in records]
    for index, record in enumerate(records):
        for key in _key(record):
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index
    for left in range(len(records)):
        for right in range(left):
            if (
                token_sets[left]
                and _jaccard(token_sets[left], token_sets[right]) >= threshold
            ):
                union(left, right)
    grouped: dict[int, list[CorpusFrameRecord]] = defaultdict(list)
    for index, record in enumerate(records):
        grouped[find(index)].append(record)
    result = []
    for members in grouped.values():
        stable = "|".join(sorted(key for record in members for key in _key(record)))
        group_id = "article-group-" + hashlib.sha256(stable.encode()).hexdigest()[:16]
        result.append(
            CorpusArticleGroup(
                group_id, tuple(sorted(members, key=lambda r: r.record_id))
            )
        )
    return tuple(sorted(result, key=lambda group: group.group_id))


def _load_frame(path: Path) -> tuple[CorpusFrameRecord, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise CorpusSelectionError(
            f"Unable to read corpus frame {path}: {error}"
        ) from error
    records: list[CorpusFrameRecord] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise TypeError("record must be an object")
            records.append(CorpusFrameRecord.model_validate(value))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise CorpusSelectionError(
                f"invalid frame line {number}: {error}"
            ) from error
    if not records:
        raise CorpusSelectionError("corpus frame must contain at least one record")
    if len({record.record_id for record in records}) != len(records):
        raise CorpusSelectionError("corpus frame record_id values must be unique")
    return tuple(records)


def _rank(seed: int, group_id: str) -> str:
    return hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest()


def _exclusion_reason(
    group: CorpusArticleGroup, config: CorpusSelectionConfig, protected: set[str]
) -> str | None:
    records = group.records
    if any(record.record_id in protected for record in records):
        return "evaluation-holdout"
    if not any(record.available for record in records):
        return "unavailable"
    if any(record.language not in config.allowed_languages for record in records):
        return "language"
    if any(
        record.document_type not in config.allowed_document_types for record in records
    ):
        return "document-type"
    if any(
        record.reuse_class not in config.allowed_reuse_classes for record in records
    ):
        return "reuse-class"
    years = [record.year for record in records if record.year is not None]
    if not years:
        return "missing-year"
    if not any(config.min_year <= year <= config.max_year for year in years):
        return "year-range"
    return None


def select_corpus(
    config: CorpusSelectionConfig, frame_path: Path | None = None
) -> CorpusSelectionResult:
    """Select roles from a local metadata frame without fetching or processing text."""

    selected_path = frame_path or config.frame_path
    records = _load_frame(selected_path)
    groups = _group_records(records, config.near_duplicate_jaccard)
    protected = set(config.protected_record_ids)
    reasons = {
        group.group_id: _exclusion_reason(group, config, protected) for group in groups
    }
    eligible = [group for group in groups if reasons[group.group_id] is None]
    enriched_candidates = [
        group
        for group in eligible
        if any(
            tag in config.enriched_tags
            for record in group.records
            for tag in record.challenge_tags
        )
    ]
    enriched_candidate_ids = {group.group_id for group in enriched_candidates}
    ranked = sorted(
        (group for group in eligible if group.group_id not in enriched_candidate_ids),
        key=lambda group: _rank(config.seed, group.group_id),
    )
    broad_count = (
        config.broad_max_groups
        if config.broad_max_groups is not None
        else int(len(ranked) * config.broad_fraction)
    )
    broad = tuple(ranked[:broad_count])
    broad_ids = {group.group_id for group in broad}
    enriched = tuple(
        sorted(
            (group for group in enriched_candidates if group.group_id not in broad_ids),
            key=lambda group: _rank(config.seed, "enriched:" + group.group_id),
        )[: config.enriched_max_groups]
    )
    enriched_ids = {group.group_id for group in enriched}
    release_ids = (
        (broad_ids | enriched_ids) if config.final_release_includes_selected else set()
    )
    broad_probability = (len(broad) / len(eligible)) if eligible else 0.0
    assignments: list[dict[str, object]] = []
    for record in records:
        group = next(
            group
            for group in groups
            if record.record_id in {r.record_id for r in group.records}
        )
        reason = reasons[group.group_id]
        memberships: list[str] = []
        if group.group_id in broad_ids:
            memberships.append("discovery")
        if group.group_id in enriched_ids:
            memberships.append("enriched")
        if group.group_id in release_ids:
            memberships.append("tagged-release")
        if reason is not None:
            role = "excluded:" + reason
            selection_reason = reason
        elif not memberships:
            role = "eligible-not-selected"
            selection_reason = "outside-configured-pool-cap"
        else:
            role = memberships[0]
            selection_reason = (
                "challenge-priority"
                if "enriched" in memberships
                else "seeded-broad-rank"
            )
        assignments.append(
            {
                "record_id": record.record_id,
                "group_id": group.group_id,
                "role": role,
                "pool_memberships": memberships,
                "available": record.available,
                "selection_reason": selection_reason,
                "selection_probability": broad_probability
                if "discovery" in memberships
                else None,
                "evaluation_inference_only": reason == "evaluation-holdout",
            }
        )
    source_kind_counts = Counter(record.source_kind for record in records)
    year_counts = Counter(
        str(record.year) if record.year is not None else "unknown" for record in records
    )
    language_counts = Counter(record.language for record in records)
    document_type_counts = Counter(record.document_type for record in records)
    reuse_class_counts = Counter(record.reuse_class for record in records)
    structure_tag_counts = Counter(
        tag for record in records for tag in record.challenge_tags
    )
    tagged_structure_groups = sum(
        any(
            tag in config.enriched_tags
            for record in group.records
            for tag in record.challenge_tags
        )
        for group in groups
    )
    exclusion_counts = Counter(
        str(item["role"]).removeprefix("excluded:")
        for item in assignments
        if str(item["role"]).startswith("excluded:")
    )
    selected_groups = broad + enriched
    estimated_bytes = sum(
        len(record.text.encode("utf-8"))
        for group in selected_groups
        for record in group.records
        if record.available
    )
    estimated_minutes = (
        len(selected_groups) / config.work_scale_limits.estimated_documents_per_minute
    )
    summary: dict[str, object] = {
        "snapshot_cutoff": config.snapshot_cutoff,
        "selection_rationale": config.selection_rationale,
        "frame_records": len(records),
        "article_groups": len(groups),
        "eligible_groups": len(eligible),
        "eligible_group_fraction": round(len(eligible) / len(groups), 6),
        "enriched_candidate_groups": len(enriched_candidates),
        "tagged_structure_groups": tagged_structure_groups,
        "selected_group_counts": {
            "discovery": len(broad),
            "enriched": len(enriched),
            "tagged-release": len(release_ids),
        },
        "selected_record_counts": {
            "discovery": sum(len(group.records) for group in broad),
            "enriched": sum(len(group.records) for group in enriched),
            "tagged-release": sum(len(group.records) for group in selected_groups),
        },
        "exclusion_group_counts": dict(sorted(exclusion_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "year_counts": dict(sorted(year_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "document_type_counts": dict(sorted(document_type_counts.items())),
        "reuse_class_counts": dict(sorted(reuse_class_counts.items())),
        "structure_tag_counts": dict(sorted(structure_tag_counts.items())),
        "estimated_selected_text_bytes": estimated_bytes,
        "estimated_selected_runtime_minutes": round(estimated_minutes, 3),
        "work_scale_limits": config.work_scale_limits.model_dump(mode="json"),
        "protected_record_ids": sorted(protected),
    }
    limitations = (
        "This is a bounded metadata-frame proposal; no bulk retrieval or resolver "
        "processing was run.",
        "Selection probabilities apply only to the seeded broad pool; enriched "
        "examples have a separate denominator.",
        "T029/T030 protected groups are excluded by identifier closure, including "
        "abstract/full-text counterparts.",
        "Work-scale runtime and storage are estimates until T041 measures real "
        "acquisition and processing costs.",
    )
    return CorpusSelectionResult(
        config,
        hashlib.sha256(selected_path.read_bytes()).hexdigest(),
        groups,
        tuple(sorted(assignments, key=lambda item: str(item["record_id"]))),
        summary,
        limitations,
    )


def load_corpus_selection_config(path: Path) -> CorpusSelectionConfig:
    """Load and validate the YAML corpus-selection section."""

    try:
        raw = load_config_layer(path)
        section = raw.get("corpus_selection")
        if not isinstance(section, Mapping):
            raise CorpusSelectionError(
                "configuration must contain a 'corpus_selection' mapping"
            )
        return CorpusSelectionConfig.model_validate(section)
    except CorpusSelectionError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise CorpusSelectionError(
            f"invalid corpus-selection configuration: {error}"
        ) from error


def write_corpus_selection_manifest(result: CorpusSelectionResult, path: Path) -> str:
    """Write a stable frozen manifest and return its content fingerprint."""

    payload = (
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "CORPUS_SELECTION_SCHEMA_VERSION",
    "CorpusArticleGroup",
    "CorpusFrameRecord",
    "CorpusSelectionConfig",
    "CorpusSelectionError",
    "CorpusSelectionResult",
    "WorkScaleLimits",
    "load_corpus_selection_config",
    "select_corpus",
    "write_corpus_selection_manifest",
]
