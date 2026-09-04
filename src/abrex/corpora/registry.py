"""Default and injectable registries for corpus plugins."""

from __future__ import annotations

from abrex.corpora.base import CorpusAdapter, NormalizationStep
from abrex.registry import Registry

CORPUS_ADAPTERS = Registry[CorpusAdapter]("corpus_adapters")
NORMALIZERS = Registry[NormalizationStep]("normalizers")


def register_builtin_components() -> None:
    """Register the small built-in fixture components once per process."""

    from abrex.corpora.adapters.fixture import FixtureCorpusAdapter
    from abrex.corpora.normalization import IdentityNormalization, TrimCapturedText

    if "fixture" not in CORPUS_ADAPTERS:
        CORPUS_ADAPTERS.register("fixture", FixtureCorpusAdapter)
    if "identity" not in NORMALIZERS:
        NORMALIZERS.register("identity", IdentityNormalization)
    if "trim_captured_text" not in NORMALIZERS:
        NORMALIZERS.register("trim_captured_text", TrimCapturedText)


register_builtin_components()

__all__ = ["CORPUS_ADAPTERS", "NORMALIZERS", "register_builtin_components"]
