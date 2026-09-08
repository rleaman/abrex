"""Deterministic sampling and leakage-control tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abrex.literature.sampling import (
    FrameRecord,
    SamplingConfig,
    SamplingError,
    SamplingRoleConfig,
    derive_lexicon_view,
    load_sampling_config,
    sample_frame,
    write_sampling_manifest,
)


def _config(tmp_path: Path, **overrides: object) -> SamplingConfig:
    values: dict[str, object] = {
        "frame_path": tmp_path / "frame.jsonl",
        "manifest_path": tmp_path / "manifest.json",
        "seed": 7,
        "roles": (
            SamplingRoleConfig(name="challenge", strategy="challenge", max_groups=1),
            SamplingRoleConfig(name="development", fraction=0.5, lexicon_allowed=True),
            SamplingRoleConfig(name="evaluation", fraction=0.5),
        ),
    }
    values.update(overrides)
    return SamplingConfig.model_validate(values)


def _write_frame(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_sampling_groups_versions_and_blocks_held_out_lexicon(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(
        frame,
        [
            {"record_id": "pmid-1", "pmid": "1", "text": "same article text"},
            {
                "record_id": "pmcid-1",
                "pmcid": "PMC1",
                "text": "same article text",
            },
            {
                "record_id": "challenge",
                "pmid": "2",
                "text": "table cell evidence",
                "challenge_tags": ["table"],
                "occurrence_keys": ["held-out|term"],
            },
            {
                "record_id": "development",
                "pmid": "3",
                "text": "development evidence",
                "occurrence_keys": ["allowed|term"],
            },
        ],
    )
    config = _config(tmp_path)
    first = sample_frame(config)
    second = sample_frame(config)
    assert first.to_dict() == second.to_dict()
    assert len(first.groups) == 3
    grouped = {
        record_id: group.group_id
        for group in first.groups
        for record_id in group.record_ids
    }
    assert grouped["pmid-1"] == grouped["pmcid-1"]
    assert len({item["group_id"] for item in first.assignments}) == 3
    assert "held-out|term" not in derive_lexicon_view(first)
    assert first.frequency_priorities == {}
    assert all(
        item["lexicon_allowed"] is False
        for item in first.assignments
        if item["role"] == "evaluation"
    )


def test_sampling_accounts_unavailable_official_and_unknown_overlap(
    tmp_path: Path,
) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(
        frame,
        [
            {
                "record_id": "official",
                "pmid": "1",
                "text": "official source",
                "official_split": "test",
            },
            {
                "record_id": "missing",
                "pmid": "2",
                "available": False,
            },
            {
                "record_id": "unknown",
                "pmid": "3",
                "text": "unknown training overlap",
                "teacher_overlap": "unknown",
            },
            {
                "record_id": "known",
                "pmid": "4",
                "text": "known training overlap",
                "teacher_overlap": "yes",
            },
        ],
    )
    result = sample_frame(
        _config(tmp_path, roles=(SamplingRoleConfig(name="development", fraction=1.0),))
    )
    roles = {item["record_id"]: item["role"] for item in result.assignments}
    assert roles == {
        "known": "excluded:teacher-overlap",
        "missing": "unavailable",
        "official": "official:test",
        "unknown": "development",
    }
    assert result.summary["unavailable_texts"] == 1
    assert result.summary["unknown_teacher_overlap_groups"] == 3


def test_sampling_detects_conflicting_official_splits(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(
        frame,
        [
            {"record_id": "a", "pmid": "1", "text": "same", "official_split": "train"},
            {"record_id": "b", "pmid": "1", "text": "same", "official_split": "test"},
        ],
    )
    with pytest.raises(SamplingError, match="conflicting official"):
        sample_frame(_config(tmp_path))


def test_sampling_config_and_manifest_are_typed_and_reproducible(
    tmp_path: Path,
) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(frame, [{"record_id": "one", "pmid": "1", "text": "one"}])
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "sampling:\n"
        f"  frame_path: {frame}\n"
        f"  manifest_path: {tmp_path / 'out.json'}\n"
        "  seed: 3\n"
        "  roles:\n"
        "    - name: development\n      fraction: 1.0\n",
        encoding="utf-8",
    )
    config = load_sampling_config(config_path)
    result = sample_frame(config)
    fingerprint = write_sampling_manifest(result, config.manifest_path)
    payload = config.manifest_path.read_text(encoding="utf-8")
    assert fingerprint == hashlib.sha256(payload.encode()).hexdigest()
    assert json.loads(payload)["mode"] == "proposal"
    assert json.loads(payload)["summary"]["source_kind_counts"] == {"unknown": 1}


def test_sampling_uses_optional_frequency_resource_for_occurrence_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(
        frame,
        [
            {
                "record_id": "one",
                "pmid": "1",
                "text": "one",
                "occurrence_keys": ["CNS|central nervous system"],
            }
        ],
    )

    class Variant:
        count = 12

    class Resource:
        def lookup(self, short_form: str) -> tuple[Variant, ...]:
            assert short_form == "CNS"
            return (Variant(),)

    monkeypatch.setattr(
        "abrex.literature.sampling.FrequencyResource", lambda _path: Resource()
    )
    result = sample_frame(
        _config(
            tmp_path,
            frequency_resource_path=tmp_path / "resource.sqlite",
            roles=(
                SamplingRoleConfig(
                    name="development", fraction=1.0, lexicon_allowed=True
                ),
            ),
        )
    )
    assert result.frequency_priorities == {"CNS": 12}


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"roles": ()}, "at least 1"),
        (
            {
                "roles": (
                    SamplingRoleConfig(name="a", fraction=0.7),
                    SamplingRoleConfig(name="b", fraction=0.7),
                )
            },
            "at most 1",
        ),
        (
            {
                "roles": (
                    {
                        "name": "a",
                        "strategy": "challenge",
                        "fraction": 0.1,
                        "max_groups": 1,
                    },
                )
            },
            "challenge roles",
        ),
    ],
)
def test_sampling_config_rejects_ambiguous_policies(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _config(tmp_path, **overrides)


def test_sampling_rejects_duplicate_frame_ids_and_bad_json(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jsonl"
    frame.write_text(
        json.dumps({"record_id": "one", "text": "x"})
        + "\n"
        + json.dumps({"record_id": "one", "text": "y"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SamplingError, match="unique"):
        sample_frame(_config(tmp_path))
    frame.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(SamplingError, match="Invalid frame line"):
        sample_frame(_config(tmp_path))


def test_sampling_rejects_empty_frame(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jsonl"
    frame.write_text("\n", encoding="utf-8")
    with pytest.raises(SamplingError, match="at least one"):
        sample_frame(_config(tmp_path))


def test_sampling_role_and_frame_validation_branches() -> None:
    with pytest.raises(ValueError, match="require fraction"):
        SamplingRoleConfig(name="empty")
    with pytest.raises(ValueError, match="unique"):
        SamplingConfig(
            frame_path=Path("frame"),
            seed=1,
            roles=(
                SamplingRoleConfig(name="same", fraction=1.0),
                SamplingRoleConfig(name="same", fraction=0.0, max_groups=1),
            ),
        )
    invalid_values = (
        ({"record_id": "x"}, "identifier or text"),
        ({"record_id": "x", "pmid": " "}, "pmid"),
        ({"record_id": "x", "text": "x", "source_sha256": "bad"}, "64-character"),
        ({"record_id": "x", "text": "x", "challenge_tags": [""]}, "challenge_tags"),
        ({"record_id": "x", "text": "x", "occurrence_keys": [""]}, "occurrence_keys"),
    )
    for values, message in invalid_values:
        with pytest.raises(ValueError, match=message):
            FrameRecord.model_validate(values)


def test_sampling_reports_bad_frequency_resource_and_load_config_errors(
    tmp_path: Path,
) -> None:
    frame = tmp_path / "frame.jsonl"
    _write_frame(
        frame,
        [
            {
                "record_id": "one",
                "pmid": "1",
                "text": "one",
                "occurrence_keys": ["CNS|term"],
            }
        ],
    )
    with pytest.raises(SamplingError, match="frequency resource"):
        sample_frame(
            _config(
                tmp_path,
                frequency_resource_path=tmp_path / "missing.sqlite",
                roles=(
                    SamplingRoleConfig(
                        name="development", fraction=1.0, lexicon_allowed=True
                    ),
                ),
            )
        )
    missing_config = tmp_path / "missing.yaml"
    with pytest.raises(SamplingError, match="Unable to read configuration"):
        load_sampling_config(missing_config)
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("sampling: 3\n", encoding="utf-8")
    with pytest.raises(SamplingError, match="'sampling' mapping"):
        load_sampling_config(malformed)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "sampling:\n  frame_path: frame\n  seed: -1\n"
        "  roles:\n    - name: development\n      fraction: 1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(SamplingError, match="Invalid sampling configuration"):
        load_sampling_config(invalid)
