"""Mapping from resolver predictions to downstream article entities."""

from __future__ import annotations

from dataclasses import dataclass

from abrex.domain import AbbreviationDefinition, TextSpan
from abrex.literature.models import ArticleDocument
from abrex.resolvers import PredictionDiagnostic, PredictionRecord, ResolverMetadata


@dataclass(frozen=True, slots=True)
class ArticleEntity:
    """A downstream-friendly prediction with article and section provenance.

    Canonical spans remain available in ``short_form``/``long_form``.  The
    optional section spans are populated only when a canonical span is fully
    contained in one source section.  ``mapping_issues`` makes ambiguous
    cross-section predictions observable to consumers.
    """

    article_id: str
    pmid: str | None
    pmcid: str | None
    document_id: str
    document_section_id: str | None
    short_form: TextSpan | None
    long_form: TextSpan | None
    short_form_text: str | None
    long_form_text: str | None
    short_form_section_id: str | None
    long_form_section_id: str | None
    short_form_section_span: TextSpan | None
    long_form_section_span: TextSpan | None
    resolver: ResolverMetadata
    mapping_issues: tuple[str, ...] = ()

    @classmethod
    def from_prediction(
        cls,
        source: ArticleDocument,
        prediction: AbbreviationDefinition,
        resolver: ResolverMetadata,
    ) -> ArticleEntity:
        short_location = source.location_for_span(prediction.short_form)
        long_location = source.location_for_span(prediction.long_form)
        issues: list[str] = []
        if prediction.short_form is not None and short_location is None:
            issues.append("short_form_not_contained_in_one_section")
        if prediction.long_form is not None and long_location is None:
            issues.append("long_form_not_contained_in_one_section")
        return cls(
            article_id=source.provenance.article_id,
            pmid=source.provenance.pmid,
            pmcid=source.provenance.pmcid,
            document_id=source.document.document_id,
            document_section_id=source.provenance.section_id,
            short_form=prediction.short_form,
            long_form=prediction.long_form,
            short_form_text=prediction.short_form_text,
            long_form_text=prediction.long_form_text,
            short_form_section_id=(short_location[0] if short_location else None),
            long_form_section_id=(long_location[0] if long_location else None),
            short_form_section_span=(short_location[1] if short_location else None),
            long_form_section_span=(long_location[1] if long_location else None),
            resolver=resolver,
            mapping_issues=tuple(issues),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible downstream record."""

        return {
            "article_id": self.article_id,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
            "document_id": self.document_id,
            "document_section_id": self.document_section_id,
            "short_form": _span(self.short_form),
            "long_form": _span(self.long_form),
            "short_form_text": self.short_form_text,
            "long_form_text": self.long_form_text,
            "short_form_section_id": self.short_form_section_id,
            "long_form_section_id": self.long_form_section_id,
            "short_form_section_span": _span(self.short_form_section_span),
            "long_form_section_span": _span(self.long_form_section_span),
            "resolver": {
                "key": self.resolver.key,
                "version": self.resolver.implementation_version,
            },
            "mapping_issues": list(self.mapping_issues),
        }


@dataclass(frozen=True, slots=True)
class ArticlePredictionRecord:
    """One segment's resolver output and mapped downstream entities."""

    source: ArticleDocument
    predictions: PredictionRecord
    entities: tuple[ArticleEntity, ...]

    def __post_init__(self) -> None:
        if self.predictions.document_id != self.source.document.document_id:
            raise ValueError("prediction record does not match source document")
        if not isinstance(self.entities, tuple) or any(
            not isinstance(entity, ArticleEntity) for entity in self.entities
        ):
            raise TypeError("entities must be a tuple of ArticleEntity values")


@dataclass(frozen=True, slots=True)
class ArticleResolutionResult:
    """Complete local-article resolution result for downstream consumers."""

    article_id: str
    pmid: str | None
    pmcid: str | None
    resolver: ResolverMetadata
    records: tuple[ArticlePredictionRecord, ...]

    @property
    def entities(self) -> tuple[ArticleEntity, ...]:
        """Return mapped entities in segment and prediction order."""

        return tuple(entity for record in self.records for entity in record.entities)

    @property
    def diagnostics(self) -> tuple[PredictionDiagnostic, ...]:
        """Return resolver diagnostics in execution order."""

        return tuple(
            diagnostic
            for record in self.records
            for diagnostic in record.predictions.diagnostics
        )


def _span(span: TextSpan | None) -> dict[str, int] | None:
    return None if span is None else {"start": span.start, "end": span.end}


__all__ = ["ArticleEntity", "ArticlePredictionRecord", "ArticleResolutionResult"]
