"""Validation of resolver output against an unchanged canonical document."""

from __future__ import annotations

from collections.abc import Iterable

from abrex.domain import AbbreviationDefinition, Document
from abrex.resolvers.base import (
    PredictionDiagnostic,
    PredictionValidationError,
    PredictionValidationMode,
    PredictionValidationResult,
    ResolverMetadata,
    attach_resolver_metadata,
)


def validate_predictions(
    document: Document,
    predictions: Iterable[object],
    *,
    resolver: ResolverMetadata,
    mode: PredictionValidationMode = "strict",
) -> PredictionValidationResult:
    """Validate and annotate resolver output without changing document text.

    In permissive mode invalid predictions are dropped and counted in the
    returned diagnostics. Strict mode raises after collecting all diagnostics.
    No duplicate prediction policy is applied; duplicate values are retained.
    """

    if not isinstance(document, Document):
        raise TypeError("document must be a Document")
    if mode not in ("strict", "permissive"):
        raise ValueError(f"Unsupported prediction validation mode: {mode!r}")

    valid: list[AbbreviationDefinition] = []
    diagnostics: list[PredictionDiagnostic] = []
    seen = 0
    for index, candidate in enumerate(predictions):
        seen += 1
        if not isinstance(candidate, AbbreviationDefinition):
            diagnostics.append(
                PredictionDiagnostic(
                    "error",
                    "INVALID_PREDICTION_TYPE",
                    "Resolver output must contain AbbreviationDefinition values",
                    document.document_id,
                    action="dropped",
                    prediction_index=index,
                    phase="validation",
                    details=(("actual_type", type(candidate).__name__),),
                )
            )
            continue
        try:
            candidate.validate_against(document)
        except (TypeError, ValueError) as error:
            diagnostics.append(
                PredictionDiagnostic(
                    "error",
                    "INVALID_PREDICTION",
                    str(error),
                    document.document_id,
                    action="dropped",
                    prediction_index=index,
                    phase="validation",
                )
            )
            continue
        valid.append(attach_resolver_metadata(candidate, resolver))

    result = PredictionValidationResult(tuple(valid), tuple(diagnostics), seen)
    if mode == "strict" and diagnostics:
        raise PredictionValidationError(
            f"Resolver produced invalid predictions for {document.document_id!r}",
            document_id=document.document_id,
            result=result,
        )
    return result


__all__ = ["validate_predictions"]
