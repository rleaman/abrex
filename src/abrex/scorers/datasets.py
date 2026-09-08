"""Leakage-safe candidate feature/label dataset materialization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from abrex.candidates import CandidateArtifact
from abrex.domain import CorpusRecord, Document, TextSpan
from abrex.features import ConfiguredFeatureSet, FeatureMatrix
from abrex.scorers.splits import SplitDatasets, SplitManifest, partition_dataset


class LabelConstructionConfig(BaseModel):
    """Explicit label policy; incomplete annotations never create negatives."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    partial_annotation_policy: Literal["abstain"] = "abstain"
    include_silver: bool = False


@dataclass(frozen=True, slots=True)
class CandidateLabel:
    """A label joined to one stable feature-row key with origin lineage."""

    document_id: str
    candidate_index: int
    value: float
    origin: Literal["gold", "silver"]
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrainingDatasetArtifact:
    """Materialized labeled rows and split datasets with reproducibility data."""

    features: FeatureMatrix
    labels: tuple[CandidateLabel, ...]
    splits: SplitDatasets
    candidate_fingerprint: str
    dataset_fingerprint: str


def materialize_training_dataset(
    artifact: CandidateArtifact,
    documents: dict[str, Document],
    records: dict[str, CorpusRecord],
    feature_set: ConfiguredFeatureSet,
    manifest: SplitManifest,
    *,
    config: LabelConstructionConfig | None = None,
    silver_labels: dict[tuple[str, TextSpan, TextSpan], tuple[float, tuple[str, ...]]]
    | None = None,
) -> TrainingDatasetArtifact:
    """Build rows from complete gold pairs, optionally supplied silver labels.

    Unmatched candidates are omitted rather than treated as negative because
    source annotations may be partial. The feature set receives only documents
    and candidates, never labels or corpus records.
    """

    policy = config or LabelConstructionConfig()
    feature_matrix = feature_set.extract_artifact(artifact, documents)
    labels: list[CandidateLabel] = []
    values: list[float] = []
    selected_rows = []
    for row in feature_matrix.rows:
        record = records.get(row.document_id)
        if record is None:
            raise ValueError(f"No corpus record for {row.document_id!r}")
        exact_gold = {
            (item.short_form, item.long_form)
            for item in record.gold_annotations
            if item.short_form is not None and item.long_form is not None
        }
        if (row.candidate.short_form, row.candidate.long_form) in exact_gold:
            label = CandidateLabel(row.document_id, row.candidate_index, 1.0, "gold")
        else:
            silver = (silver_labels or {}).get(
                (row.document_id, row.candidate.short_form, row.candidate.long_form)
            )
            if not policy.include_silver or silver is None:
                continue
            value, evidence_ids = silver
            if value not in (0.0, 1.0):
                raise ValueError("silver labels must be binary 0.0 or 1.0")
            label = CandidateLabel(
                row.document_id, row.candidate_index, value, "silver", evidence_ids
            )
        labels.append(label)
        values.append(label.value)
        selected_rows.append(row)
    selected_features = FeatureMatrix(feature_matrix.schema, tuple(selected_rows))
    split_datasets = partition_dataset(selected_features, tuple(values), manifest)
    candidate_fingerprint = _fingerprint(artifact)
    dataset_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "candidate_fingerprint": candidate_fingerprint,
                "feature_schema": feature_matrix.schema.as_dict(),
                "rows": [
                    (label.document_id, label.candidate_index, label.value)
                    for label in labels
                ],
                "split": manifest.model_dump(mode="json"),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return TrainingDatasetArtifact(
        selected_features,
        tuple(labels),
        split_datasets,
        candidate_fingerprint,
        dataset_fingerprint,
    )


def _fingerprint(artifact: CandidateArtifact) -> str:
    payload = repr(artifact).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "CandidateLabel",
    "LabelConstructionConfig",
    "TrainingDatasetArtifact",
    "materialize_training_dataset",
]
