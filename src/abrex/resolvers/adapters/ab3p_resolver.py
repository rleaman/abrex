"""Resolver implementation coordinating Ab3P parsing with acquisition backends."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from abrex.domain import AbbreviationDefinition, Document
from abrex.resolvers.adapters.ab3p import (
    AB3P_ADAPTER_VERSION,
    Ab3PResolverConfig,
    parse_ab3p_output,
    reconstruct_predictions,
)

if TYPE_CHECKING:
    from abrex.infrastructure.ab3p import Ab3PRawResult


class Ab3PResolver:
    """Run Ab3P or replay its portable raw cache."""

    identity = "ab3p"
    version = AB3P_ADAPTER_VERSION

    def __init__(self, **params: object) -> None:
        self.config = Ab3PResolverConfig.model_validate(params)
        from abrex.infrastructure.ab3p import Ab3PCache

        self.cache = Ab3PCache(self.config.cache.path) if self.config.cache else None

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Return canonical predictions through the shared raw-output pipeline."""

        result = self._acquire(document)
        return reconstruct_predictions(document, parse_ab3p_output(result.stdout))

    def _acquire(self, document: Document) -> Ab3PRawResult:
        from abrex.infrastructure.ab3p import Ab3PCacheMiss, run_ab3p

        config = self.config
        if config.cache and config.cache.read:
            try:
                assert self.cache is not None
                return self.cache.read(document, config)
            except Ab3PCacheMiss:
                if config.backend == "cache_only":
                    raise
        if config.backend == "cache_only":
            raise Ab3PCacheMiss(
                f"No compatible Ab3P cache entry for {document.document_id!r}"
            )
        result = run_ab3p(document, config)
        if config.cache and config.cache.write:
            assert self.cache is not None
            self.cache.write(document, config, result)
        return result


__all__ = ["Ab3PResolver"]
