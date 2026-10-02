"""Tests for source-grounded Jev candidate judgment."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from abrex.config import ComponentSpec
from abrex.domain import Document
from abrex.resolvers import (
    RESOLVERS,
    JevBudgetError,
    JevCandidateJudgeResolver,
    JevResolverError,
    JevResponseError,
    calibrate_threshold,
)


def _generators() -> tuple[ComponentSpec, ...]:
    return (ComponentSpec(type="parenthetical", params={}),)


def _answer(choice: str, probability: float = 0.9) -> SimpleNamespace:
    remaining = (1.0 - probability) / 2
    probabilities = {
        "forward": remaining,
        "reverse": remaining,
        "not_definition": remaining,
    }
    probabilities[choice] = probability
    return SimpleNamespace(
        choice=choice,
        confidence=probability,
        probabilities=probabilities,
    )


class FakeClient:
    def __init__(self, *, failures: int = 0, extra: bool = False) -> None:
        self.failures = failures
        self.extra = extra
        self.calls: list[dict[str, Any]] = []

    def system_one(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        if len(self.calls) <= self.failures:
            raise TimeoutError("temporary test timeout")
        state = kwargs["state"]
        assert isinstance(state, dict)
        rows = state["candidates"]
        assert isinstance(rows, dict)
        choices = {}
        for candidate_id, value in rows.items():
            assert isinstance(value, dict)
            choice = (
                "forward"
                if value["proposed_long_form"] == "tumor necrosis factor"
                else "not_definition"
            )
            choices[candidate_id] = _answer(choice)
        if self.extra:
            choices["unexpected"] = _answer("not_definition")
        return SimpleNamespace(
            choices=choices,
            model="jev-1.13.0",
            request_id="req-test",
            usage={"input_tokens": 123, "output_tokens": 4},
        )


def _resolver(tmp_path: Any, client: FakeClient, **params: object) -> Any:
    return JevCandidateJudgeResolver(
        client=client,
        candidate_generators=_generators(),
        cache_path=tmp_path / "jev.jsonl",
        **params,
    )


def test_jev_selects_only_exact_grounded_candidate_and_records_metadata(
    tmp_path: Any,
) -> None:
    client = FakeClient()
    resolver = _resolver(tmp_path, client)
    document = Document("d1", "β tumor necrosis factor (TNF) is measured.")

    predictions = resolver.resolve(document)

    assert len(predictions) == 1
    prediction = predictions[0]
    assert prediction.short_form_text == "TNF"
    assert prediction.long_form_text == "tumor necrosis factor"
    assert prediction.prediction is not None
    assert prediction.prediction.confidence == pytest.approx(0.9)
    assert prediction.prediction.model_artifact_fingerprint == "jev-1.13.0"
    assert prediction.provenance is not None
    assert "request_id=req-test" in prediction.provenance.transformation_notes
    assert client.calls[0]["model"] == "jev-1.13.0"
    assert client.calls[0]["timeout"] == 30.0


def test_jev_cache_replay_performs_no_network_call(tmp_path: Any) -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    first_client = FakeClient()
    assert _resolver(tmp_path, first_client).resolve(document)

    second_client = FakeClient(failures=100)
    predictions = _resolver(tmp_path, second_client, cache_only=True).resolve(document)

    assert predictions
    assert not second_client.calls
    assert predictions[0].provenance is not None
    assert "cached=true" in predictions[0].provenance.transformation_notes


def test_jev_retries_retryable_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr("abrex.resolvers.jev.time.sleep", lambda _seconds: None)
    client = FakeClient(failures=2)

    assert _resolver(tmp_path, client, retries=2).resolve(
        Document("d1", "tumor necrosis factor (TNF)")
    )
    assert len(client.calls) == 3


def test_jev_limits_requests_and_cache_misses(tmp_path: Any) -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    with pytest.raises(JevBudgetError, match="request budget"):
        _resolver(tmp_path, FakeClient(), maximum_network_requests=0).resolve(document)
    with pytest.raises(JevBudgetError, match="cache miss"):
        _resolver(tmp_path, FakeClient(), cache_only=True).resolve(document)


def test_jev_rejects_malformed_response_and_frozen_contracts(tmp_path: Any) -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    with pytest.raises(JevResponseError, match="unexpected question"):
        _resolver(tmp_path, FakeClient(extra=True)).resolve(document)
    with pytest.raises(ValueError, match="frozen to"):
        JevCandidateJudgeResolver(model="jev-moving", client=FakeClient())
    with pytest.raises(ValueError, match="frozen to policy"):
        JevCandidateJudgeResolver(policy_version="future", client=FakeClient())


def test_jev_rejects_invalid_cache_without_silent_loss(tmp_path: Any) -> None:
    cache = tmp_path / "bad.jsonl"
    cache.write_text(
        json.dumps(
            {
                "model": "jev-1.13.0",
                "policy_version": "abrex-candidate-choice-v1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(JevResponseError, match="invalid Jev cache"):
        JevCandidateJudgeResolver(
            client=FakeClient(),
            candidate_generators=_generators(),
            cache_path=cache,
        )


def test_jev_surfaces_nonretryable_errors(tmp_path: Any) -> None:
    class AuthenticationError(Exception):
        pass

    class BadClient:
        def system_one(self, **_kwargs: object) -> object:
            raise AuthenticationError("denied")

    with pytest.raises(JevResolverError, match="after 1 attempt"):
        JevCandidateJudgeResolver(
            client=BadClient(),
            candidate_generators=_generators(),
            cache_path=tmp_path / "cache.jsonl",
        ).resolve(Document("d1", "tumor necrosis factor (TNF)"))


def test_calibration_maximizes_f1_then_precision_then_threshold() -> None:
    result = calibrate_threshold([(0.9, True), (0.8, False)], grid=(0.5, 0.85, 0.9))
    assert result.threshold == 0.9
    assert result.f1 == 1.0
    assert result.precision == 1.0
    with pytest.raises(ValueError, match="at least one"):
        calibrate_threshold([])
    with pytest.raises(ValueError, match="must not be empty"):
        calibrate_threshold([(0.9, True)], grid=())
    with pytest.raises(ValueError, match="between zero and one"):
        calibrate_threshold([(0.9, True)], grid=(1.1,))
    bounded = calibrate_threshold(
        [(0.9, True), (0.8, False)], grid=(0.5, 0.85), total_positives=2
    )
    assert bounded.true_positives == 1
    assert bounded.false_negatives == 1
    with pytest.raises(ValueError, match="below observed"):
        calibrate_threshold([(0.9, True)], total_positives=0)


def test_jev_registry_key_and_cache_identity_are_stable(tmp_path: Any) -> None:
    resolver = _resolver(tmp_path, FakeClient())
    assert RESOLVERS.get("jev_candidate_judge") is JevCandidateJudgeResolver
    assert resolver.cache_identity["model"] == "jev-1.13.0"
    assert resolver.cache_identity["policy_version"] == "abrex-candidate-choice-v1"
