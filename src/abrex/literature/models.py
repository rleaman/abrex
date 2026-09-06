"""Source-side article values and canonical-document segmentation values.

These models deliberately live outside :mod:`abrex.domain`.  They describe
the representation used by a local PubMed/PMC integration and carry enough
context to map canonical predictions back to the source article.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from abrex.domain import Document, TextSpan


class ArticleError(ValueError):
    """Base class for malformed local article data or mapping failures."""


class ArticleMappingError(ArticleError):
    """Raised when a canonical prediction cannot be mapped unambiguously."""


def _optional_text(value: str | None, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{field_name} must be a non-empty string or None")


@dataclass(frozen=True, slots=True)
class ArticleSection:
    """One locally available article section in source order.

    ``text`` is already the exact text supplied to the integration.  No
    Unicode normalization, whitespace repair, or title insertion is applied.
    """

    section_id: str
    text: str
    title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.section_id, str) or not self.section_id.strip():
            raise ValueError("section_id must be a non-empty string")
        if not isinstance(self.text, str):
            raise TypeError("section text must be a string")
        _optional_text(self.title, "section title")


@dataclass(frozen=True, slots=True)
class Article:
    """A local PubMed/PMC article representation.

    ``article_id`` is the caller's stable identifier.  If it is omitted, a
    PMCID is preferred, followed by a PMID.  The derived identifier is
    deterministic and the original identifiers remain available in
    provenance.
    """

    article_id: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    sections: tuple[ArticleSection, ...] = ()
    title: str | None = None

    def __post_init__(self) -> None:
        _optional_text(self.article_id, "article_id")
        _optional_text(self.pmid, "pmid")
        _optional_text(self.pmcid, "pmcid")
        _optional_text(self.title, "title")
        if not self.article_id and not self.pmid and not self.pmcid:
            raise ValueError("article requires article_id, pmid, or pmcid")
        raw_sections: object = self.sections
        if not isinstance(raw_sections, Sequence) or isinstance(
            raw_sections, str | bytes
        ):
            raise TypeError("sections must be a sequence of ArticleSection values")
        sections = tuple(raw_sections)
        if not sections:
            raise ValueError("article requires at least one section")
        if any(not isinstance(section, ArticleSection) for section in sections):
            raise TypeError("sections must contain ArticleSection values")
        section_ids = [section.section_id for section in sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("article section IDs must be unique")
        object.__setattr__(self, "sections", sections)
        if self.article_id is None:
            derived = self.pmcid or self.pmid
            assert derived is not None
            object.__setattr__(self, "article_id", derived)

    @property
    def stable_id(self) -> str:
        """Return the stable source identifier used in canonical document IDs."""

        assert self.article_id is not None
        return self.article_id


@dataclass(frozen=True, slots=True)
class ArticleDocumentProvenance:
    """Article and segmentation context for one canonical document."""

    article_id: str
    pmid: str | None
    pmcid: str | None
    title: str | None
    segmentation_policy: str
    section_id: str | None
    section_title: str | None
    section_index: int | None
    section_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.article_id.strip():
            raise ValueError("article provenance article_id must not be empty")
        if not self.segmentation_policy.strip():
            raise ValueError("segmentation_policy must not be empty")
        _optional_text(self.pmid, "pmid")
        _optional_text(self.pmcid, "pmcid")
        _optional_text(self.title, "title")
        _optional_text(self.section_id, "section_id")
        _optional_text(self.section_title, "section_title")
        if not isinstance(self.section_ids, tuple) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.section_ids
        ):
            raise TypeError("section_ids must be a tuple of non-empty strings")
        if self.section_index is not None and (
            isinstance(self.section_index, bool)
            or not isinstance(self.section_index, int)
            or self.section_index < 0
        ):
            raise ValueError("section_index must be a non-negative integer or None")


@dataclass(frozen=True, slots=True)
class ArticleSectionLocation:
    """Location of a source section in one canonical document."""

    section_id: str
    canonical_span: TextSpan

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("section location section_id must not be empty")


@dataclass(frozen=True, slots=True)
class ArticleDocument:
    """A canonical document together with article mapping context."""

    document: Document
    provenance: ArticleDocumentProvenance
    section_locations: tuple[ArticleSectionLocation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.document, Document):
            raise TypeError("document must be a Document")
        if not isinstance(self.provenance, ArticleDocumentProvenance):
            raise TypeError("provenance must be ArticleDocumentProvenance")
        if not isinstance(self.section_locations, tuple) or any(
            not isinstance(item, ArticleSectionLocation)
            for item in self.section_locations
        ):
            raise TypeError(
                "section_locations must be a tuple of ArticleSectionLocation values"
            )
        for location in self.section_locations:
            location.canonical_span.validate_against(self.document.text)

    def location_for_span(self, span: TextSpan | None) -> tuple[str, TextSpan] | None:
        """Map a fully contained canonical span to a source section.

        A span in an article separator, or one crossing a section boundary,
        returns ``None`` rather than being silently assigned to a section.
        """

        if span is None:
            return None
        self.document.validate_span(span)
        matches = [
            location
            for location in self.section_locations
            if location.canonical_span.start <= span.start
            and span.end <= location.canonical_span.end
        ]
        if len(matches) != 1:
            return None
        location = matches[0]
        local = TextSpan(
            span.start - location.canonical_span.start,
            span.end - location.canonical_span.start,
        )
        return location.section_id, local


__all__ = [
    "Article",
    "ArticleDocument",
    "ArticleDocumentProvenance",
    "ArticleError",
    "ArticleMappingError",
    "ArticleSection",
    "ArticleSectionLocation",
]
