"""Bridge scored candidates to the existing resolver prediction contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from abrex.domain import AbbreviationDefinition, Document, PredictionMetadata
from abrex.scorers.base import ScoredCandidate
from abrex.scorers.execution import ScorerExecutor

if TYPE_CHECKING:
    from abrex.resolvers.base import PredictionRecord


def materialize_predictions(
    document: Document,
    scored: tuple[ScoredCandidate, ...],
    executor: ScorerExecutor,
    *,
    model_artifact_fingerprint: str | None = None,
) -> PredictionRecord:
    """Select and materialize candidates with explicit scorer provenance."""

    if any(item.document_id != document.document_id for item in scored):
        raise ValueError("Scored candidates must belong to the supplied document")
    scores = tuple(item.score for item in scored)
    accepted = executor.select(scores)
    predictions = tuple(
        _prediction(document, item, executor, model_artifact_fingerprint)
        for item, keep in zip(scored, accepted, strict=True)
        if keep
    )
    from abrex.resolvers.base import PredictionRecord

    return PredictionRecord(document.document_id, predictions=predictions)


def materialize_feature_predictions(
    scored: tuple[ScoredCandidate, ...],
    documents: Mapping[str, Document],
    executor: ScorerExecutor,
    *,
    model_artifact_fingerprint: str | None = None,
) -> tuple[PredictionRecord, ...]:
    """Group scored feature rows into deterministic resolver records."""

    grouped: dict[str, list[ScoredCandidate]] = {}
    for item in scored:
        grouped.setdefault(item.document_id, []).append(item)
    missing = sorted(set(grouped) - set(documents))
    if missing:
        raise ValueError(f"No canonical documents for scored IDs: {missing!r}")
    return tuple(
        materialize_predictions(
            documents[document_id],
            tuple(grouped[document_id]),
            executor,
            model_artifact_fingerprint=model_artifact_fingerprint,
        )
        for document_id in sorted(grouped)
    )


def _prediction(
    document: Document,
    item: ScoredCandidate,
    executor: ScorerExecutor,
    model_artifact_fingerprint: str | None,
) -> AbbreviationDefinition:
    candidate = item.candidate
    return AbbreviationDefinition(
        document_id=document.document_id,
        short_form=candidate.short_form,
        long_form=candidate.long_form,
        short_form_text=document.text_for(candidate.short_form),
        long_form_text=document.text_for(candidate.long_form),
        prediction=PredictionMetadata(
            score=item.score,
            component=executor.identity,
            component_version=executor.version,
            model_artifact_fingerprint=model_artifact_fingerprint,
            feature_config_fingerprint=executor.feature_config_fingerprint,
        ),
    )


__all__ = [
    "materialize_feature_predictions",
    "materialize_predictions",
]
