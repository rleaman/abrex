"""Offline PubMed/PMC article integration at the resolver boundary."""

from abrex.literature.io import (
    ARTICLE_RESOLUTION_SCHEMA_VERSION,
    ARTICLE_SCHEMA_VERSION,
    ArticleSerializationError,
    article_from_dict,
    article_resolution_to_dict,
    article_to_dict,
    read_article_json,
    serialize_article_resolution,
    write_article_resolution,
)
from abrex.literature.mapping import (
    ArticleEntity,
    ArticlePredictionRecord,
    ArticleResolutionResult,
)
from abrex.literature.models import (
    Article,
    ArticleDocument,
    ArticleDocumentProvenance,
    ArticleError,
    ArticleMappingError,
    ArticleSection,
    ArticleSectionLocation,
)
from abrex.literature.registry import SEGMENTERS, register_builtin_components
from abrex.literature.segmenters import (
    ArticleSegmenter,
    ArticleSegmenterConfig,
    SectionDocumentSegmenter,
    SectionSegmenterConfig,
    WholeArticleSegmenter,
)
from abrex.literature.service import (
    ArticleResolutionService,
    LiteratureConfig,
    create_article_resolution_service,
    literature_config_from_resolved,
)

__all__ = [
    "ARTICLE_RESOLUTION_SCHEMA_VERSION",
    "ARTICLE_SCHEMA_VERSION",
    "Article",
    "ArticleDocument",
    "ArticleDocumentProvenance",
    "ArticleEntity",
    "ArticleError",
    "ArticleMappingError",
    "ArticlePredictionRecord",
    "ArticleResolutionResult",
    "ArticleResolutionService",
    "ArticleSection",
    "ArticleSectionLocation",
    "ArticleSegmenter",
    "ArticleSegmenterConfig",
    "ArticleSerializationError",
    "LiteratureConfig",
    "SEGMENTERS",
    "SectionDocumentSegmenter",
    "SectionSegmenterConfig",
    "WholeArticleSegmenter",
    "article_from_dict",
    "article_resolution_to_dict",
    "article_to_dict",
    "create_article_resolution_service",
    "literature_config_from_resolved",
    "read_article_json",
    "register_builtin_components",
    "serialize_article_resolution",
    "write_article_resolution",
]
