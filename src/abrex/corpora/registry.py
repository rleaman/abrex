"""Default and injectable registries for corpus plugins."""

from __future__ import annotations

from collections.abc import Callable

from abrex.corpora.base import CorpusAdapter, NormalizationStep
from abrex.registry import Registry

CORPUS_ADAPTERS = Registry[CorpusAdapter]("corpus_adapters")
NORMALIZERS = Registry[NormalizationStep]("normalizers")


def register_builtin_components() -> None:
    """Register the small built-in fixture components once per process."""

    from abrex.corpora.adapters.fixture import FixtureCorpusAdapter
    from abrex.corpora.adapters.historical import (
        BioCCorpusAdapter,
        SDUAcronymDisambiguationAdapter,
        SDUAcronymExtractionAdapter,
        SDUAcronymIdentificationAdapter,
    )
    from abrex.corpora.normalization import IdentityNormalization, TrimCapturedText

    if "fixture" not in CORPUS_ADAPTERS:
        CORPUS_ADAPTERS.register("fixture", FixtureCorpusAdapter)
    historical: dict[str, Callable[..., CorpusAdapter]] = {
        "schwartz_hearst": lambda **params: BioCCorpusAdapter(
            dataset_variant="schwartz_hearst", **params
        ),
        "ab3p_corpus": lambda **params: BioCCorpusAdapter(
            dataset_variant="ab3p_corpus", **params
        ),
        "bioadi": lambda **params: BioCCorpusAdapter(
            dataset_variant="bioadi", **params
        ),
        "medstract": lambda **params: BioCCorpusAdapter(
            dataset_variant="medstract", **params
        ),
        "sdu_aaai21_ai": lambda: SDUAcronymIdentificationAdapter(
            dataset_variant="sdu_aaai21_ai"
        ),
        "sdu_aaai21_ad": lambda: SDUAcronymDisambiguationAdapter(
            dataset_variant="sdu_aaai21_ad"
        ),
        "sdu_aaai22_ae": lambda: SDUAcronymExtractionAdapter(
            dataset_variant="sdu_aaai22_ae"
        ),
    }
    for key, factory in historical.items():
        if key not in CORPUS_ADAPTERS:
            CORPUS_ADAPTERS.register(key, factory)
    if "identity" not in NORMALIZERS:
        NORMALIZERS.register("identity", IdentityNormalization)
    if "trim_captured_text" not in NORMALIZERS:
        NORMALIZERS.register("trim_captured_text", TrimCapturedText)


register_builtin_components()

__all__ = ["CORPUS_ADAPTERS", "NORMALIZERS", "register_builtin_components"]
