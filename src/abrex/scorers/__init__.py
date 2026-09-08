"""Registry-driven supervised candidate scoring infrastructure.

T015 intentionally supplies no scientific model or label policy. Applications
register a scorer, provide explicit split/label artifacts, and choose any
calibration and selection policy through configuration.
"""

from abrex.scorers.artifacts import (
    ScorerArtifactError,
    fingerprint_feature_schema,
    load_scorer_artifact,
    write_scorer_artifact,
)
from abrex.scorers.base import (
    SCORER_ARTIFACT_SCHEMA_VERSION,
    SPLIT_MANIFEST_SCHEMA_VERSION,
    Calibrator,
    PersistableScorer,
    ScoredCandidate,
    Scorer,
    ScorerArtifact,
    ScoringDataset,
    SelectionPolicy,
)
from abrex.scorers.config import (
    ScorerConfig,
    create_scorer_executor,
    scorer_config_from_resolved,
)
from abrex.scorers.datasets import (
    CandidateLabel,
    LabelConstructionConfig,
    TrainingDatasetArtifact,
    materialize_training_dataset,
)
from abrex.scorers.execution import ScorerExecutor, derive_child_seed
from abrex.scorers.materialization import (
    materialize_feature_predictions,
    materialize_predictions,
)
from abrex.scorers.registry import (
    CALIBRATORS,
    SCORERS,
    SELECTION_POLICIES,
    register_builtin_components,
)
from abrex.scorers.splits import (
    SplitDatasets,
    SplitManifest,
    partition_dataset,
    read_split_manifest,
)
from abrex.scorers.strategies import FixedThreshold, IdentityCalibrator

__all__ = [
    "CALIBRATORS",
    "CandidateLabel",
    "Calibrator",
    "FixedThreshold",
    "IdentityCalibrator",
    "LabelConstructionConfig",
    "PersistableScorer",
    "SCORER_ARTIFACT_SCHEMA_VERSION",
    "SCORERS",
    "SPLIT_MANIFEST_SCHEMA_VERSION",
    "SELECTION_POLICIES",
    "ScoredCandidate",
    "Scorer",
    "ScorerArtifact",
    "ScorerArtifactError",
    "ScorerConfig",
    "ScorerExecutor",
    "ScoringDataset",
    "SelectionPolicy",
    "SplitDatasets",
    "SplitManifest",
    "TrainingDatasetArtifact",
    "create_scorer_executor",
    "derive_child_seed",
    "fingerprint_feature_schema",
    "load_scorer_artifact",
    "materialize_feature_predictions",
    "materialize_predictions",
    "materialize_training_dataset",
    "partition_dataset",
    "read_split_manifest",
    "register_builtin_components",
    "scorer_config_from_resolved",
    "write_scorer_artifact",
]
