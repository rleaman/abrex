"""Explicit article-to-document segmentation policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import Document, TextSpan
from abrex.literature.models import (
    Article,
    ArticleDocument,
    ArticleDocumentProvenance,
    ArticleSectionLocation,
)


class ArticleSegmenter(Protocol):
    """Convert one source article into canonical documents."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def segment(self, article: Article) -> tuple[ArticleDocument, ...]: ...


class SectionSegmenterConfig(BaseModel):
    """Configuration for one-document-per-source-section segmentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    include_empty_sections: bool = True


class ArticleSegmenterConfig(BaseModel):
    """Configuration for one canonical document containing all sections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    separator: str = Field(default="\n\n", min_length=1)


@dataclass(frozen=True, slots=True)
class SectionDocumentSegmenter:
    """Expose every source section as an independent canonical document."""

    include_empty_sections: bool = True
    identity: str = "sections"
    version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.include_empty_sections, bool):
            raise TypeError("include_empty_sections must be a boolean")

    def segment(self, article: Article) -> tuple[ArticleDocument, ...]:
        """Return section documents without changing section text or offsets."""

        documents: list[ArticleDocument] = []
        for index, section in enumerate(article.sections):
            if not self.include_empty_sections and not section.text:
                continue
            document_id = f"{article.stable_id}/section/{section.section_id}"
            document = Document(document_id, section.text)
            provenance = ArticleDocumentProvenance(
                article_id=article.stable_id,
                pmid=article.pmid,
                pmcid=article.pmcid,
                title=article.title,
                segmentation_policy=self.identity,
                section_id=section.section_id,
                section_title=section.title,
                section_index=index,
                section_ids=(section.section_id,),
            )
            documents.append(
                ArticleDocument(
                    document,
                    provenance,
                    (
                        ArticleSectionLocation(
                            section.section_id, TextSpan(0, len(section.text))
                        ),
                    ),
                )
            )
        return tuple(documents)


@dataclass(frozen=True, slots=True)
class WholeArticleSegmenter:
    """Join sections using an explicit separator into one canonical document."""

    separator: str = "\n\n"
    identity: str = "article"
    version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.separator, str) or not self.separator:
            raise ValueError("article segmentation separator must not be empty")

    def segment(self, article: Article) -> tuple[ArticleDocument, ...]:
        """Build one document and retain each section's canonical interval."""

        parts: list[str] = []
        locations: list[ArticleSectionLocation] = []
        offset = 0
        for index, section in enumerate(article.sections):
            if index:
                parts.append(self.separator)
                offset += len(self.separator)
            start = offset
            parts.append(section.text)
            offset += len(section.text)
            locations.append(
                ArticleSectionLocation(section.section_id, TextSpan(start, offset))
            )
        text = "".join(parts)
        document = Document(f"{article.stable_id}/article", text)
        provenance = ArticleDocumentProvenance(
            article_id=article.stable_id,
            pmid=article.pmid,
            pmcid=article.pmcid,
            title=article.title,
            segmentation_policy=self.identity,
            section_id=None,
            section_title=None,
            section_index=None,
            section_ids=tuple(section.section_id for section in article.sections),
        )
        return (ArticleDocument(document, provenance, tuple(locations)),)


__all__ = [
    "ArticleSegmenter",
    "ArticleSegmenterConfig",
    "SectionDocumentSegmenter",
    "SectionSegmenterConfig",
    "WholeArticleSegmenter",
]
