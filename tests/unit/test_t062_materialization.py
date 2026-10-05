"""Regression tests for the reconciled T062 development projection."""

from __future__ import annotations

from pathlib import Path

from scripts.materialize_t062_development import materialize

from abrex.corpora import read_canonical_dataset


def test_t062_materialization_preserves_texts_and_all_strict_relations(
    tmp_path: Path,
) -> None:
    output = tmp_path / "t062.jsonl"
    manifest = tmp_path / "t062.manifest.json"

    records, relations, fingerprint = materialize(
        Path("evidence/T059/t057-strict-development.jsonl"),
        Path("evidence/T059/t057-strict-development.manifest.json"),
        Path("evidence/T062/development-ledger-v1.json"),
        output,
        manifest,
    )

    loaded, loaded_manifest = read_canonical_dataset(output, manifest)
    assert records == len(loaded) == 20
    assert relations == sum(len(record.gold_annotations) for record in loaded) == 67
    assert loaded_manifest.fingerprint == fingerprint
    assert loaded_manifest.annotation_count == 67
    assert loaded_manifest.validation.total == 5
    assert all(
        issue.code == "OVERLAPPING_ANNOTATIONS"
        for issue in loaded_manifest.validation.issues
    )
