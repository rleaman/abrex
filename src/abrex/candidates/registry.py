"""Registry for candidate generators."""

from __future__ import annotations

from abrex.candidates.base import CandidateGenerator
from abrex.registry import Registry

GENERATORS = Registry[CandidateGenerator]("candidate_generators")


def register_builtin_components() -> None:
    """Register built-in generators exactly once."""

    from abrex.candidates.generators import (
        ParentheticalCandidateConfig,
        ParentheticalCandidateGenerator,
    )

    if "parenthetical" not in GENERATORS:
        GENERATORS.register(
            "parenthetical",
            ParentheticalCandidateGenerator,
            config_model=ParentheticalCandidateConfig,
        )


register_builtin_components()

__all__ = ["GENERATORS", "register_builtin_components"]
