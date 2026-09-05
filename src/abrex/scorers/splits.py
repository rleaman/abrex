"""Explicit document-level train/dev/test split manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.features import FeatureMatrix, FeatureRow
from abrex.scorers.base import SPLIT_MANIFEST_SCHEMA_VERSION, ScoringDataset


class SplitManifest(BaseModel):
    """Checked-in document assignments consumed without inventing splits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SPLIT_MANIFEST_SCHEMA_VERSION
    train: tuple[str, ...] = Field(min_length=1)
    dev: tuple[str, ...] = ()
    test: tuple[str, ...] = ()
    dataset_fingerprint: str | None = None

    @model_validator(mode="after")
    def validate_assignments(self) -> SplitManifest:
        assignments = (self.train, self.dev, self.test)
        if any(
            not document_id.strip() for split in assignments for document_id in split
        ):
            raise ValueError("Split document IDs must not be empty")
        flattened = [document_id for split in assignments for document_id in split]
        if len(set(flattened)) != len(flattened):
            raise ValueError("A document may occur in only one split")
        if self.schema_version != SPLIT_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported split manifest schema: {self.schema_version}"
            )
        return self

    def split_for(self, document_id: str) -> str:
        """Return the declared split or raise for an unassigned document."""

        for name, values in (
            ("train", self.train),
            ("dev", self.dev),
            ("test", self.test),
        ):
            if document_id in values:
                return name
        raise ValueError(f"Document {document_id!r} is absent from split manifest")


@dataclass(frozen=True, slots=True)
class SplitDatasets:
    """Feature/label datasets partitioned by the supplied manifest."""

    train: ScoringDataset
    dev: ScoringDataset | None
    test: ScoringDataset | None


def read_split_manifest(path: Path) -> SplitManifest:
    """Read a JSON split manifest and validate it at the application boundary."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read split manifest {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("Split manifest root must be an object")
    return SplitManifest.model_validate(data)


def partition_dataset(
    features: FeatureMatrix,
    labels: tuple[float, ...],
    manifest: SplitManifest,
) -> SplitDatasets:
    """Partition rows by document IDs, preserving artifact row order."""

    if len(labels) != len(features.rows):
        raise ValueError("Labels must match feature rows before partitioning")
    buckets: dict[str, list[FeatureRow]] = {"train": [], "dev": [], "test": []}
    label_buckets: dict[str, list[float]] = {"train": [], "dev": [], "test": []}
    for row, label in zip(features.rows, labels, strict=True):
        split = manifest.split_for(row.document_id)
        buckets[split].append(row)
        label_buckets[split].append(float(label))

    def build(name: str) -> ScoringDataset | None:
        if not buckets[name]:
            return None
        return ScoringDataset(
            name,
            FeatureMatrix(features.schema, tuple(buckets[name])),
            tuple(label_buckets[name]),
        )

    train = build("train")
    if train is None:
        raise ValueError("Split manifest produced no training rows")
    return SplitDatasets(train, build("dev"), build("test"))


__all__ = ["SplitDatasets", "SplitManifest", "partition_dataset", "read_split_manifest"]
