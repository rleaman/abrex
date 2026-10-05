"""Source-grounded direct abbreviation extraction with bounded model access."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    TextSpan,
)
from abrex.resolvers.base import (
    PredictionDiagnostic,
    ResolverResolution,
)

DIRECT_EXTRACTION_VERSION = "2"
DIRECT_POLICY_VERSION = "source-grounded-direct-v1"
DIRECT_PROMPT_VERSION = "abrex-direct-extraction-2026-10-05-v1"
DIRECT_MODEL = "gpt-6-luna"


class DirectExtractionError(ValueError):
    """Base class for direct-extraction failures."""


class DirectExtractionBudgetError(DirectExtractionError):
    """A request would exceed a configured usage or monetary limit."""


class DirectExtractionResponseError(DirectExtractionError):
    """A provider response violated the frozen response contract."""


class GroundedSpan(BaseModel):
    """One literal occurrence and its Unicode half-open offsets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class GroundedPair(BaseModel):
    """One proposed abbreviation relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    short_form: GroundedSpan
    long_form: GroundedSpan
    evidence: Literal["contiguous", "discontinuous"]


class DirectExtractionOutput(BaseModel):
    """Strict structured output returned by the extraction model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pairs: tuple[GroundedPair, ...]


class DirectExtractionConfig(BaseModel):
    """Frozen prompt identity plus explicit request and spending bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = DIRECT_MODEL
    policy_version: str = DIRECT_POLICY_VERSION
    prompt_version: str = DIRECT_PROMPT_VERSION
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = (
        "medium"
    )
    cache_path: Path = Path(".cache/abrex/direct-extraction.jsonl")
    cache_only: bool = False
    endpoint: str = "https://api.openai.com/v1/responses"
    api_key_env: str = "OPENAI_API_KEY"
    maximum_document_characters: int = Field(default=48_000, ge=1)
    maximum_network_attempts: int = Field(default=60, ge=0)
    maximum_estimated_input_tokens: int = Field(default=100_000, ge=1)
    maximum_output_tokens_per_request: int = Field(default=2_048, ge=64)
    monetary_cap_usd: float = Field(default=0.25, gt=0)
    input_usd_per_million_tokens: float = Field(default=0.10, ge=0)
    output_usd_per_million_tokens: float = Field(default=0.50, ge=0)
    timeout_seconds: float = Field(default=60.0, gt=0)
    retries: int = Field(default=2, ge=0, le=10)


class DirectExtractionClient(Protocol):
    """Narrow provider boundary for one structured extraction request."""

    def create_response(
        self, *, payload: Mapping[str, object], timeout_seconds: float
    ) -> Mapping[str, object]:
        """Return a normalized response mapping."""


class DirectExtractionResolver:
    """Extract literal pairs directly, independently of candidate generators."""

    identity = "openai_direct_extraction"
    version = DIRECT_EXTRACTION_VERSION

    def __init__(self, *, client: DirectExtractionClient, **params: object) -> None:
        self.config = DirectExtractionConfig.model_validate(params)
        if self.config.policy_version != DIRECT_POLICY_VERSION:
            raise ValueError(
                f"Unsupported direct extraction policy {self.config.policy_version!r}"
            )
        if self.config.prompt_version != DIRECT_PROMPT_VERSION:
            raise ValueError(
                f"Unsupported direct extraction prompt {self.config.prompt_version!r}"
            )
        self._client = client
        self._lock = threading.Lock()
        self._network_attempts = 0
        self._estimated_input_tokens = 0
        self._actual_input_tokens = 0
        self._actual_output_tokens = 0
        self._cache_hits = 0
        self._cache = self._load_cache()

    @property
    def cache_identity(self) -> dict[str, object]:
        """Return every setting that can affect a response or its reuse."""

        return {
            "resolver": self.identity,
            "version": self.version,
            "endpoint": self.config.endpoint,
            "model": self.config.model,
            "policy_version": self.config.policy_version,
            "prompt_version": self.config.prompt_version,
            "reasoning_effort": self.config.reasoning_effort,
            "schema": DirectExtractionOutput.model_json_schema(),
            "maximum_output_tokens_per_request": (
                self.config.maximum_output_tokens_per_request
            ),
        }

    @property
    def usage(self) -> dict[str, int | float]:
        """Return cumulative non-cached usage observed by this instance."""

        return {
            "network_attempts": self._network_attempts,
            "estimated_input_tokens": self._estimated_input_tokens,
            "actual_input_tokens": self._actual_input_tokens,
            "actual_output_tokens": self._actual_output_tokens,
            "cache_hits": self._cache_hits,
            "actual_cost_usd": self._cost(
                self._actual_input_tokens, self._actual_output_tokens
            ),
        }

    def resolve(self, document: Document) -> tuple[AbbreviationDefinition, ...]:
        """Return only exact, contiguous, source-validated predictions."""

        return cast(
            tuple[AbbreviationDefinition, ...],
            self.resolve_detailed(document).predictions,
        )

    def resolve_detailed(self, document: Document) -> ResolverResolution:
        """Extract pairs and retain every abstention or rejected output."""

        if len(document.text) > self.config.maximum_document_characters:
            raise DirectExtractionBudgetError(
                f"document {document.document_id!r} has {len(document.text)} "
                "characters, exceeding maximum_document_characters="
                f"{self.config.maximum_document_characters}"
            )
        request = self.request_payload(document)
        request_hash = _sha256_json(
            {"endpoint": self.config.endpoint, "payload": request}
        )
        response, _cached = self._response(request, request_hash)
        output = self._parse_output(response)
        predictions: list[AbbreviationDefinition] = []
        diagnostics: list[PredictionDiagnostic] = [
            PredictionDiagnostic(
                "info",
                "DIRECT_REQUEST_COMPLETED",
                "The structured extraction request completed successfully",
                document.document_id,
                phase="extraction",
                details=_request_details(response, request_hash),
            )
        ]
        seen: set[tuple[int, int, int, int]] = set()
        for index, pair in enumerate(output.pairs):
            details = _pair_details(pair)
            if pair.evidence == "discontinuous":
                diagnostics.append(
                    PredictionDiagnostic(
                        "info",
                        "DIRECT_DISCONTINUOUS_EVIDENCE",
                        "Discontinuous evidence is retained outside exact-pair scoring",
                        document.document_id,
                        action="dropped",
                        prediction_index=index,
                        phase="source_grounding",
                        details=details,
                    )
                )
                continue
            problem = _grounding_problem(document, pair)
            if problem is not None:
                diagnostics.append(
                    PredictionDiagnostic(
                        "warning",
                        "DIRECT_UNSUPPORTED_OUTPUT",
                        problem,
                        document.document_id,
                        action="dropped",
                        prediction_index=index,
                        phase="source_grounding",
                        details=details,
                    )
                )
                continue
            key = (
                pair.short_form.start,
                pair.short_form.end,
                pair.long_form.start,
                pair.long_form.end,
            )
            if key in seen:
                diagnostics.append(
                    PredictionDiagnostic(
                        "info",
                        "DIRECT_DUPLICATE_OUTPUT",
                        "Duplicate grounded pair was dropped",
                        document.document_id,
                        action="dropped",
                        prediction_index=index,
                        phase="deduplication",
                        details=details,
                    )
                )
                continue
            seen.add(key)
            predictions.append(
                self._prediction(document, pair, response, request_hash, index)
            )
        if not output.pairs:
            diagnostics.append(
                PredictionDiagnostic(
                    "info",
                    "DIRECT_ABSTAINED",
                    "The extractor returned no abbreviation relations",
                    document.document_id,
                    phase="extraction",
                )
            )
        return ResolverResolution(tuple(predictions), tuple(diagnostics))

    def request_payload(self, document: Document) -> dict[str, object]:
        """Return the complete deterministic provider payload for audit."""

        return {
            "model": self.config.model,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": _developer_prompt()}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "document_id": document.document_id,
                                    "text": document.text,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "abbreviation_relations",
                    "strict": True,
                    "schema": DirectExtractionOutput.model_json_schema(),
                }
            },
            "max_output_tokens": self.config.maximum_output_tokens_per_request,
            "reasoning": {"effort": self.config.reasoning_effort},
            "metadata": {
                "policy_version": self.config.policy_version,
                "prompt_version": self.config.prompt_version,
                "document_id": document.document_id,
            },
        }

    def _response(
        self, request: Mapping[str, object], request_hash: str
    ) -> tuple[Mapping[str, object], bool]:
        cached = self._cache.get(request_hash)
        if cached is not None:
            with self._lock:
                self._cache_hits += 1
            return cached, True
        if self.config.cache_only:
            raise DirectExtractionBudgetError(
                f"Direct extraction cache miss for request {request_hash}"
            )
        estimated = max(1, len(_json(request)) // 4)
        self._reserve_tokens_and_cost(estimated)
        attempts = 0
        started = time.perf_counter()
        while True:
            self._reserve_attempt()
            attempts += 1
            try:
                raw = self._client.create_response(
                    payload=request, timeout_seconds=self.config.timeout_seconds
                )
                break
            except Exception as error:  # provider boundary
                if attempts > self.config.retries or not _retryable(error):
                    raise DirectExtractionError(
                        f"Direct extraction request {request_hash} failed after "
                        f"{attempts} attempt(s): {type(error).__name__}: {error}"
                    ) from error
                time.sleep(min(2.0, 0.25 * (2 ** (attempts - 1))))
        response = dict(raw)
        response["latency_seconds"] = time.perf_counter() - started
        response["network_attempts"] = attempts
        input_tokens, output_tokens = _usage(response)
        with self._lock:
            self._actual_input_tokens += input_tokens
            self._actual_output_tokens += output_tokens
            if (
                self._cost(self._actual_input_tokens, self._actual_output_tokens)
                > self.config.monetary_cap_usd
            ):
                raise DirectExtractionBudgetError(
                    "Provider usage exceeded monetary_cap_usd; response was not cached"
                )
        self._parse_output(response)
        self._cache_response(request_hash, response)
        return response, False

    def _prediction(
        self,
        document: Document,
        pair: GroundedPair,
        response: Mapping[str, object],
        request_hash: str,
        index: int,
    ) -> AbbreviationDefinition:
        request_id = response.get("request_id")
        model = response.get("model")
        prediction = AbbreviationDefinition(
            document.document_id,
            short_form=TextSpan(pair.short_form.start, pair.short_form.end),
            long_form=TextSpan(pair.long_form.start, pair.long_form.end),
            short_form_text=pair.short_form.quote,
            long_form_text=pair.long_form.quote,
            provenance=AnnotationProvenance(
                adapter_identity=self.identity,
                adapter_version=self.version,
                transformation_notes=(
                    f"policy={self.config.policy_version}",
                    f"prompt={self.config.prompt_version}",
                    f"output_index={index}",
                    f"request_id={request_id if isinstance(request_id, str) else ''}",
                    f"latency_seconds={_latency(response):.6f}",
                    f"network_attempts={_network_attempts(response)}",
                    f"input_tokens={_usage(response)[0]}",
                    f"output_tokens={_usage(response)[1]}",
                    "literal_quotes_validated=true",
                    "unicode_offsets=python-code-points-half-open",
                ),
            ),
            prediction=PredictionMetadata(
                component=self.identity,
                component_version=self.version,
                model_artifact_fingerprint=(
                    model if isinstance(model, str) else self.config.model
                ),
                feature_config_fingerprint=request_hash,
            ),
        )
        prediction.validate_against(document)
        return prediction

    def _parse_output(self, response: Mapping[str, object]) -> DirectExtractionOutput:
        raw = response.get("output")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as error:
                raise DirectExtractionResponseError(
                    f"Direct extraction output is not JSON: {error.msg}"
                ) from error
        try:
            return DirectExtractionOutput.model_validate(raw)
        except ValidationError as error:
            raise DirectExtractionResponseError(
                f"Invalid direct extraction response: {error}"
            ) from error

    def _reserve_attempt(self) -> None:
        with self._lock:
            if self._network_attempts >= self.config.maximum_network_attempts:
                raise DirectExtractionBudgetError(
                    "Direct extraction network-attempt budget exhausted"
                )
            self._network_attempts += 1

    def _reserve_tokens_and_cost(self, estimated: int) -> None:
        with self._lock:
            if (
                self._estimated_input_tokens + estimated
                > self.config.maximum_estimated_input_tokens
            ):
                raise DirectExtractionBudgetError(
                    "Direct extraction estimated input-token budget exhausted"
                )
            worst_cost = self._cost(
                self._actual_input_tokens + estimated,
                self._actual_output_tokens
                + self.config.maximum_output_tokens_per_request,
            )
            if worst_cost > self.config.monetary_cap_usd:
                raise DirectExtractionBudgetError(
                    "Direct extraction request could exceed monetary_cap_usd"
                )
            self._estimated_input_tokens += estimated

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.config.input_usd_per_million_tokens
            + output_tokens * self.config.output_usd_per_million_tokens
        ) / 1_000_000

    def _load_cache(self) -> dict[str, Mapping[str, object]]:
        if not self.config.cache_path.exists():
            return {}
        result: dict[str, Mapping[str, object]] = {}
        try:
            lines = self.config.cache_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise TypeError("cache row must be an object")
                request_hash = raw.get("request_hash")
                response = raw.get("response")
                if not isinstance(request_hash, str) or not isinstance(response, dict):
                    raise TypeError("cache row requires request_hash and response")
                self._parse_output(cast(Mapping[str, object], response))
                if request_hash in result:
                    raise ValueError(f"duplicate request hash {request_hash}")
                result[request_hash] = cast(Mapping[str, object], response)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise DirectExtractionResponseError(
                f"Invalid direct extraction cache {self.config.cache_path}: {error}"
            ) from error
        return result

    def _cache_response(
        self, request_hash: str, response: Mapping[str, object]
    ) -> None:
        row = {"request_hash": request_hash, "response": dict(response)}
        path = self.config.cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if request_hash in self._cache:
                return
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(_json(row) + "\n")
            self._cache[request_hash] = dict(response)


def create_openai_direct_extractor(**params: object) -> DirectExtractionResolver:
    """Construct the registered resolver with the HTTP infrastructure adapter."""

    from abrex.infrastructure.openai_responses import OpenAIResponsesClient

    config = DirectExtractionConfig.model_validate(params)
    client = OpenAIResponsesClient(
        endpoint=config.endpoint, api_key_env=config.api_key_env
    )
    return DirectExtractionResolver(client=client, **config.model_dump(mode="python"))


def _developer_prompt() -> str:
    return (
        "Extract abbreviation-definition relations stated in the supplied text. "
        "Return each literal short-form occurrence and its literal long-form "
        "occurrence. Offsets are zero-based Unicode code-point offsets into the "
        "exact supplied text and use half-open [start,end) intervals. Copy quotes "
        "exactly: text[start:end] must equal quote. Do not normalize, infer missing "
        "text, or use external knowledge. Mark evidence discontinuous when a "
        "definition cannot be represented by one literal span. Omit uncertain or "
        "unsupported relations. Return all supported relations, including ones that "
        "a parenthesis-based candidate generator could miss."
    )


def _grounding_problem(document: Document, pair: GroundedPair) -> str | None:
    for label, span in (("short_form", pair.short_form), ("long_form", pair.long_form)):
        if span.end <= span.start:
            return f"{label} span must be non-empty"
        if span.end > len(document.text):
            return f"{label} span exceeds document length"
        if document.text[span.start : span.end] != span.quote:
            return f"{label} quote does not match the stated occurrence"
    if (
        pair.short_form.start == pair.long_form.start
        and pair.short_form.end == pair.long_form.end
    ):
        return "short-form and long-form occurrences must be distinct"
    return None


def _pair_details(pair: GroundedPair) -> tuple[tuple[str, str], ...]:
    return (
        ("short_form", pair.short_form.quote),
        ("short_span", f"[{pair.short_form.start},{pair.short_form.end})"),
        ("long_form", pair.long_form.quote),
        ("long_span", f"[{pair.long_form.start},{pair.long_form.end})"),
        ("evidence", pair.evidence),
    )


def _request_details(
    response: Mapping[str, object], request_hash: str
) -> tuple[tuple[str, str], ...]:
    request_id = response.get("request_id")
    model = response.get("model")
    input_tokens, output_tokens = _usage(response)
    return (
        ("request_hash", request_hash),
        ("request_id", request_id if isinstance(request_id, str) else ""),
        ("model", model if isinstance(model, str) else ""),
        ("latency_seconds", f"{_latency(response):.6f}"),
        ("network_attempts", str(_network_attempts(response))),
        ("input_tokens", str(input_tokens)),
        ("output_tokens", str(output_tokens)),
    )


def _usage(response: Mapping[str, object]) -> tuple[int, int]:
    usage = response.get("usage", {})
    if not isinstance(usage, Mapping):
        raise DirectExtractionResponseError("response usage must be an object")
    values: list[int] = []
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DirectExtractionResponseError(
                f"response usage {key} must be a non-negative integer"
            )
        values.append(value)
    return values[0], values[1]


def _latency(response: Mapping[str, object]) -> float:
    value = response.get("latency_seconds", 0.0)
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise DirectExtractionResponseError(
            "response latency_seconds must be a non-negative number"
        )
    return float(value)


def _network_attempts(response: Mapping[str, object]) -> int:
    value = response.get("network_attempts", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DirectExtractionResponseError(
            "response network_attempts must be a non-negative integer"
        )
    return value


def _retryable(error: Exception) -> bool:
    status = getattr(error, "status", None)
    if isinstance(status, int):
        return status in {408, 409, 429} or status >= 500
    name = type(error).__name__.casefold()
    return not any(value in name for value in ("auth", "badrequest", "validation"))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "DIRECT_MODEL",
    "DIRECT_POLICY_VERSION",
    "DIRECT_PROMPT_VERSION",
    "DirectExtractionBudgetError",
    "DirectExtractionClient",
    "DirectExtractionConfig",
    "DirectExtractionError",
    "DirectExtractionOutput",
    "DirectExtractionResolver",
    "DirectExtractionResponseError",
    "GroundedPair",
    "GroundedSpan",
    "create_openai_direct_extractor",
]
