"""Injectable registry for article segmentation strategies."""

from __future__ import annotations

from abrex.literature.segmenters import ArticleSegmenter
from abrex.registry import Registry

SEGMENTERS = Registry[ArticleSegmenter]("article-segmenters")


def register_builtin_components() -> None:
    """Register the explicit built-in article segmentation policies."""

    from abrex.literature.segmenters import (
        ArticleSegmenterConfig,
        SectionDocumentSegmenter,
        SectionSegmenterConfig,
        WholeArticleSegmenter,
    )

    if "sections" not in SEGMENTERS:
        SEGMENTERS.register(
            "sections", SectionDocumentSegmenter, config_model=SectionSegmenterConfig
        )
    if "article" not in SEGMENTERS:
        SEGMENTERS.register(
            "article", WholeArticleSegmenter, config_model=ArticleSegmenterConfig
        )


register_builtin_components()

__all__ = ["SEGMENTERS", "register_builtin_components"]
