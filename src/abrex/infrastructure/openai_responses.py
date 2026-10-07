"""Minimal OpenAI Responses API adapter for structured direct extraction."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Literal, cast


class OpenAIResponsesHTTPError(RuntimeError):
    """An HTTP request to the Responses API failed."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


class OpenAIResponsesOutputError(RuntimeError):
    """A completed response had no usable structured output text."""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        input_tokens: int,
        output_tokens: int,
        request_id: str | None = None,
        model: str | None = None,
        response_status: str | None = None,
        incomplete_reason: str | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.request_id = request_id
        self.model = model
        self.response_status = response_status
        self.incomplete_reason = incomplete_reason
        super().__init__(message)


class OpenAIResponsesClient:
    """Send one JSON request and normalize its structured text response."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key_env: str,
        provider: Literal["openai", "azure_openai"] = "openai",
    ) -> None:
        self.endpoint = _response_url(endpoint, provider)
        self.api_key_env = api_key_env
        self.provider = provider

    def create_response(
        self, *, payload: Mapping[str, object], timeout_seconds: float
    ) -> Mapping[str, object]:
        """Return model, request ID, parsed output text, and token usage."""

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise OpenAIResponsesHTTPError(
                401, f"Environment variable {self.api_key_env!r} is not set"
            )
        headers = {"Content-Type": "application/json"}
        if self.provider == "azure_openai":
            headers["api-key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise OpenAIResponsesHTTPError(error.code, body[:1000]) from error
        except (urllib.error.URLError, TimeoutError, UnicodeError) as error:
            raise RuntimeError(f"Responses API request failed: {error}") from error
        if not isinstance(raw, dict):
            raise TypeError("Responses API returned a non-object payload")
        response_mapping = cast(Mapping[str, object], raw)
        input_tokens, output_tokens = _token_usage(response_mapping)
        try:
            output_text = _output_text(response_mapping)
        except (RuntimeError, TypeError) as error:
            incomplete = response_mapping.get("incomplete_details")
            raise OpenAIResponsesOutputError(
                _output_failure_message(response_mapping, error),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_id=(raw.get("id") if isinstance(raw.get("id"), str) else None),
                model=(raw.get("model") if isinstance(raw.get("model"), str) else None),
                response_status=(
                    raw.get("status") if isinstance(raw.get("status"), str) else None
                ),
                incomplete_reason=(
                    incomplete.get("reason")
                    if isinstance(incomplete, Mapping)
                    and isinstance(incomplete.get("reason"), str)
                    else None
                ),
            ) from error
        return {
            "model": raw.get("model"),
            "request_id": raw.get("id"),
            "output": output_text,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }


def _response_url(endpoint: str, provider: Literal["openai", "azure_openai"]) -> str:
    if provider == "openai":
        return endpoint
    parsed = urllib.parse.urlsplit(endpoint.strip())
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Azure OpenAI endpoint must be an HTTPS URL without credentials or query"
        )
    path = parsed.path.rstrip("/")
    if path not in ("", "/openai/v1", "/openai/v1/responses"):
        raise ValueError(
            "Azure OpenAI endpoint must be a resource URL or /openai/v1 URL"
        )
    return urllib.parse.urlunsplit(
        ("https", parsed.netloc, "/openai/v1/responses", "", "")
    )


def _output_text(response: Mapping[str, object]) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise TypeError("Responses API output must be an array")
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise RuntimeError(f"Responses API refusal: {part.get('refusal', '')}")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(cast(str, part["text"]))
    if len(texts) != 1:
        raise TypeError(f"Expected one structured output text, received {len(texts)}")
    return texts[0]


def _token_usage(response: Mapping[str, object]) -> tuple[int, int]:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        raise TypeError("Responses API usage must be an object")
    values: list[int] = []
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TypeError(f"Responses API usage {key} must be a non-negative integer")
        values.append(value)
    return values[0], values[1]


def _output_failure_message(response: Mapping[str, object], error: Exception) -> str:
    status = response.get("status")
    incomplete = response.get("incomplete_details")
    reason = incomplete.get("reason") if isinstance(incomplete, Mapping) else None
    output = response.get("output")
    item_types = (
        [item.get("type") for item in output if isinstance(item, Mapping)]
        if isinstance(output, list)
        else []
    )
    return (
        "Responses API returned no usable structured output text "
        f"(status={status!r}, incomplete_reason={reason!r}, "
        f"output_item_types={item_types!r}, cause={type(error).__name__})"
    )


__all__ = [
    "OpenAIResponsesClient",
    "OpenAIResponsesHTTPError",
    "OpenAIResponsesOutputError",
]
