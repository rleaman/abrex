"""Tests for the source-grounded direct extraction baseline."""

from __future__ import annotations

import io
import json
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from abrex.cli import main
from abrex.config import ComponentSpec, ConfigError, load_resolved_config
from abrex.domain import Document
from abrex.experiments import run_experiment
from abrex.infrastructure.openai_responses import OpenAIResponsesClient
from abrex.resolvers import (
    RESOLVERS,
    DirectExtractionBudgetError,
    DirectExtractionConfig,
    DirectExtractionResolver,
    ResolverExecutor,
)


class FakeClient:
    def __init__(self, output: Mapping[str, object], *, failures: int = 0) -> None:
        self.output = output
        self.failures = failures
        self.calls: list[dict[str, object]] = []

    def create_response(
        self, *, payload: Mapping[str, object], timeout_seconds: float
    ) -> Mapping[str, object]:
        self.calls.append(
            {"payload": dict(payload), "timeout_seconds": timeout_seconds}
        )
        if len(self.calls) <= self.failures:
            raise TimeoutError("temporary")
        return {
            "model": "gpt-6-luna-2026-09-01",
            "request_id": "resp-test",
            "output": dict(self.output),
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }


def _span(text: str, quote: str) -> dict[str, object]:
    start = text.index(quote)
    return {"quote": quote, "start": start, "end": start + len(quote)}


def _pair(
    text: str,
    *,
    short: str = "TNF",
    long: str = "tumor necrosis factor",
    evidence: str = "contiguous",
) -> dict[str, object]:
    return {
        "short_form": _span(text, short),
        "long_form": _span(text, long),
        "evidence": evidence,
    }


def _resolver(tmp_path: Any, client: FakeClient, **params: object) -> Any:
    return DirectExtractionResolver(
        client=client,
        cache_path=tmp_path / "direct.jsonl",
        **params,
    )


