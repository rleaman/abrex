"""Regression tests for the frozen T057 canonical challenge materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from abrex.corpora import read_canonical_dataset


def _module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "materialize_t057_challenge.py"
    spec = importlib.util.spec_from_file_location("materialize_t057_challenge", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_materializes_all_frozen_challenge_cases(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    output = tmp_path / "challenge.jsonl"
    manifest = tmp_path / "challenge.manifest.json"

    summary = _module().materialize(
        root / "evidence/T052/review-packet-v2.json",
        root / "evidence/T057/strict-exact-pair-development.json",
        output,
        manifest,
    )
    records, loaded_manifest = read_canonical_dataset(output, manifest)

    assert summary == (20, 59, loaded_manifest.fingerprint)
    assert len(records) == 20
    assert sum(len(record.gold_annotations) for record in records) == 59
    assert all(record.provenance is not None for record in records)
