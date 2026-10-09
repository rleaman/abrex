"""Milestone C locked-gold projection and second-review tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from abrex.config import load_resolved_config
from abrex.literature import read_blind_packet
from abrex.literature.milestone_c_postlock import (
    MilestoneCPostlockProjection,
    materialize_milestone_c_postlock,
)
from abrex.literature.review_interchange import read_annotation_state

ROOT = Path(__file__).parents[2]
EVIDENCE = ROOT / "evidence/campaign-2026-10/milestone-c"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialize(tmp_path: Path) -> MilestoneCPostlockProjection:
    return materialize_milestone_c_postlock(
        packet_path=EVIDENCE / "review-packet-blind-v1.json",
        state_path=EVIDENCE / "review-packet-blind-v1.annotations.json",
        lock_path=EVIDENCE / "review-packet-blind-v1.annotations.lock.json",
        source_manifest_path=EVIDENCE / "source-manifest-v1.json",
        protocol_path=EVIDENCE / "protocol-v1.json",
        prediction_path=tmp_path / "prediction.jsonl",
        prediction_manifest_path=tmp_path / "prediction.manifest.json",
        gold_path=tmp_path / "gold.jsonl",
        gold_manifest_path=tmp_path / "gold.manifest.json",
        ledger_path=tmp_path / "ledger.json",
        run_manifest_path=tmp_path / "run.json",
        second_review_packet_path=tmp_path / "second-packet.json",
        second_review_state_path=tmp_path / "second-state.json",
        second_review_selection_path=tmp_path / "second-selection.json",
    )


def test_postlock_projection_separates_gold_and_freezes_second_review(
    tmp_path: Path,
) -> None:
    state_path = EVIDENCE / "review-packet-blind-v1.annotations.json"
    lock_path = EVIDENCE / "review-packet-blind-v1.annotations.lock.json"
    before = (_sha(state_path), _sha(lock_path))

    result = _materialize(tmp_path)

    counts = cast(Mapping[str, object], result.ledger["counts"])
    second_counts = cast(Mapping[str, object], result.second_review_manifest["counts"])
    assert len(result.prediction_records) == 120
    assert all(not record.gold_annotations for record in result.prediction_records)
    assert sum(len(record.gold_annotations) for record in result.gold_records) == 66
    assert counts["diagnostic_relations"] == 2
    assert counts["unresolved_relations"] == 0
    assert second_counts == {
        "primary_cases": 120,
        "positive_cases": 26,
        "negative_cases": 94,
        "sampled_negative_cases": 10,
        "selected_cases": 36,
    }
    assert before == (_sha(state_path), _sha(lock_path))

    second_packet = read_blind_packet(tmp_path / "second-packet.json")
    second_state = read_annotation_state(
        second_packet.annotation_packet(), tmp_path / "second-state.json"
    )
    assert len(second_packet.cases) == 36
    assert second_state.annotations == {}
    selection = json.loads((tmp_path / "second-selection.json").read_text())
    assert selection["negative_ranking"].startswith("ascending sha256")
    assert len(selection["owner_only_review_focus"]) == 1


def test_postlock_projection_rejects_a_nonbinding_lock(tmp_path: Path) -> None:
    value = json.loads(
        (EVIDENCE / "review-packet-blind-v1.annotations.lock.json").read_text()
    )
    value["annotation_state_sha256"] = "0" * 64
    bad_lock = tmp_path / "bad-lock.json"
    bad_lock.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="does not bind the annotation state"):
        materialize_milestone_c_postlock(
            packet_path=EVIDENCE / "review-packet-blind-v1.json",
            state_path=EVIDENCE / "review-packet-blind-v1.annotations.json",
            lock_path=bad_lock,
            source_manifest_path=EVIDENCE / "source-manifest-v1.json",
            protocol_path=EVIDENCE / "protocol-v1.json",
            prediction_path=tmp_path / "prediction.jsonl",
            prediction_manifest_path=tmp_path / "prediction.manifest.json",
            gold_path=tmp_path / "gold.jsonl",
            gold_manifest_path=tmp_path / "gold.manifest.json",
            ledger_path=tmp_path / "ledger.json",
            run_manifest_path=tmp_path / "run.json",
            second_review_packet_path=tmp_path / "second-packet.json",
            second_review_state_path=tmp_path / "second-state.json",
            second_review_selection_path=tmp_path / "second-selection.json",
        )


def test_confirmatory_online_configs_preserve_frozen_limits() -> None:
    environment = {
        "AZURE_OPENAI_DEPLOYMENT": "test-luna",
        "AZURE_OPENAI_ENDPOINT": "https://example.invalid",
        "AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS": "0.1",
        "AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS": "0.5",
    }
    jev = load_resolved_config(
        (ROOT / "configs/experiments/campaign-2026-10-milestone-c-jev.yaml",),
        environment=environment,
    )
    luna = load_resolved_config(
        (ROOT / "configs/experiments/campaign-2026-10-milestone-c-luna.yaml",),
        environment=environment,
    )

    jev_resolver = cast(Mapping[str, object], jev.model_dump()["resolver"])
    jev_params = cast(Mapping[str, object], jev_resolver["params"])
    assert jev_resolver["type"] == "jev_candidate_judge"
    assert jev_resolver["error_policy"] == "collect"
    assert jev_params["maximum_network_requests"] == 64
    assert jev_params["maximum_input_tokens"] == 723000
    assert jev_params["retries"] == 0

    luna_resolver = cast(Mapping[str, object], luna.model_dump()["resolver"])
    luna_params = cast(Mapping[str, object], luna_resolver["params"])
    assert luna_resolver["type"] == "openai_direct_extraction"
    assert luna_resolver["error_policy"] == "collect"
    assert luna_params["prompt_version"] == ("abrex-quote-grounded-2026-10-06-i02")
    assert luna_params["maximum_network_attempts"] == 120
    assert luna_params["maximum_estimated_input_tokens"] == 201000
    assert luna_params["maximum_output_tokens_per_request"] == 8192
    assert luna_params["monetary_cap_usd"] == 0.10
    assert luna_params["retries"] == 0


def test_confirmatory_linux_configs_collect_runtime_failures() -> None:
    environment = {
        "ABREX_AB3P_MANIFEST": "/runtime/ab3p/manifest.json",
        "ABREX_AB3P_ROOT": "/runtime/ab3p",
        "ABREX_PLODV2_CHECKPOINT": "/runtime/plod/best-model.pt",
    }
    for name, expected_type in (
        ("campaign-2026-10-milestone-c-ab3p-linux.yaml", "ab3p"),
        ("campaign-2026-10-milestone-c-plodv2-linux.yaml", "plodv2_pairing"),
    ):
        config = load_resolved_config(
            (ROOT / "configs/experiments" / name,), environment=environment
        )
        resolver = cast(Mapping[str, object], config.model_dump()["resolver"])
        assert resolver["type"] == expected_type
        assert resolver["error_policy"] == "collect"
