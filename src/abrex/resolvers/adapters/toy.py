"""A deterministic, deliberately small resolver for contract and smoke tests."""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import AbbreviationDefinition, Document, PredictionMetadata, TextSpan


class ToyResolverConfig(BaseModel):
    """Parameters for the fixture resolver's optional prediction metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence: float | None = Field(default=None, ge=0, le=1)
    score: float | None = Field(default=None, allow_inf_nan=False)


class ToyResolver:
    """Extract ``long form (SHORT)`` constructions without changing text.

    This is a fixture implementation, not a scientific baseline. It exists
    to prove YAML composition, canonical offsets, metadata, and artifact
    determinism before a production resolver is added.
    """

    identity = "toy"
    version = "1"
    _pattern = re.compile(
        r"(?P<long>[A-Za-z][A-Za-z0-9 -]*?[A-Za-z0-9])\s*"
        r"\((?P<short>[A-Za-z][A-Za-z0-9-]*)\)"
    )

    def __init__(
        self, confidence: float | None = None, score: float | None = None
    ) -> None:
        self.config = ToyResolverConfig(confidence=confidence, score=score)

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Return pattern matches in left-to-right source order."""

        for match in self._pattern.finditer(document.text):
            long_start, long_end = match.span("long")
            short_start, short_end = match.span("short")
            yield AbbreviationDefinition(
                document_id=document.document_id,
                short_form=TextSpan(short_start, short_end),
                long_form=TextSpan(long_start, long_end),
                short_form_text=document.text[short_start:short_end],
                long_form_text=document.text[long_start:long_end],
                prediction=PredictionMetadata(
                    confidence=self.config.confidence,
                    score=self.config.score,
                ),
            )


__all__ = ["ToyResolver", "ToyResolverConfig"]
