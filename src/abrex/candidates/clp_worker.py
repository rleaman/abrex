"""Versioned JSON boundary for optional CellLiteraturePipeline workers."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abrex.candidates.base import (
    Candidate,
    CandidateDiagnostic,
    CandidateGenerationResult,
)
from abrex.domain import AnnotationProvenance, Document, SourceTextSpan, TextSpan

CLP_WORKER_REQUEST_SCHEMA: Literal["clp-abbr-worker-request-v1"] = (
    "clp-abbr-worker-request-v1"
)
CLP_WORKER_RESPONSE_SCHEMA: Literal["clp-abbr-worker-response-v1"] = (
    "clp-abbr-worker-response-v1"
)


class CLPWorkerProtocolError(ValueError):
    """A worker response is inconsistent with its immutable request."""


class CLPWorkerDocument(BaseModel):
    """One source-only document sent to an external CLP worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    text: str


class CLPWorkerRequest(BaseModel):
    """Prediction-only request; it deliberately has no annotation field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["clp-abbr-worker-request-v1"] = CLP_WORKER_REQUEST_SCHEMA
    request_id: str = Field(min_length=1)
    documents: tuple[CLPWorkerDocument, ...]

    @model_validator(mode="after")
    def unique_documents(self) -> CLPWorkerRequest:
        """Require stable one-to-one document identity."""

        identities = [item.document_id for item in self.documents]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP worker request document IDs must be unique")
        return self


class CLPWorkerPair(BaseModel):
    """One text-grounded CLP decision returned by a worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pair_id: str = Field(min_length=1)
    decision: Literal["accepted", "rejected", "unscorable"]
    short_form: str = Field(min_length=1)
    long_form: str = Field(min_length=1)
    rule: str = Field(min_length=1)


class CLPWorkerDocumentResult(BaseModel):
    """All decisions for one requested source document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    pairs: tuple[CLPWorkerPair, ...]

    @model_validator(mode="after")
    def unique_pairs(self) -> CLPWorkerDocumentResult:
        """Reject duplicate pair identities within a document."""

        identities = [item.pair_id for item in self.pairs]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP worker pair IDs must be unique per document")
        return self


class CLPWorkerResponse(BaseModel):
    """Versioned response independent of sister-project Python internals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["clp-abbr-worker-response-v1"] = CLP_WORKER_RESPONSE_SCHEMA
    request_id: str = Field(min_length=1)
    worker_identity: str = Field(min_length=1)
    worker_version: str = Field(min_length=1)
    documents: tuple[CLPWorkerDocumentResult, ...]

    @model_validator(mode="after")
    def unique_documents(self) -> CLPWorkerResponse:
        """Reject duplicate result documents."""

        identities = [item.document_id for item in self.documents]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP worker response document IDs must be unique")
        return self


def map_clp_worker_response(
    request: CLPWorkerRequest, response: CLPWorkerResponse
) -> tuple[CandidateGenerationResult, ...]:
    """Validate a worker response and map only unambiguous accepted pairs."""

    if response.request_id != request.request_id:
        raise CLPWorkerProtocolError("CLP worker response request_id mismatch")
    requested = {item.document_id: item for item in request.documents}
    returned = {item.document_id: item for item in response.documents}
    if set(returned) != set(requested):
        raise CLPWorkerProtocolError(
            "CLP worker response document IDs do not match the request"
        )
    results: list[CandidateGenerationResult] = []
    for document_id in sorted(requested):
        source = requested[document_id]
        document = Document(source.document_id, source.text)
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for pair in returned[document_id].pairs:
            if pair.decision != "accepted":
                diagnostics.append(
                    _diagnostic(document_id, pair, f"clp_worker_{pair.decision}")
                )
                continue
            short_span = _unique_span(document.text, pair.short_form)
            long_span = _unique_span(document.text, pair.long_form)
            if short_span is None or long_span is None:
                diagnostics.append(
                    _diagnostic(document_id, pair, "clp_worker_ambiguous_mapping")
                )
                continue
            candidates.append(
                Candidate(
                    document_id,
                    short_span,
                    long_span,
                    "clp_worker_pair",
                    AnnotationProvenance(
                        source_corpus=response.worker_identity,
                        original_short_form=SourceTextSpan(text=pair.short_form),
                        original_long_form=SourceTextSpan(text=pair.long_form),
                        adapter_identity="clp_worker_v1",
                        adapter_version=response.worker_version,
                        transformation_notes=(pair.rule, pair.pair_id),
                    ),
                )
            )
        results.append(
            CandidateGenerationResult(
                document_id, tuple(candidates), tuple(diagnostics)
            )
        )
    return tuple(results)


def _unique_span(text: str, value: str) -> TextSpan | None:
    matches = tuple(re.finditer(re.escape(value), text))
    if len(matches) != 1:
        return None
    return TextSpan(matches[0].start(), matches[0].end())


def _diagnostic(
    document_id: str, pair: CLPWorkerPair, code: str
) -> CandidateDiagnostic:
    return CandidateDiagnostic(
        "info",
        code,
        f"CLP pair {pair.pair_id} ({pair.rule}) was not mapped to a candidate",
        document_id,
        "pruned",
    )


__all__ = [
    "CLP_WORKER_REQUEST_SCHEMA",
    "CLP_WORKER_RESPONSE_SCHEMA",
    "CLPWorkerDocument",
    "CLPWorkerDocumentResult",
    "CLPWorkerPair",
    "CLPWorkerProtocolError",
    "CLPWorkerRequest",
    "CLPWorkerResponse",
    "map_clp_worker_response",
]
