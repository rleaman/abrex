"""Source-grounded TypeSafe Jev candidate judgment resolver."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates import (
    Candidate,
    CandidatePipelineConfig,
    create_candidate_pipeline,
)
from abrex.config import ComponentSpec
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
)

JEV_RESOLVER_VERSION = "1"
JEV_POLICY_VERSION = "abrex-candidate-choice-v1"
JEV_MODEL = "jev-1.13.0"
CALIBRATION_GRID = tuple(index / 100 for index in range(50, 100, 5))


class JevResolverError(ValueError):
    """Base class for bounded Jev resolution failures."""


class JevBudgetError(JevResolverError):
    """Raised before a request would exceed a configured run limit."""


class JevResponseError(JevResolverError):
    """Raised when a service response violates the frozen response contract."""


class JevClient(Protocol):
    """Narrow SDK boundary used by the infrastructure resolver."""

    def system_one(self, **kwargs: object) -> object:
        """Return one typed System One response."""


def _default_generators() -> tuple[ComponentSpec, ...]:
    return (
        ComponentSpec(type="parenthetical", params={}),
        ComponentSpec(type="reverse_order", params={}),
        ComponentSpec(type="nested_parenthetical", params={}),
        ComponentSpec(type="clp_table_v5_1", params={}),
    )


class JevCandidateJudgeConfig(BaseModel):
    """Typed limits and scientific policy for one Jev resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = JEV_MODEL
    policy_version: str = JEV_POLICY_VERSION
    candidate_generators: tuple[ComponentSpec, ...] = Field(
        default_factory=_default_generators, min_length=1
    )
    confidence_threshold: float = Field(default=0.5, ge=0, le=1)
    cache_path: Path = Path(".cache/abrex/jev-candidate-judge.jsonl")
    cache_only: bool = False
    maximum_candidates_per_document: int = Field(default=512, ge=1)
    maximum_candidates_per_request: int = Field(default=64, ge=1, le=255)
    maximum_request_characters: int = Field(default=48_000, ge=1)
    maximum_network_requests: int = Field(default=500, ge=0)
    maximum_input_tokens: int = Field(default=10_000_000, ge=1)
    timeout_seconds: float = Field(default=30.0, gt=0)
    retries: int = Field(default=3, ge=0, le=10)
    concurrency: int = Field(default=8, ge=1, le=40)


@dataclass(frozen=True, slots=True)
class JevChoice:
    """One validated candidate judgment."""

    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True, slots=True)
class JevResponse:
    """Service metadata and choices retained in the content-addressed cache."""

    model: str
    request_id: str | None
    choices: dict[str, JevChoice]
    input_tokens: int | None
    output_tokens: int | None
    latency_seconds: float
    network_attempts: int
    cached: bool = False


