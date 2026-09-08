"""PLODv2 span detection behind an optional, injectable runtime boundary.

The detector deliberately emits independent one-form predictions.  Pairing is
owned by T024 and is never inferred from model scores here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    SourceTextSpan,
    TextSpan,
)

PLOD_VERSION = "plodv2-detector-v1"
DuplicatePolicy = Literal["deduplicate", "retain"]
Device = Literal["auto", "cpu", "cuda"]


class PlodConfig(BaseModel):
    """Validated runtime and segmentation settings for PLODv2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_path: str
    checkpoint_sha256: str | None = None
    device: Device = "cpu"
    batch_size: int = Field(default=1, ge=1)
    max_chars_per_window: int | None = Field(default=None, ge=1)
    window_overlap: int = Field(default=0, ge=0)
    duplicate_policy: DuplicatePolicy = "deduplicate"
    runtime_version: str = "flair-optional"

    @field_validator("checkpoint_sha256")
    @classmethod
    def _valid_hash(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("checkpoint_sha256 must be a lowercase SHA-256")
        return value

    def model_dump_for_identity(self) -> dict[str, object]:
        """Return only deterministic, JSON-compatible configuration values."""

        return cast(dict[str, object], self.model_dump(mode="json"))


@dataclass(frozen=True, slots=True)
class RawPlodSpan:
    """A tagger span before canonical validation and coordinate translation."""

    label: str
    start: int
    end: int
    score: float | None = None
    window_start: int = 0


@dataclass(frozen=True, slots=True)
class ValidatedPlodSpan:
    """A validated canonical span retaining the model's raw label and score."""

    label: Literal["SF", "LF"]
    span: TextSpan
    text: str
    score: float | None
    source_window_start: int


@dataclass(frozen=True, slots=True)
class PlodSpanRecord:
    """Serializable detector output for one document."""

    document_id: str
    raw_spans: tuple[RawPlodSpan, ...]
    validated_spans: tuple[ValidatedPlodSpan, ...]
    diagnostics: tuple[str, ...] = ()


class PlodTagger(Protocol):
    """Minimal runtime seam implemented by Flair and test doubles."""

    def predict(self, text: str) -> Iterable[RawPlodSpan]: ...


class _FlairTagger:
    def __init__(self, config: PlodConfig) -> None:
        try:
            from flair.data import Sentence
            from flair.models import SequenceTagger
        except ImportError as error:
            raise RuntimeError(
                "PLODv2 requires the optional Flair/PyTorch runtime; install "
                "docs/artifacts/plod-runtime-requirements.txt"
            ) from error
        checkpoint = Path(config.checkpoint_path)
        if not checkpoint.is_file():
            raise FileNotFoundError(f"PLODv2 checkpoint does not exist: {checkpoint}")
        if config.checkpoint_sha256 is not None:
            actual = _sha256_file(checkpoint)
            if actual != config.checkpoint_sha256:
                raise ValueError(
                    f"PLODv2 checkpoint hash mismatch: expected "
                    f"{config.checkpoint_sha256}, got {actual}"
                )
        if config.device == "cuda":
            try:
                import torch
            except ImportError as error:
                raise RuntimeError("PLODv2 CUDA mode requires PyTorch") from error
            if not torch.cuda.is_available():
                raise RuntimeError("PLODv2 CUDA was requested but is unavailable")
        try:
            import torch

            _ = torch.device("cuda" if config.device == "cuda" else "cpu")
        except ImportError as error:
            if config.device == "cuda":
                raise RuntimeError(
                    "PLODv2 CUDA mode requires PyTorch and Flair"
                ) from error
        self._sentence_type = Sentence
        self._tagger = SequenceTagger.load(str(checkpoint))

    def predict(self, text: str) -> Iterable[RawPlodSpan]:
        sentence = self._sentence_type(text)
        self._tagger.predict(sentence)
        for entity in sentence.get_spans("ner"):
            label = str(entity.get_label("ner").value)
            score = float(entity.get_label("ner").score)
            yield RawPlodSpan(label, entity.start_position, entity.end_position, score)


class PlodSpanDetector:
    """Detect and validate independent PLODv2 SF/LF spans."""

    identity = "plodv2_span_detector"
    version = PLOD_VERSION

    def __init__(
        self,
        *,
        checkpoint_path: str | None = None,
        checkpoint_sha256: str | None = None,
        device: Device = "cpu",
        batch_size: int = 1,
        max_chars_per_window: int | None = None,
        window_overlap: int = 0,
        duplicate_policy: DuplicatePolicy = "deduplicate",
        runtime_version: str = "flair-optional",
        config: PlodConfig | None = None,
        tagger: PlodTagger | None = None,
    ) -> None:
        self.config = config or PlodConfig(
            checkpoint_path=checkpoint_path or "",
            checkpoint_sha256=checkpoint_sha256,
            device=device,
            batch_size=batch_size,
            max_chars_per_window=max_chars_per_window,
            window_overlap=window_overlap,
            duplicate_policy=duplicate_policy,
            runtime_version=runtime_version,
        )
        self._tagger = tagger or _FlairTagger(self.config)

    @property
    def cache_identity(self) -> dict[str, object]:
        checkpoint = Path(self.config.checkpoint_path)
        fingerprint = (
            _sha256_file(checkpoint)
            if checkpoint.is_file()
            else self.config.checkpoint_sha256 or "missing"
        )
        return {
            "detector": self.identity,
            "version": self.version,
            "checkpoint_sha256": fingerprint,
            "config": self.config.model_dump_for_identity(),
        }

    def detect(self, document: Document) -> PlodSpanRecord:
        raw: list[RawPlodSpan] = []
        diagnostics: list[str] = []
        for window_start, window_text in _windows(
            document.text,
            self.config.max_chars_per_window,
            self.config.window_overlap,
        ):
            for span in self._tagger.predict(window_text):
                raw.append(
                    RawPlodSpan(
                        span.label,
                        span.start,
                        span.end,
                        span.score,
                        window_start,
                    )
                )
        validated: list[ValidatedPlodSpan] = []
        seen: set[tuple[str, int, int]] = set()
        for item in raw:
            label = {"AC": "SF", "SF": "SF", "LF": "LF"}.get(item.label)
            if label is None:
                diagnostics.append(f"ignored_label:{item.label}")
                continue
            start = item.window_start + item.start
            end = item.window_start + item.end
            try:
                canonical_span = TextSpan(start, end)
                document.validate_span(canonical_span)
            except (TypeError, ValueError) as error:
                diagnostics.append(f"invalid_span:{item.label}:{error}")
                continue
            key = (label, start, end)
            if self.config.duplicate_policy == "deduplicate" and key in seen:
                continue
            seen.add(key)
            validated.append(
                ValidatedPlodSpan(
                    cast(Literal["SF", "LF"], label),
                    canonical_span,
                    document.text_for(canonical_span),
                    item.score,
                    item.window_start,
                )
            )
        return PlodSpanRecord(
            document.document_id, tuple(raw), tuple(validated), tuple(diagnostics)
        )

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Expose independent spans through the standard resolver contract."""

        record = self.detect(document)
        for item in record.validated_spans:
            prediction = PredictionMetadata(
                score=item.score,
                component=self.identity,
                component_version=self.version,
                model_artifact_fingerprint=str(
                    self.cache_identity["checkpoint_sha256"]
                ),
                feature_config_fingerprint=_config_fingerprint(self.config),
            )
            provenance = AnnotationProvenance(
                source_record_id=document.document_id,
                adapter_identity=self.identity,
                adapter_version=self.version,
                original_short_form=(
                    SourceTextSpan(text=item.text) if item.label == "SF" else None
                ),
                original_long_form=(
                    SourceTextSpan(text=item.text) if item.label == "LF" else None
                ),
                transformation_notes=(f"plod_label:{item.label}",),
            )
            yield AbbreviationDefinition(
                document.document_id,
                short_form=item.span if item.label == "SF" else None,
                long_form=item.span if item.label == "LF" else None,
                short_form_text=item.text if item.label == "SF" else None,
                long_form_text=item.text if item.label == "LF" else None,
                provenance=provenance,
                prediction=prediction,
            )


def serialize_span_record(record: PlodSpanRecord) -> str:
    """Serialize detector output deterministically as one JSON object."""

    data = {
        "schema_version": "plod-spans-v1",
        "document_id": record.document_id,
        "raw_spans": [
            {
                "label": x.label,
                "start": x.start,
                "end": x.end,
                "score": x.score,
                "window_start": x.window_start,
            }
            for x in record.raw_spans
        ],
        "validated_spans": [
            {
                "label": x.label,
                "start": x.span.start,
                "end": x.span.end,
                "text": x.text,
                "score": x.score,
                "source_window_start": x.source_window_start,
            }
            for x in record.validated_spans
        ],
        "diagnostics": list(record.diagnostics),
    }
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _windows(text: str, limit: int | None, overlap: int) -> Iterable[tuple[int, str]]:
    if limit is None or len(text) <= limit:
        yield 0, text
        return
    if overlap >= limit:
        raise ValueError("window_overlap must be smaller than max_chars_per_window")
    step = limit - overlap
    for start in range(0, len(text), step):
        yield start, text[start : start + limit]
        if start + limit >= len(text):
            break


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _config_fingerprint(config: PlodConfig) -> str:
    return hashlib.sha256(
        json.dumps(
            config.model_dump_for_identity(), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


__all__ = [
    "PLOD_VERSION",
    "PlodConfig",
    "RawPlodSpan",
    "ValidatedPlodSpan",
    "PlodSpanRecord",
    "PlodTagger",
    "PlodSpanDetector",
    "serialize_span_record",
]