def test_direct_extractor_validates_literal_unicode_offsets_and_metadata(
    tmp_path: Any,
) -> None:
    text = "β tumor necrosis factor (TNF) is measured."
    client = FakeClient({"pairs": [_pair(text)]})
    resolver = _resolver(tmp_path, client)

    result = resolver.resolve_detailed(Document("d1", text))

    assert len(result.predictions) == 1
    prediction = result.predictions[0]
    assert prediction.short_form_text == "TNF"
    assert prediction.long_form_text == "tumor necrosis factor"
    assert prediction.short_form is not None
    assert prediction.short_form.start == text.index("TNF")
    assert prediction.prediction is not None
    assert prediction.prediction.model_artifact_fingerprint == ("gpt-6-luna-2026-09-01")
    assert prediction.provenance is not None
    assert "literal_quotes_validated=true" in (
        prediction.provenance.transformation_notes
    )
    payload = client.calls[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-6-luna"
    text_config = payload["text"]
    assert isinstance(text_config, dict)
    format_config = text_config["format"]
    assert isinstance(format_config, dict)
    assert format_config["strict"] is True
    assert result.diagnostics[0].code == "DIRECT_REQUEST_COMPLETED"
    assert dict(result.diagnostics[0].details)["request_id"] == "resp-test"


def test_direct_extractor_diagnoses_unsupported_discontinuous_and_duplicate(
    tmp_path: Any,
) -> None:
    text = "tumor necrosis factor (TNF)"
    valid = _pair(text)
    invalid = _pair(text)
    assert isinstance(invalid["short_form"], dict)
    invalid["short_form"]["start"] = 0
    discontinuous = _pair(text, evidence="discontinuous")
    resolver = _resolver(
        tmp_path,
        FakeClient({"pairs": [valid, invalid, discontinuous, valid]}),
    )

    record = ResolverExecutor(resolver).resolve_document(Document("d1", text))

    assert len(record.predictions) == 1
    assert [item.code for item in record.diagnostics] == [
        "DIRECT_REQUEST_COMPLETED",
        "DIRECT_UNSUPPORTED_OUTPUT",
        "DIRECT_DISCONTINUOUS_EVIDENCE",
        "DIRECT_DUPLICATE_OUTPUT",
    ]
    assert record.diagnostics[0].action == "observed"
    assert all(item.action == "dropped" for item in record.diagnostics[1:])


def test_direct_extractor_abstention_cache_and_usage(tmp_path: Any) -> None:
    document = Document("d1", "No definitions here.")
    first_client = FakeClient({"pairs": []})
    first = _resolver(tmp_path, first_client)
    first_result = first.resolve_detailed(document)

    assert [item.code for item in first_result.diagnostics] == [
        "DIRECT_REQUEST_COMPLETED",
        "DIRECT_ABSTAINED",
    ]
    assert first.usage["network_attempts"] == 1
    assert first.usage["actual_input_tokens"] == 100
    assert first.usage["cache_hits"] == 0

    replay_client = FakeClient({"pairs": []}, failures=100)
    replay = _resolver(tmp_path, replay_client, cache_only=True)
    replay_result = replay.resolve_detailed(document)
    assert replay_result.diagnostics == first_result.diagnostics
    assert replay.usage["cache_hits"] == 1
    assert not replay_client.calls


def test_direct_extractor_cache_identity_includes_provider_endpoint(
    tmp_path: Path,
) -> None:
    document = Document("d1", "No definitions here.")
    cache_path = tmp_path / "direct.jsonl"
    first = DirectExtractionResolver(
        client=FakeClient({"pairs": []}),
        cache_path=cache_path,
        endpoint="https://provider-one.invalid/v1/responses",
    )
    first.resolve_detailed(document)

    changed_destination = DirectExtractionResolver(
        client=FakeClient({"pairs": []}),
        cache_path=cache_path,
        endpoint="https://provider-two.invalid/v1/responses",
        cache_only=True,
    )

    with pytest.raises(DirectExtractionBudgetError, match="cache miss"):
        changed_destination.resolve_detailed(document)


def test_direct_extractor_limits_cost_requests_and_documents(tmp_path: Any) -> None:
    text = "tumor necrosis factor (TNF)"
    with pytest.raises(DirectExtractionBudgetError, match="network-attempt"):
        _resolver(
            tmp_path / "attempts", FakeClient({"pairs": []}), maximum_network_attempts=0
        ).resolve(Document("d1", text))
    with pytest.raises(DirectExtractionBudgetError, match="could exceed"):
        _resolver(
            tmp_path / "cost",
            FakeClient({"pairs": []}),
            monetary_cap_usd=0.000001,
        ).resolve(Document("d1", text))
    with pytest.raises(DirectExtractionBudgetError, match="characters"):
        _resolver(
            tmp_path / "length",
            FakeClient({"pairs": []}),
            maximum_document_characters=2,
        ).resolve(Document("d1", text))


def test_direct_extractor_retries_and_rejects_bad_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr("abrex.resolvers.direct_extraction.time.sleep", lambda _: None)
    client = FakeClient({"pairs": []}, failures=1)
    assert not _resolver(tmp_path / "retry", client, retries=1).resolve(
        Document("d1", "No definitions")
    )
    assert len(client.calls) == 2

    cache = tmp_path / "bad.jsonl"
    cache.write_text(json.dumps({"request_hash": "x", "response": {}}) + "\n")
    with pytest.raises(ValueError, match="Invalid direct extraction cache"):
        DirectExtractionResolver(client=FakeClient({"pairs": []}), cache_path=cache)


def test_direct_extractor_is_registry_backed() -> None:
    entry = RESOLVERS.get_entry("openai_direct_extraction")
    assert entry.config_model is not None
    config = DirectExtractionConfig.model_validate({})
    assert config.model == "gpt-6-luna"
    assert ComponentSpec(type=entry.key, params={}).type == entry.key


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (
            "https://example.openai.azure.com/",
            "https://example.openai.azure.com/openai/v1/responses",
        ),
        (
            "https://example.openai.azure.com/openai/v1/",
            "https://example.openai.azure.com/openai/v1/responses",
        ),
        (
            "https://example.openai.azure.com/openai/v1/responses",
            "https://example.openai.azure.com/openai/v1/responses",
        ),
    ],
)
def test_azure_response_url_accepts_resource_and_v1_endpoint(
    endpoint: str, expected: str
) -> None:
    client = OpenAIResponsesClient(
        endpoint=endpoint,
        api_key_env="ABREX_TEST_AZURE_KEY",
        provider="azure_openai",
    )
    assert client.endpoint == expected


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.openai.azure.com",
        "https://example.openai.azure.com/openai/deployments/test",
        "https://example.openai.azure.com?api-version=2025-04-01-preview",
    ],
)
def test_azure_response_url_rejects_non_v1_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError, match="Azure OpenAI endpoint"):
        OpenAIResponsesClient(
            endpoint=endpoint,
            api_key_env="ABREX_TEST_AZURE_KEY",
            provider="azure_openai",
        )


