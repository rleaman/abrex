"""Deterministic contemporary article sampling and leakage controls.

This module creates reviewable *proposals*.  It does not establish a final
scientific train/dev/test protocol.  Article identity, availability and
teacher-overlap facts are supplied by the frame and retained in the manifest;
the sampler never infers them from resolver output.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.config import load_config_layer
from abrex.resources import FrequencyResource

SAMPLING_SCHEMA_VERSION = "contemporary-sampling-v1"
_WHITESPACE = re.compile(r"\s+")


class SamplingError(ValueError):
    """Raised when a sampling frame or proposal is malformed."""


class SamplingRoleConfig(BaseModel):
    """One explicit proposal role and its selection policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    strategy: Literal["random", "challenge"] = "random"
    fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    max_groups: int | None = Field(default=None, ge=1)
    lexicon_allowed: bool = False

    @model_validator(mode="after")
    def validate_policy(self) -> SamplingRoleConfig:
        if self.strategy == "challenge" and self.fraction != 0.0:
            raise ValueError("challenge roles use max_groups, not fraction")
        if (
            self.strategy == "random"
            and self.fraction == 0.0
            and self.max_groups is None
        ):
            raise ValueError("random roles require fraction or max_groups")
        return self


class SamplingConfig(BaseModel):
    """Typed configuration for a deterministic, reviewable frame proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_path: Path
    manifest_path: Path = Path(".artifacts/T029/sampling-manifest.json")
    seed: int = Field(ge=0)
    mode: Literal["proposal"] = "proposal"
    roles: tuple[SamplingRoleConfig, ...] = Field(min_length=1)
    near_duplicate_jaccard: float = Field(default=0.98, ge=0.0, le=1.0)
    target_years: tuple[int, ...] = ()
    frequency_resource_path: Path | None = None

    @model_validator(mode="after")
    def validate_roles(self) -> SamplingConfig:
        names = [role.name for role in self.roles]
        if len(set(names)) != len(names):
            raise ValueError("sampling role names must be unique")
        random_fraction = sum(
            role.fraction for role in self.roles if role.strategy == "random"
        )
        if random_fraction > 1.0 + 1e-9:
            raise ValueError("random role fractions must sum to at most 1")
        return self


class FrameRecord(BaseModel):
    """One article candidate in a local, source-backed sampling frame."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    text: str = ""
    pmid: str | None = None
    pmcid: str | None = None
    source_sha256: str | None = None
    source_kind: Literal["abstract", "full_text", "unknown"] = "unknown"
    year: int | None = None
    available: bool = True
    official_split: str | None = None
    teacher_overlap: Literal["yes", "no", "unknown"] = "unknown"
    challenge_tags: tuple[str, ...] = ()
    occurrence_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_identifiers(self) -> FrameRecord:
        if self.pmid is None and self.pmcid is None and not self.text.strip():
            raise ValueError("frame records need an identifier or text")
        for name, value in (("pmid", self.pmid), ("pmcid", self.pmcid)):
            if value is not None and not value.strip():
                raise ValueError(f"{name} must be non-empty or null")
        if self.source_sha256 is not None and (
            len(self.source_sha256) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a 64-character hexadecimal digest")
        if any(not value.strip() for value in self.challenge_tags):
            raise ValueError("challenge_tags must not contain empty values")
        if any(not value.strip() for value in self.occurrence_keys):
            raise ValueError("occurrence_keys must not contain empty values")
        return self


@dataclass(frozen=True, slots=True)
class ArticleGroup:
    """A duplicate-safe group that must remain in one partition."""

    group_id: str
    record_ids: tuple[str, ...]
    pmids: tuple[str, ...]
    pmcids: tuple[str, ...]
    source_kinds: tuple[str, ...]
    official_splits: tuple[str, ...]
    available_count: int
    unavailable_count: int
    teacher_overlap: str
    challenge_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SamplingResult:
    """A deterministic proposal plus accounting needed for review."""

    config: SamplingConfig
    frame_fingerprint: str
    groups: tuple[ArticleGroup, ...]
    assignments: tuple[dict[str, object], ...]
    occurrence_links: tuple[dict[str, object], ...]
    frequency_priorities: dict[str, int]
    summary: dict[str, object]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the proposal with stable ordering and provenance."""

        return {
            "schema_version": SAMPLING_SCHEMA_VERSION,
            "mode": self.config.mode,
            "seed": self.config.seed,
            "config": self.config.model_dump(mode="json"),
            "frame_fingerprint": self.frame_fingerprint,
            "groups": [
                {
                    "group_id": group.group_id,
                    "record_ids": list(group.record_ids),
                    "pmids": list(group.pmids),
                    "pmcids": list(group.pmcids),
                    "source_kinds": list(group.source_kinds),
                    "official_splits": list(group.official_splits),
                    "available_count": group.available_count,
                    "unavailable_count": group.unavailable_count,
                    "teacher_overlap": group.teacher_overlap,
                    "challenge_tags": list(group.challenge_tags),
                }
                for group in self.groups
            ],
            "assignments": list(self.assignments),
            "occurrence_links": list(self.occurrence_links),
            "frequency_priorities": self.frequency_priorities,
            "summary": self.summary,
            "limitations": list(self.limitations),
        }


def _normalized_text(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _identifier_key(value: str, prefix: str) -> str:
    normalized = value.strip().casefold()
    if prefix == "pmcid" and normalized.startswith("pmc"):
        normalized = normalized[3:]
    return f"{prefix}:{normalized}"


def _content_key(record: FrameRecord) -> str | None:
    normalized = _normalized_text(record.text)
    if not normalized:
        return None
    return "content:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", _normalized_text(text)))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _group_records(
    records: Sequence[FrameRecord], threshold: float
) -> tuple[ArticleGroup, ...]:
    union_find = _UnionFind(len(records))
    keys: dict[str, int] = {}
    token_sets: list[set[str]] = []
    for index, record in enumerate(records):
        record_keys = [
            key
            for key in (
                _identifier_key(record.pmid, "pmid") if record.pmid else None,
                _identifier_key(record.pmcid, "pmcid") if record.pmcid else None,
                _content_key(record),
            )
            if key is not None
        ]
        for key in record_keys:
            previous = keys.setdefault(key, index)
            union_find.union(index, previous)
        token_sets.append(_token_set(record.text))
    for left in range(len(records)):
        if not token_sets[left]:
            continue
        for right in range(left):
            if _jaccard(token_sets[left], token_sets[right]) >= threshold:
                union_find.union(left, right)

    members: dict[int, list[FrameRecord]] = defaultdict(list)
    for index, record in enumerate(records):
        members[union_find.find(index)].append(record)
    groups: list[ArticleGroup] = []
    for group_records in members.values():
        ids = tuple(sorted(record.record_id for record in group_records))
        stable_key = "|".join(
            sorted(
                key
                for record in group_records
                for key in (
                    _identifier_key(record.pmid, "pmid") if record.pmid else None,
                    _identifier_key(record.pmcid, "pmcid") if record.pmcid else None,
                    _content_key(record),
                )
                if key is not None
            )
        )
        group_id = (
            "article-group-" + hashlib.sha256(stable_key.encode()).hexdigest()[:16]
        )
        official = tuple(
            sorted({r.official_split for r in group_records if r.official_split})
        )
        if len(official) > 1:
            raise SamplingError(
                f"group {group_id} has conflicting official splits: {official}"
            )
        overlap = (
            "yes"
            if any(r.teacher_overlap == "yes" for r in group_records)
            else (
                "unknown"
                if any(r.teacher_overlap == "unknown" for r in group_records)
                else "no"
            )
        )
        groups.append(
            ArticleGroup(
                group_id,
                ids,
                tuple(sorted({r.pmid for r in group_records if r.pmid})),
                tuple(sorted({r.pmcid for r in group_records if r.pmcid})),
                tuple(sorted({r.source_kind for r in group_records})),
                official,
                sum(r.available for r in group_records),
                sum(not r.available for r in group_records),
                overlap,
                tuple(sorted({tag for r in group_records for tag in r.challenge_tags})),
            )
        )
    return tuple(sorted(groups, key=lambda group: group.group_id))


def _rank(seed: int, group_id: str) -> str:
    return hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest()


def _load_frame(path: Path) -> tuple[FrameRecord, ...]:
    records: list[FrameRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise SamplingError(f"Unable to read sampling frame {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if not isinstance(data, Mapping):
                raise TypeError("record must be an object")
            record = FrameRecord.model_validate(data)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SamplingError(f"Invalid frame line {line_number}: {error}") from error
        records.append(record)
    if not records:
        raise SamplingError("sampling frame must contain at least one record")
    if len({record.record_id for record in records}) != len(records):
        raise SamplingError("sampling frame record_id values must be unique")
    return tuple(records)


def _select_groups(
    groups: Sequence[ArticleGroup], config: SamplingConfig
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    available = [
        group
        for group in groups
        if group.available_count and group.teacher_overlap != "yes"
    ]
    for group in groups:
        if group.official_splits:
            assignments[group.group_id] = f"official:{group.official_splits[0]}"
        elif group.unavailable_count == len(group.record_ids):
            assignments[group.group_id] = "unavailable"
        elif group.teacher_overlap == "yes":
            assignments[group.group_id] = "excluded:teacher-overlap"
    available = [group for group in available if group.group_id not in assignments]
    challenge_roles = [role for role in config.roles if role.strategy == "challenge"]
    random_roles = [role for role in config.roles if role.strategy == "random"]
    challenge_groups = sorted(
        (group for group in available if group.challenge_tags),
        key=lambda group: _rank(config.seed, "challenge:" + group.group_id),
    )
    remaining = {group.group_id: group for group in available}
    for role in challenge_roles:
        count = role.max_groups or 0
        for group in challenge_groups[:count]:
            if group.group_id in remaining:
                assignments[group.group_id] = role.name
                remaining.pop(group.group_id)
    random_pool = sorted(
        remaining.values(), key=lambda group: _rank(config.seed, group.group_id)
    )
    cursor = 0
    for role in random_roles:
        requested = role.max_groups
        if requested is None:
            requested = int(len(available) * role.fraction)
        selected = random_pool[cursor : cursor + requested]
        assignments.update({group.group_id: role.name for group in selected})
        cursor += len(selected)
    for group in groups:
        assignments.setdefault(group.group_id, "not-selected")
    return assignments


def sample_frame(
    config: SamplingConfig, frame_path: Path | None = None
) -> SamplingResult:
    """Group and assign a local frame without consulting resolver detections."""

    selected_path = frame_path or config.frame_path
    records = _load_frame(selected_path)
    frame_bytes = selected_path.read_bytes()
    frame_fingerprint = hashlib.sha256(frame_bytes).hexdigest()
    groups = _group_records(records, config.near_duplicate_jaccard)
    group_by_record = {
        record_id: group for group in groups for record_id in group.record_ids
    }
    assignments = _select_groups(groups, config)
    role_configs = {role.name: role for role in config.roles}
    record_assignments: list[dict[str, object]] = []
    occurrence_to_records: dict[str, list[str]] = defaultdict(list)
    for record in records:
        group = group_by_record[record.record_id]
        role = assignments[group.group_id]
        role_config = role_configs.get(role)
        lexicon_allowed = bool(role_config and role_config.lexicon_allowed)
        if role.startswith("official:") or role.startswith("excluded:"):
            lexicon_allowed = False
        probability = (
            1.0
            / sum(
                1
                for candidate in groups
                if candidate.available_count and candidate.teacher_overlap != "yes"
            )
            if role_config and role_config.strategy == "random"
            else None
        )
        record_assignments.append(
            {
                "record_id": record.record_id,
                "group_id": group.group_id,
                "role": role,
                "available": record.available,
                "teacher_overlap": group.teacher_overlap,
                "official_split": group.official_splits[0]
                if group.official_splits
                else None,
                "sampling_probability": probability,
                "lexicon_allowed": lexicon_allowed,
            }
        )
        if record.available:
            for occurrence in record.occurrence_keys:
                if lexicon_allowed:
                    occurrence_to_records[occurrence].append(record.record_id)
    occurrence_links = tuple(
        {"key": key, "record_ids": sorted(values), "lexicon_allowed": True}
        for key, values in sorted(occurrence_to_records.items())
    )
    frequency_priorities: dict[str, int] = {}
    if config.frequency_resource_path is not None:
        try:
            resource = FrequencyResource(config.frequency_resource_path)
            for link in occurrence_links:
                short_form = str(link["key"]).split("|", maxsplit=1)[0]
                frequency_priorities[short_form] = sum(
                    variant.count for variant in resource.lookup(short_form)
                )
        except (OSError, ValueError, IndexError, sqlite3.Error) as error:
            raise SamplingError(
                "Unable to query configured frequency resource "
                f"{config.frequency_resource_path}: {error}"
            ) from error
    source_kind_counts: dict[str, int] = defaultdict(int)
    year_counts: dict[str, int] = defaultdict(int)
    for record in records:
        source_kind_counts[record.source_kind] += 1
        year_counts[str(record.year) if record.year is not None else "unknown"] += 1
    role_counts: dict[str, int] = defaultdict(int)
    for assignment in record_assignments:
        role_counts[str(assignment["role"])] += 1
    summary = {
        "frame_records": len(records),
        "frame_available_records": sum(record.available for record in records),
        "frame_unavailable_records": sum(not record.available for record in records),
        "article_groups": len(groups),
        "assigned_groups": sum(role != "not-selected" for role in assignments.values()),
        "role_record_counts": dict(sorted(role_counts.items())),
        "unavailable_texts": sum(group.unavailable_count for group in groups),
        "unknown_teacher_overlap_groups": sum(
            group.teacher_overlap == "unknown" for group in groups
        ),
        "occurrence_link_count": len(occurrence_links),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "year_counts": dict(sorted(year_counts.items())),
        "target_years": list(config.target_years),
        "frequency_priority_short_forms": len(frequency_priorities),
    }
    limitations = (
        (
            "This is a proposal; role fractions and target years require scientific "
            "review."
        ),
        "Unavailable texts and unknown teacher overlap are reported, not imputed.",
        (
            "Challenge selections are deliberately selected and must not enter "
            "population-weighted estimates."
        ),
        (
            "Occurrence links come only from supplied sampled-frame metadata; "
            "aggregate frequency counts do not establish article locations."
        ),
        "No benchmark claim is made from Ab3P-only selection or labels.",
    )
    return SamplingResult(
        config,
        frame_fingerprint,
        groups,
        tuple(sorted(record_assignments, key=lambda item: str(item["record_id"]))),
        occurrence_links,
        dict(sorted(frequency_priorities.items())),
        summary,
        limitations,
    )


def load_sampling_config(path: Path) -> SamplingConfig:
    """Load and validate the YAML sampling section."""

    try:
        raw = load_config_layer(path)
        section = raw.get("sampling")
        if not isinstance(section, Mapping):
            raise SamplingError(
                "sampling configuration must contain a 'sampling' mapping"
            )
        return SamplingConfig.model_validate(section)
    except SamplingError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise SamplingError(
            f"Invalid sampling configuration {path}: {error}"
        ) from error


def write_sampling_manifest(result: SamplingResult, path: Path) -> str:
    """Write a deterministic proposal manifest and return its content hash."""

    payload = (
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_lexicon_view(result: SamplingResult) -> dict[str, tuple[str, ...]]:
    """Return occurrence links eligible for induction, excluding held-out roles."""

    return {
        str(link["key"]): tuple(
            str(record_id) for record_id in cast(Sequence[object], link["record_ids"])
        )
        for link in result.occurrence_links
        if link.get("lexicon_allowed") is True
    }


__all__ = [
    "SAMPLING_SCHEMA_VERSION",
    "ArticleGroup",
    "FrameRecord",
    "SamplingConfig",
    "SamplingError",
    "SamplingResult",
    "SamplingRoleConfig",
    "derive_lexicon_view",
    "load_sampling_config",
    "sample_frame",
    "write_sampling_manifest",
]