class JevCandidateJudgeResolver:
    """Judge deterministic source-span candidates with batched Jev Choices."""

    identity = "jev_candidate_judge"
    version = JEV_RESOLVER_VERSION

    def __init__(self, *, client: JevClient | None = None, **params: object) -> None:
        self.config = JevCandidateJudgeConfig.model_validate(params)
        if self.config.model != JEV_MODEL:
            raise ValueError(
                f"T059 is frozen to {JEV_MODEL!r}; got {self.config.model!r}"
            )
        if self.config.policy_version != JEV_POLICY_VERSION:
            raise ValueError(
                f"T059 is frozen to policy {JEV_POLICY_VERSION!r}; got "
                f"{self.config.policy_version!r}"
            )
        self.pipeline = create_candidate_pipeline(
            CandidatePipelineConfig(
                generators=self.config.candidate_generators, deduplicate=True
            )
        )
        self._provided_client = client
        self._client_instance: JevClient | None = client
        self._lock = threading.Lock()
        self._network_requests = 0
        self._estimated_input_tokens = 0
        self._actual_input_tokens = 0
        self._cache = self._load_cache()

    @property
    def cache_identity(self) -> dict[str, object]:
        """Return every setting that can change predictions or request reuse."""

        return {
            "resolver": self.identity,
            "version": self.version,
            "model": self.config.model,
            "policy_version": self.config.policy_version,
            "threshold": self.config.confidence_threshold,
            "candidate_generators": [
                item.model_dump(mode="json")
                for item in self.config.candidate_generators
            ],
            "limits": {
                "maximum_candidates_per_document": (
                    self.config.maximum_candidates_per_document
                ),
                "maximum_candidates_per_request": (
                    self.config.maximum_candidates_per_request
                ),
                "maximum_request_characters": self.config.maximum_request_characters,
                "maximum_network_requests": self.config.maximum_network_requests,
                "maximum_input_tokens": self.config.maximum_input_tokens,
            },
        }

    def resolve(self, document: Document) -> tuple[AbbreviationDefinition, ...]:
        """Generate exact candidates, judge them, and return accepted pairs."""

        record = self.pipeline.generate(document)
        candidates = tuple(record.candidates)
        if not candidates:
            return ()
        if len(candidates) > self.config.maximum_candidates_per_document:
            raise JevBudgetError(
                f"document {document.document_id!r} produced {len(candidates)} "
                "candidates, exceeding maximum_candidates_per_document="
                f"{self.config.maximum_candidates_per_document}"
            )
        chunks = self._chunks(document, candidates)
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as pool:
            responses = tuple(
                pool.map(
                    lambda item: self._judge_chunk(document, item[0], item[1]),
                    enumerate(chunks),
                )
            )
        predictions: list[AbbreviationDefinition] = []
        for chunk, response in zip(chunks, responses, strict=True):
            for local_index, candidate in enumerate(chunk):
                question_id = f"candidate_{local_index:03d}"
                choice = response.choices[question_id]
                if choice.choice == "not_definition":
                    continue
                probability = choice.probabilities[choice.choice]
                if probability < self.config.confidence_threshold:
                    continue
                short_span = candidate.short_form
                long_span = candidate.long_form
                if choice.choice == "reverse":
                    short_span, long_span = long_span, short_span
                request_hash = self._request_hash(
                    *self._request(document, chunk), self.config.model
                )
                probabilities = json.dumps(
                    choice.probabilities, sort_keys=True, separators=(",", ":")
                )
                prediction = AbbreviationDefinition(
                    document.document_id,
                    short_form=short_span,
                    long_form=long_span,
                    short_form_text=document.text_for(short_span),
                    long_form_text=document.text_for(long_span),
                    provenance=AnnotationProvenance(
                        adapter_identity=self.identity,
                        adapter_version=self.version,
                        transformation_notes=(
                            f"policy={self.config.policy_version}",
                            f"choice={choice.choice}",
                            f"probabilities={probabilities}",
                            f"request_id={response.request_id or ''}",
                            f"latency_seconds={response.latency_seconds:.6f}",
                            f"network_attempts={response.network_attempts}",
                            f"cached={str(response.cached).lower()}",
                        ),
                    ),
                    prediction=PredictionMetadata(
                        confidence=probability,
                        component=self.identity,
                        component_version=self.version,
                        model_artifact_fingerprint=response.model,
                        feature_config_fingerprint=request_hash,
                    ),
                )
                prediction.validate_against(document)
                predictions.append(prediction)
        return tuple(_deduplicate_predictions(predictions))

    def _chunks(
        self, document: Document, candidates: tuple[Candidate, ...]
    ) -> tuple[tuple[Candidate, ...], ...]:
        chunks: list[tuple[Candidate, ...]] = []
        cursor = 0
        while cursor < len(candidates):
            end = min(
                len(candidates),
                cursor + self.config.maximum_candidates_per_request,
            )
            selected = candidates[cursor:end]
            while selected:
                state, questions = self._request(document, selected)
                if _json_characters(state, questions) <= (
                    self.config.maximum_request_characters
                ):
                    break
                selected = selected[:-1]
            if not selected:
                raise JevBudgetError(
                    f"document {document.document_id!r} cannot fit one candidate "
                    "within "
                    f"{self.config.maximum_request_characters} request characters"
                )
            chunks.append(selected)
            cursor += len(selected)
        return tuple(chunks)

    def _judge_chunk(
        self,
        document: Document,
        chunk_number: int,
        candidates: tuple[Candidate, ...],
    ) -> JevResponse:
        state, questions = self._request(document, candidates)
        request_hash = self._request_hash(state, questions, self.config.model)
        cached = self._cache.get(request_hash)
        if cached is not None:
            return JevResponse(
                cached.model,
                cached.request_id,
                cached.choices,
                cached.input_tokens,
                cached.output_tokens,
                cached.latency_seconds,
                0,
                True,
            )
        if self.config.cache_only:
            raise JevBudgetError(f"Jev cache miss for request {request_hash}")
        estimated_tokens = max(1, _json_characters(state, questions) // 4)
        self._reserve_tokens(estimated_tokens)
        attempts = 0
        started = time.perf_counter()
        while True:
            self._reserve_request()
            attempts += 1
            try:
                raw = self._client().system_one(
                    state=state,
                    questions=questions,
                    model=self.config.model,
                    timeout=self.config.timeout_seconds,
                )
                break
            except Exception as error:  # SDK boundary, re-raised with typed context
                if attempts > self.config.retries or not _retryable(error):
                    raise JevResolverError(
                        f"Jev request {request_hash} failed after {attempts} "
                        "attempt(s): "
                        f"{type(error).__name__}: {error}"
                    ) from error
                time.sleep(min(2.0, 0.25 * (2 ** (attempts - 1))))
        latency = time.perf_counter() - started
        response = _parse_response(
            raw,
            expected_questions=tuple(questions),
            latency_seconds=latency,
            network_attempts=attempts,
        )
        self._record_actual_tokens(response.input_tokens, estimated_tokens)
        self._cache_response(
            request_hash,
            state,
            questions,
            response,
            document_id=document.document_id,
            chunk_number=chunk_number,
        )
        return response

    def _request(
        self, document: Document, candidates: Sequence[Candidate]
    ) -> tuple[dict[str, object], dict[str, object]]:
        candidate_rows: dict[str, object] = {}
        questions: dict[str, object] = {}
        for index, candidate in enumerate(candidates):
            candidate.validate_against(document)
            candidate_id = f"candidate_{index:03d}"
            candidate_rows[candidate_id] = {
                "proposed_short_form": document.text_for(candidate.short_form),
                "proposed_long_form": document.text_for(candidate.long_form),
                "short_span": [candidate.short_form.start, candidate.short_form.end],
                "long_span": [candidate.long_form.start, candidate.long_form.end],
                "construction": candidate.construction,
            }
            questions[candidate_id] = {
                "type": "choice",
                "instructions": {
                    "question": (
                        "Does this exact pair express an abbreviation definition in "
                        "the supplied passage, and if so which span is the short form?"
                    ),
                    "state_reference": f"candidates.{candidate_id}",
                    "rules": [
                        "Judge only the quoted source passage and exact candidate "
                        "spans.",
                        "Do not invent, extend, or normalize either source span.",
                        "A co-occurrence without an explicit definition is not enough.",
                    ],
                },
                "criteria": {
                    "forward": (
                        "The proposed short form abbreviates the proposed long form."
                    ),
                    "reverse": (
                        "The proposed long-form span is actually the short form and "
                        "the proposed short-form span is its expansion."
                    ),
                    "not_definition": (
                        "The exact spans do not form an explicit abbreviation "
                        "definition."
                    ),
                },
            }
        state: dict[str, object] = {
            "document_id": document.document_id,
            "passage": document.text,
            "candidates": candidate_rows,
        }
        return state, questions

    def _client(self) -> JevClient:
        if self._client_instance is not None:
            return self._client_instance
        if not os.environ.get("TYPESAFE_API_KEY", "").strip():
            raise JevResolverError("TYPESAFE_API_KEY is required for a live cache miss")
        try:
            sdk = importlib.import_module("typesafe_sdk")
        except ImportError as error:
            raise JevResolverError(
                "Jev requires the optional dependency: pip install -e .[jev]"
            ) from error
        TypeSafeClient = sdk.TypeSafeClient
        self._client_instance = cast(JevClient, TypeSafeClient(model=self.config.model))
        return self._client_instance

    def _reserve_request(self) -> None:
        with self._lock:
            if self._network_requests >= self.config.maximum_network_requests:
                raise JevBudgetError(
                    "Jev network request budget exhausted at "
                    f"{self.config.maximum_network_requests}"
                )
            self._network_requests += 1

    def _reserve_tokens(self, estimate: int) -> None:
        with self._lock:
            if (
                self._estimated_input_tokens + estimate
                > self.config.maximum_input_tokens
            ):
                raise JevBudgetError(
                    "Jev estimated input-token budget would exceed "
                    f"{self.config.maximum_input_tokens}"
                )
            self._estimated_input_tokens += estimate

    def _record_actual_tokens(self, actual: int | None, estimate: int) -> None:
        with self._lock:
            self._actual_input_tokens += actual if actual is not None else estimate
            if self._actual_input_tokens > self.config.maximum_input_tokens:
                raise JevBudgetError(
                    "Jev reported input-token usage exceeded the configured budget"
                )

    def _load_cache(self) -> dict[str, JevResponse]:
        path = self.config.cache_path
        if not path.is_file():
            return {}
        result: dict[str, JevResponse] = {}
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    if value.get("policy_version") != self.config.policy_version:
                        continue
                    if value.get("model") != self.config.model:
                        continue
                    result[str(value["request_hash"])] = _response_from_mapping(
                        _mapping(value["response"], "response"), cached=True
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise JevResponseError(
                        f"invalid Jev cache entry at {path}:{line_number}: {error}"
                    ) from error
        return result

    def _cache_response(
        self,
        request_hash: str,
        state: Mapping[str, object],
        questions: Mapping[str, object],
        response: JevResponse,
        *,
        document_id: str,
        chunk_number: int,
    ) -> None:
        record = {
            "schema_version": "jev-cache-v1",
            "request_hash": request_hash,
            "policy_version": self.config.policy_version,
            "model": self.config.model,
            "document_id": document_id,
            "chunk_number": chunk_number,
            "state": state,
            "questions": questions,
            "response": _response_mapping(response),
        }
        with self._lock:
            existing = self._cache.get(request_hash)
            if existing is not None:
                return
            self.config.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.cache_path.open(
                "a", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            self._cache[request_hash] = response

    @staticmethod
    def _request_hash(
        state: Mapping[str, object], questions: Mapping[str, object], model: str
    ) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "model": model,
                    "policy_version": JEV_POLICY_VERSION,
                    "state": state,
                    "questions": questions,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Frozen threshold and strict pair classification counts."""

    threshold: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int


def calibrate_threshold(
    observations: Sequence[tuple[float, bool]],
    *,
    grid: Sequence[float] = CALIBRATION_GRID,
    total_positives: int | None = None,
) -> CalibrationResult:
    """Choose maximum strict F1, then precision, then the higher threshold."""

    if not observations:
        raise ValueError("calibration requires at least one observation")
    if not grid:
        raise ValueError("calibration grid must not be empty")
    results: list[CalibrationResult] = []
    observed_positive = sum(correct for _, correct in observations)
    total_positive = observed_positive if total_positives is None else total_positives
    if isinstance(total_positive, bool) or not isinstance(total_positive, int):
        raise TypeError("total_positives must be an integer or None")
    if total_positive < observed_positive:
        raise ValueError("total_positives cannot be below observed correct predictions")
    for threshold in grid:
        if not 0 <= threshold <= 1:
            raise ValueError("calibration thresholds must be between zero and one")
        accepted = [
            (probability, correct)
            for probability, correct in observations
            if probability >= threshold
        ]
        true_positives = sum(correct for _, correct in accepted)
        false_positives = len(accepted) - true_positives
        false_negatives = total_positive - true_positives
        precision = (
            true_positives / (true_positives + false_positives)
            if true_positives + false_positives
            else 0.0
        )
        recall = true_positives / total_positive if total_positive else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        results.append(
            CalibrationResult(
                threshold,
                precision,
                recall,
                f1,
                true_positives,
                false_positives,
                false_negatives,
            )
        )
    return max(results, key=lambda item: (item.f1, item.precision, item.threshold))


def _parse_response(
    raw: object,
    *,
    expected_questions: tuple[str, ...],
    latency_seconds: float,
    network_attempts: int,
) -> JevResponse:
    choices_value = getattr(raw, "choices", None)
    if not isinstance(choices_value, Mapping):
        raise JevResponseError("Jev response choices must be a mapping")
    choices: dict[str, JevChoice] = {}
    for question_id in expected_questions:
        answer = choices_value.get(question_id)
        if answer is None:
            raise JevResponseError(f"Jev response omitted {question_id}")
        choice = getattr(answer, "choice", None)
        confidence = getattr(answer, "confidence", None)
        probabilities_value = getattr(answer, "probabilities", None)
        if choice not in {"forward", "reverse", "not_definition"}:
            raise JevResponseError(f"invalid choice for {question_id}: {choice!r}")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            raise JevResponseError(f"invalid confidence for {question_id}")
        if not isinstance(probabilities_value, Mapping):
            raise JevResponseError(f"invalid probabilities for {question_id}")
        probabilities = {
            str(key): float(value) for key, value in probabilities_value.items()
        }
        if set(probabilities) != {"forward", "reverse", "not_definition"}:
            raise JevResponseError(f"incomplete probabilities for {question_id}")
        if any(value < 0 or value > 1 for value in probabilities.values()):
            raise JevResponseError(f"out-of-range probabilities for {question_id}")
        choices[question_id] = JevChoice(str(choice), float(confidence), probabilities)
    if set(choices_value) != set(expected_questions):
        raise JevResponseError("Jev response returned unexpected question IDs")
    usage = getattr(raw, "usage", None)
    return JevResponse(
        model=str(getattr(raw, "model", JEV_MODEL)),
        request_id=_optional_string(getattr(raw, "request_id", None)),
        choices=choices,
        input_tokens=_usage_value(usage, "input_tokens"),
        output_tokens=_usage_value(usage, "output_tokens"),
        latency_seconds=latency_seconds,
        network_attempts=network_attempts,
    )


def _response_mapping(response: JevResponse) -> dict[str, object]:
    return {
        "model": response.model,
        "request_id": response.request_id,
        "choices": {
            key: {
                "choice": value.choice,
                "confidence": value.confidence,
                "probabilities": value.probabilities,
            }
            for key, value in response.choices.items()
        },
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "latency_seconds": response.latency_seconds,
        "network_attempts": response.network_attempts,
    }


def _response_from_mapping(value: Mapping[str, Any], *, cached: bool) -> JevResponse:
    choices_value = _mapping(value.get("choices"), "choices")
    choices: dict[str, JevChoice] = {}
    for key, raw in choices_value.items():
        answer = _mapping(raw, "choice")
        probabilities = _mapping(answer.get("probabilities"), "probabilities")
        choices[str(key)] = JevChoice(
            _required_string(answer, "choice"),
            float(answer["confidence"]),
            {
                str(name): float(probability)
                for name, probability in probabilities.items()
            },
        )
    return JevResponse(
        _required_string(value, "model"),
        _optional_string(value.get("request_id")),
        choices,
        _optional_int(value.get("input_tokens")),
        _optional_int(value.get("output_tokens")),
        float(value["latency_seconds"]),
        int(value["network_attempts"]),
        cached,
    )


def _json_characters(state: object, questions: object) -> int:
    return len(
        json.dumps(
            {"state": state, "questions": questions},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _usage_value(usage: object, name: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, Mapping):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    return _optional_int(value)


def _retryable(error: Exception) -> bool:
    status = getattr(error, "status", None)
    if isinstance(status, int):
        return status in {408, 409, 429} or status >= 500
    name = type(error).__name__.casefold()
    return not any(value in name for value in ("auth", "badrequest", "validation"))


def _deduplicate_predictions(
    predictions: Sequence[AbbreviationDefinition],
) -> tuple[AbbreviationDefinition, ...]:
    result: list[AbbreviationDefinition] = []
    seen: set[tuple[object, ...]] = set()
    for prediction in predictions:
        key = (prediction.document_id, prediction.short_form, prediction.long_form)
        if key not in seen:
            result.append(prediction)
            seen.add(key)
    return tuple(result)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return cast(Mapping[str, Any], value)


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise TypeError(f"{key} must be a non-empty string")
    return result


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise JevResponseError("expected a string or null")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise JevResponseError("expected an integer or null")
    return value


__all__ = [
    "CalibrationResult",
    "JEV_MODEL",
    "JEV_POLICY_VERSION",
    "JevBudgetError",
    "JevCandidateJudgeConfig",
    "JevCandidateJudgeResolver",
    "JevResolverError",
    "JevResponseError",
    "calibrate_threshold",
]