def test_campaign_config_requires_azure_route_and_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = Path("configs/experiments/campaign-2026-10-direct-extraction.yaml")
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS",
        "AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError, match="AZURE_OPENAI_DEPLOYMENT"):
        load_resolved_config((config_path,))


def test_campaign_config_runs_end_to_end_through_http_and_direct_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_path = tmp_path / "direct-cache.jsonl"
    live_override = tmp_path / "live-override.yaml"
    live_override.write_text(
        f"resolver:\n  params:\n    cache_path: {json.dumps(cache_path.as_posix())}\n",
        encoding="utf-8",
        newline="\n",
    )
    requests: list[dict[str, object]] = []

    def fake_urlopen(request: urllib.request.Request, *, timeout: float) -> io.BytesIO:
        headers = {key.lower(): value for key, value in request.header_items()}
        assert headers["api-key"] == "test-only"
        assert "authorization" not in headers
        assert (
            request.full_url == "https://example.openai.azure.com/openai/v1/responses"
        )
        assert timeout == 60
        assert isinstance(request.data, bytes)
        payload = json.loads(request.data.decode("utf-8"))
        assert isinstance(payload, dict)
        requests.append(payload)
        response = {
            "id": f"resp-{len(requests)}",
            "model": "gpt-6-luna-test-snapshot",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"pairs": []}),
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        return io.BytesIO(json.dumps(response).encode("utf-8"))

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS", "0.10")
    monkeypatch.setenv("AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS", "0.50")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    base_config = Path("configs/experiments/campaign-2026-10-direct-extraction.yaml")

    assert (
        main(
            [
                "experiment",
                "run",
                str(base_config),
                str(live_override),
                "--output-root",
                str(tmp_path / "live-output"),
            ]
        )
        == 0
    )
    live_summary = json.loads(capsys.readouterr().out)

    assert len(requests) == 20
    assert all(request["model"] == "test-deployment" for request in requests)
    manifest = json.loads(Path(live_summary["manifest"]).read_text(encoding="utf-8"))
    assert manifest["resolved_config"]["resolver"]["params"]["model"] == (
        "test-deployment"
    )
    assert "test-only" not in json.dumps(manifest)
    usage = manifest["resolver"]["usage"]
    assert usage["network_attempts"] == 20
    assert usage["estimated_input_tokens"] > 0
    assert usage["actual_input_tokens"] == 2000
    assert usage["actual_output_tokens"] == 400
    assert usage["cache_hits"] == 0
    assert usage["actual_cost_usd"] == pytest.approx(0.0004)
    assert live_summary["estimated_total_cost_usd"] == pytest.approx(0.0004)
    assert len(list(Path(live_summary["run_directory"]).glob("report-*"))) == 3
    assert len(cache_path.read_text(encoding="utf-8").splitlines()) == 20

    cache_only_override = tmp_path / "cache-only-override.yaml"
    cache_only_override.write_text(
        "resolver:\n  params:\n    cache_only: true\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.delenv("AZURE_OPENAI_API_KEY")

    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise AssertionError("cache-only replay attempted a network request")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    replay = run_experiment(
        (base_config, live_override, cache_only_override),
        output_root=tmp_path / "replay-output",
        reuse_cached_predictions=False,
    )

    replay_manifest = json.loads(replay.manifest_path.read_text(encoding="utf-8"))
    assert replay_manifest["resolver"]["usage"] == {
        "network_attempts": 0,
        "estimated_input_tokens": 0,
        "actual_input_tokens": 0,
        "actual_output_tokens": 0,
        "cache_hits": 20,
        "actual_cost_usd": 0.0,
    }
    assert replay.prediction_fingerprint == live_summary["prediction_fingerprint"]
