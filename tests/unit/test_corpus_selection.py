"""Bounded corpus-selection and article-group leakage controls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.literature import (
    CorpusFrameRecord,
    CorpusSelectionConfig,
    CorpusSelectionError,
    WorkScaleLimits,
    load_corpus_selection_config,
    select_corpus,
    write_corpus_selection_manifest,
)


def _write_frame(path: Path) -> None:
    rows = [
        {
            "record_id": "pmid-1",
            "pmid": "1",
            "text": "A biomedical abstract.",
            "source_kind": "abstract",
            "source_version": "pubmed-v1",
            "year": 2021,
        },
        {
            "record_id": "pmcid-1",
            "pmid": "1",
            "pmcid": "PMC1",
            "text": "A biomedical abstract.",
            "source_kind": "full_text",
            "source_version": "pmc-v2",
            "year": 2021,
        },
        {
            "record_id": "challenge",
            "pmid": "2",
            "text": "A difficult caption with a rare form.",
            "source_kind": "full_text",
            "challenge_tags": ["caption", "rare-form"],
            "year": 2022,
        },
        {
            "record_id": "broad",
            "pmid": "6",
            "text": "A routine biomedical article.",
            "year": 2023,
        },
        {
            "record_id": "extra",
            "pmid": "7",
            "text": "Another routine article.",
            "year": 2024,
        },
        {
            "record_id": "old",
            "pmid": "3",
            "text": "An older article.",
            "year": 2001,
        },
        {
            "record_id": "missing-year",
            "pmid": "4",
            "text": "A record missing year.",
            "year": None,
        },
        {
            "record_id": "unavailable",
            "pmid": "5",
            "text": "",
            "available": False,
            "year": 2022,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _config(frame: Path, output: Path) -> CorpusSelectionConfig:
    return CorpusSelectionConfig(
        frame_path=frame,
        manifest_path=output,
        seed=7,
        snapshot_cutoff="2026-09-07",
        selection_rationale="bounded test selection",
        min_year=2020,
        max_year=2024,
        broad_max_groups=1,
        enriched_max_groups=1,
        protected_record_ids=("pmid-1",),
        work_scale_limits=WorkScaleLimits(estimated_documents_per_minute=10),
    )


def test_selection_groups_counterparts_and_separates_pools(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(frame)
    config = _config(frame, tmp_path / "manifest.json")
    first = select_corpus(config)
    second = select_corpus(config)
    assert first.to_dict() == second.to_dict()
    assert first.summary["article_groups"] == 7
    assert first.summary["selected_group_counts"] == {
        "discovery": 1,
        "enriched": 1,
        "tagged-release": 2,
    }
    assignment = {str(row["record_id"]): row for row in first.assignments}
    assert assignment["pmid-1"]["role"] == "excluded:evaluation-holdout"
    assert assignment["pmcid-1"]["evaluation_inference_only"] is True
    assert assignment["challenge"]["role"] == "enriched"
    assert assignment["unavailable"]["role"] == "excluded:unavailable"
    assert assignment["old"]["role"] == "excluded:year-range"
    assert assignment["missing-year"]["role"] == "excluded:missing-year"
    assert any(row["role"] == "eligible-not-selected" for row in assignment.values())
    assert write_corpus_selection_manifest(first, config.manifest_path)


def test_selection_config_and_frame_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="identifier or text"):
        CorpusFrameRecord(record_id="empty")
    with pytest.raises(ValueError, match="64-character"):
        CorpusFrameRecord(record_id="bad-hash", pmid="1", source_sha256="bad")
    with pytest.raises(ValueError, match="challenge_tags"):
        CorpusFrameRecord(record_id="bad-tag", pmid="1", challenge_tags=("",))
    with pytest.raises(ValueError, match="max_year"):
        CorpusSelectionConfig(
            frame_path=tmp_path / "frame",
            seed=1,
            snapshot_cutoff="today",
            selection_rationale="test",
            min_year=2024,
            max_year=2020,
        )
    frame = tmp_path / "bad.jsonl"
    frame.write_text("not-json\n", encoding="utf-8")
    config = CorpusSelectionConfig(
        frame_path=frame,
        seed=1,
        snapshot_cutoff="today",
        selection_rationale="test",
        min_year=2020,
        max_year=2024,
    )
    with pytest.raises(CorpusSelectionError, match="invalid frame line"):
        select_corpus(config)
    nonobject = tmp_path / "nonobject.jsonl"
    nonobject.write_text("[]\n", encoding="utf-8")
    with pytest.raises(CorpusSelectionError, match="invalid frame line"):
        select_corpus(config.model_copy(update={"frame_path": nonobject}))
    excluded = tmp_path / "excluded.jsonl"
    excluded.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"record_id": "language", "pmid": "10", "year": 2022, "language": "fr"},
                {
                    "record_id": "type",
                    "pmid": "11",
                    "year": 2022,
                    "document_type": "review",
                },
                {
                    "record_id": "reuse",
                    "pmid": "12",
                    "year": 2022,
                    "reuse_class": "restricted",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    excluded_result = select_corpus(config.model_copy(update={"frame_path": excluded}))
    excluded_roles = {
        str(row["record_id"]): row["role"] for row in excluded_result.assignments
    }
    assert excluded_roles == {
        "language": "excluded:language",
        "type": "excluded:document-type",
        "reuse": "excluded:reuse-class",
    }
    missing = CorpusSelectionConfig(
        frame_path=tmp_path / "missing.jsonl",
        seed=1,
        snapshot_cutoff="today",
        selection_rationale="test",
        min_year=2020,
        max_year=2024,
    )
    with pytest.raises(CorpusSelectionError, match="Unable to read"):
        select_corpus(missing)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(CorpusSelectionError, match="at least one"):
        select_corpus(missing.model_copy(update={"frame_path": empty}))
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(
        json.dumps({"record_id": "same", "pmid": "1"})
        + "\n"
        + json.dumps({"record_id": "same", "pmid": "2"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CorpusSelectionError, match="unique"):
        select_corpus(
            CorpusSelectionConfig(
                frame_path=duplicate,
                seed=1,
                snapshot_cutoff="today",
                selection_rationale="test",
                min_year=2020,
                max_year=2024,
            )
        )
    with pytest.raises(ValueError, match="allowed_languages"):
        CorpusSelectionConfig.model_validate(
            {**config.model_dump(), "allowed_languages": []}
        )
    with pytest.raises(ValueError, match="broad selection"):
        CorpusSelectionConfig.model_validate(
            {**config.model_dump(), "broad_fraction": 0.0, "broad_max_groups": None}
        )
    with pytest.raises(ValueError, match="protected_record_ids"):
        CorpusSelectionConfig.model_validate(
            {**config.model_dump(), "protected_record_ids": ["x", "x"]}
        )
    config_path = tmp_path / "config.yaml"
    config_path.write_text("other: true\n", encoding="utf-8")
    with pytest.raises(CorpusSelectionError, match="corpus_selection"):
        load_corpus_selection_config(config_path)
    config_path.write_text("corpus_selection: [", encoding="utf-8")
    with pytest.raises(CorpusSelectionError, match="invalid corpus-selection"):
        load_corpus_selection_config(config_path)
    config_path.write_text(
        "corpus_selection:\n"
        "  frame_path: frame.jsonl\n"
        "  seed: 1\n"
        "  snapshot_cutoff: today\n"
        "  selection_rationale: test\n"
        "  min_year: 2020\n"
        "  max_year: 2024\n",
        encoding="utf-8",
    )
    assert load_corpus_selection_config(config_path).selection_rationale == "test"
