"""Tests for the T010 experiment application service."""

from __future__ import annotations

import json
from pathlib import Path

from abrex.experiments import run_experiment


def test_toy_experiment_reuses_validated_predictions(tmp_path: Path) -> None:
    config = Path("docs/examples/experiment-toy.yaml")
    first = run_experiment(
        (config,), output_root=tmp_path, reuse_cached_predictions=True
    )
    second = run_experiment(
        (config,), output_root=tmp_path, reuse_cached_predictions=True
    )

    assert first.reused_predictions is False
    assert second.reused_predictions is True
    assert first.prediction_fingerprint == second.prediction_fingerprint
    assert first.evaluation_fingerprint == second.evaluation_fingerprint
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "run-manifest-v1"
    assert manifest["predictions"]["reused"] is True
    assert manifest["corpus"]["fingerprint"] == first.corpus_fingerprint


def test_invalid_prediction_cache_is_recomputed(tmp_path: Path) -> None:
    config = Path("docs/examples/experiment-toy.yaml")
    first = run_experiment(
        (config,), output_root=tmp_path, reuse_cached_predictions=True
    )
    first.prediction_path.write_text("not-json\n", encoding="utf-8")

    second = run_experiment(
        (config,), output_root=tmp_path, reuse_cached_predictions=True
    )

    assert second.reused_predictions is False
    assert second.prediction_fingerprint == first.prediction_fingerprint
