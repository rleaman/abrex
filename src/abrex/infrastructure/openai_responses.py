"""Minimal OpenAI Responses API adapter for structured direct extraction."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import cast


class OpenAIResponsesHTTPError(RuntimeError):
    """An HTTP request to the Responses API failed."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


class OpenAIResponsesClient:
    """Send one JSON request and normalize its structured text response."""

    def __init__(self, *, endpoint: str, api_key_env: str) -> None:
        self.endpoint = endpoint
        self.api_key_env = api_key_env

    def create_response(
        self, *, payload: Mapping[str, object], timeout_seconds: float
    ) -> Mapping[str, object]:
        """Return model, request ID, parsed output text, and token usage."""

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise OpenAIResponsesHTTPError(
                401, f"Environment variable {self.api_key_env!r} is not set"
            )
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
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
        output_text = _output_text(cast(Mapping[str, object], raw))
        usage = raw.get("usage", {})
        if not isinstance(usage, dict):
            raise TypeError("Responses API usage must be an object")
        return {
            "model": raw.get("model"),
            "request_id": raw.get("id"),
            "output": output_text,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        }


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


__all__ = ["OpenAIResponsesClient", "OpenAIResponsesHTTPError"]
