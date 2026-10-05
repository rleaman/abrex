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
CLP_WORKER_REQUEST_V2_SCHEMA: Literal["clp-abbr-worker-request-v2"] = (
    "clp-abbr-worker-request-v2"
)
CLP_WORKER_RESPONSE_V2_SCHEMA: Literal["clp-abbr-worker-response-v2"] = (
    "clp-abbr-worker-response-v2"
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


class CLPWorkerPassageV2(BaseModel):
    """One ordered BioC passage with its exact canonical-text location."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: int = Field(ge=0)
    source_index: int = Field(ge=0)
    canonical_start: int = Field(ge=0)
    source_offset: int = Field(ge=0)
    section_type: str
    passage_type: str
    text: str
    xml: str | None = None


class CLPWorkerDocumentV2(BaseModel):
    """Structure-preserving input for one complete CLP section decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    source_filename: str = Field(min_length=1)
    start_position: int = Field(ge=0)
    text: str
    passages: tuple[CLPWorkerPassageV2, ...]

    @model_validator(mode="after")
    def valid_structure(self) -> CLPWorkerDocumentV2:
        """Require deterministic order and literal canonical-text agreement."""

        if not self.passages:
            raise ValueError("CLP V2 document requires at least one passage")
        if tuple(item.position for item in self.passages) != tuple(
            range(len(self.passages))
        ):
            raise ValueError("CLP V2 passage positions must be contiguous and ordered")
        if len({item.source_index for item in self.passages}) != len(self.passages):
            raise ValueError("CLP V2 source passage indexes must be unique")
        if self.start_position >= len(self.passages):
            raise ValueError("CLP V2 start_position is outside the passage sequence")
        for passage in self.passages:
            end = passage.canonical_start + len(passage.text)
            if self.text[passage.canonical_start : end] != passage.text:
                raise ValueError(
                    "CLP V2 passage text does not match its canonical location"
                )
        return self


class CLPWorkerRequestV2(BaseModel):
    """Prediction-only request retaining the structures required by full CLP."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["clp-abbr-worker-request-v2"] = CLP_WORKER_REQUEST_V2_SCHEMA
    request_id: str = Field(min_length=1)
    documents: tuple[CLPWorkerDocumentV2, ...]

    @model_validator(mode="after")
    def unique_documents(self) -> CLPWorkerRequestV2:
        """Require stable one-to-one document identity."""

        identities = [item.document_id for item in self.documents]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP V2 worker request document IDs must be unique")
        return self


class CLPWorkerSpanV2(BaseModel):
    """One half-open Unicode span in the request document's canonical text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> CLPWorkerSpanV2:
        """Reject empty or reversed spans."""

        if self.end <= self.start:
            raise ValueError("CLP V2 span end must be greater than start")
        return self


class CLPWorkerPairV2(BaseModel):
    """One CLP decision with explicit occurrence mapping status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pair_id: str = Field(min_length=1)
    decision: Literal["accepted", "rejected", "unscorable"]
    short_form: str = Field(min_length=1)
    long_form: str = Field(min_length=1)
    short_span: CLPWorkerSpanV2 | None = None
    long_span: CLPWorkerSpanV2 | None = None
    rule: str = Field(min_length=1)
    orientation: Literal["FIRST_IS_SF", "SECOND_IS_SF"]
    source_passage_indexes: tuple[int, ...]
    mapping_status: str = Field(min_length=1)


class CLPWorkerDocumentResultV2(BaseModel):
    """One complete structure-aware CLP section result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    disposition: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    pairs: tuple[CLPWorkerPairV2, ...]

    @model_validator(mode="after")
    def unique_pairs(self) -> CLPWorkerDocumentResultV2:
        """Reject duplicate pair identities within a document."""

        identities = [item.pair_id for item in self.pairs]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP V2 worker pair IDs must be unique per document")
        return self


class CLPWorkerResponseV2(BaseModel):
    """Pinned full-CLP response independent of sister-project Python types."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["clp-abbr-worker-response-v2"] = (
        CLP_WORKER_RESPONSE_V2_SCHEMA
    )
    request_id: str = Field(min_length=1)
    worker_identity: str = Field(min_length=1)
    worker_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    documents: tuple[CLPWorkerDocumentResultV2, ...]

    @model_validator(mode="after")
    def unique_documents(self) -> CLPWorkerResponseV2:
        """Reject duplicate result documents."""

        identities = [item.document_id for item in self.documents]
        if len(set(identities)) != len(identities):
            raise ValueError("CLP V2 worker response document IDs must be unique")
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


def map_clp_worker_response_v2(
    request: CLPWorkerRequestV2, response: CLPWorkerResponseV2
) -> tuple[CandidateGenerationResult, ...]:
    """Validate V2 identities and map only literal, explicitly located pairs."""

    if response.request_id != request.request_id:
        raise CLPWorkerProtocolError("CLP V2 worker response request_id mismatch")
    requested = {item.document_id: item for item in request.documents}
    returned = {item.document_id: item for item in response.documents}
    if set(returned) != set(requested):
        raise CLPWorkerProtocolError(
            "CLP V2 worker response document IDs do not match the request"
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
                    _diagnostic_v2(document_id, pair, f"clp_worker_{pair.decision}")
                )
                continue
            if pair.short_span is None or pair.long_span is None:
                diagnostics.append(
                    _diagnostic_v2(document_id, pair, "clp_worker_unscorable")
                )
                continue
            short_span = TextSpan(pair.short_span.start, pair.short_span.end)
            long_span = TextSpan(pair.long_span.start, pair.long_span.end)
            if (
                document.text_for(short_span) != pair.short_form
                or document.text_for(long_span) != pair.long_form
            ):
                raise CLPWorkerProtocolError(
                    f"CLP V2 pair {pair.pair_id} spans do not match request text"
                )
            candidates.append(
                Candidate(
                    document_id,
                    short_span,
                    long_span,
                    "clp_worker_v2_pair",
                    AnnotationProvenance(
                        source_corpus=response.worker_identity,
                        original_short_form=SourceTextSpan(
                            pair.short_span.start,
                            pair.short_span.end,
                            pair.short_form,
                        ),
                        original_long_form=SourceTextSpan(
                            pair.long_span.start,
                            pair.long_span.end,
                            pair.long_form,
                        ),
                        adapter_identity="clp_worker_v2",
                        adapter_version=response.worker_version,
                        transformation_notes=(
                            response.policy_version,
                            response.model_version,
                            pair.rule,
                            pair.pair_id,
                            pair.mapping_status,
                        ),
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


def _diagnostic_v2(
    document_id: str, pair: CLPWorkerPairV2, code: str
) -> CandidateDiagnostic:
    return CandidateDiagnostic(
        "info",
        code,
        (
            f"CLP V2 pair {pair.pair_id} ({pair.rule}) was not mapped: "
            f"{pair.mapping_status}"
        ),
        document_id,
        "pruned",
    )


__all__ = [
    "CLP_WORKER_REQUEST_SCHEMA",
    "CLP_WORKER_REQUEST_V2_SCHEMA",
    "CLP_WORKER_RESPONSE_SCHEMA",
    "CLP_WORKER_RESPONSE_V2_SCHEMA",
    "CLPWorkerDocument",
    "CLPWorkerDocumentResult",
    "CLPWorkerPair",
    "CLPWorkerProtocolError",
    "CLPWorkerRequest",
    "CLPWorkerResponse",
    "CLPWorkerDocumentResultV2",
    "CLPWorkerDocumentV2",
    "CLPWorkerPairV2",
    "CLPWorkerPassageV2",
    "CLPWorkerRequestV2",
    "CLPWorkerResponseV2",
    "CLPWorkerSpanV2",
    "map_clp_worker_response",
    "map_clp_worker_response_v2",
]
