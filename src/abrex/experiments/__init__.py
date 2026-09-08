"""Declarative experiment execution and reproducibility metadata."""

from abrex.experiments.runner import ExperimentError, ExperimentResult, run_experiment
from abrex.experiments.sharded import (
    ShardedProcessingConfig,
    ShardedRunResult,
    run_sharded,
    shard_for_document,
)

__all__ = [
    "ExperimentError",
    "ExperimentResult",
    "ShardedProcessingConfig",
    "ShardedRunResult",
    "run_experiment",
    "run_sharded",
    "shard_for_document",
]
