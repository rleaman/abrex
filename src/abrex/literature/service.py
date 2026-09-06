"""Application service for resolving local PubMed/PMC articles."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from abrex.config import ComponentSpec, ResolvedConfig, create_component
from abrex.literature.mapping import (
    ArticleEntity,
    ArticlePredictionRecord,
    ArticleResolutionResult,
)
from abrex.literature.models import Article
from abrex.literature.registry import SEGMENTERS
from abrex.literature.segmenters import ArticleSegmenter
from abrex.registry import Registry
from abrex.resolvers import (
    Resolver,
    ResolverExecutor,
    create_resolver_executor,
    resolver_config_from_resolved,
)


class LiteratureConfig(BaseModel):
    """Typed composition inputs for local article resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segmentation: ComponentSpec
    validation_mode: Literal["strict", "permissive"] = "strict"
    error_policy: Literal["raise", "collect"] = "raise"


def literature_config_from_resolved(config: ResolvedConfig) -> LiteratureConfig:
    """Validate the resolved ``literature`` article-integration section.

    The ``article`` top-level name is accepted as a documented compatibility
    alias for local callers; new YAML should use ``literature``.
    """

    raw = config.model_extra or {}
    section = raw.get("literature", raw.get("article"))
    if not isinstance(section, dict):
        raise ValueError(
            "Resolved configuration requires a literature section with segmentation"
        )
    segmentation = section.get("segmentation")
    if segmentation is None:
        raise ValueError("literature.segmentation is required")
    try:
        return LiteratureConfig.model_validate(
            {
                "segmentation": segmentation,
                "validation_mode": section.get("validation_mode", "strict"),
                "error_policy": section.get("error_policy", "raise"),
            }
        )
    except ValueError as error:
        raise ValueError(f"Invalid literature configuration: {error}") from error


class ArticleResolutionService:
    """Compose segmentation and the existing resolver execution contract."""

    def __init__(self, executor: ResolverExecutor, segmenter: ArticleSegmenter) -> None:
        self.executor = executor
        self.segmenter = segmenter

    def resolve(self, article: Article) -> ArticleResolutionResult:
        """Resolve one local article and map every prediction downstream."""

        if not isinstance(article, Article):
            raise TypeError("article must be an Article")
        sources = self.segmenter.segment(article)
        resolver_result = self.executor.resolve_documents(
            tuple(source.document for source in sources),
            error_policy=self.executor.error_policy,
        )
        records: list[ArticlePredictionRecord] = []
        for source, prediction_record in zip(
            sources, resolver_result.records, strict=True
        ):
            entities = tuple(
                ArticleEntity.from_prediction(
                    source, prediction, self.executor.metadata
                )
                for prediction in prediction_record.predictions
            )
            records.append(ArticlePredictionRecord(source, prediction_record, entities))
        return ArticleResolutionResult(
            article_id=article.stable_id,
            pmid=article.pmid,
            pmcid=article.pmcid,
            resolver=self.executor.metadata,
            records=tuple(records),
        )


def create_article_resolution_service(
    config: ResolvedConfig,
    *,
    resolver_registry: Registry[Resolver] | None = None,
    segmenter_registry: Registry[ArticleSegmenter] = SEGMENTERS,
) -> ArticleResolutionService:
    """Create a local-article service from resolved YAML configuration."""

    literature_config = literature_config_from_resolved(config)
    resolver_config = resolver_config_from_resolved(config)
    if resolver_registry is None:
        executor = create_resolver_executor(
            resolver_config,
            validation_mode=literature_config.validation_mode,
            error_policy=literature_config.error_policy,
        )
    else:
        executor = create_resolver_executor(
            resolver_config,
            registry=resolver_registry,
            validation_mode=literature_config.validation_mode,
            error_policy=literature_config.error_policy,
        )
    segmenter = create_component(literature_config.segmentation, segmenter_registry)
    return ArticleResolutionService(executor, segmenter)


__all__ = [
    "ArticleResolutionService",
    "LiteratureConfig",
    "create_article_resolution_service",
    "literature_config_from_resolved",
]
