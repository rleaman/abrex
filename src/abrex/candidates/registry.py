"""Registry for candidate generators."""

from __future__ import annotations

from abrex.candidates.base import CandidateGenerator
from abrex.registry import Registry

GENERATORS = Registry[CandidateGenerator]("candidate_generators")


def register_builtin_components() -> None:
    """Register built-in generators exactly once."""

    from abrex.candidates.generators import (
        LexicalResourceCandidateConfig,
        LexicalResourceCandidateGenerator,
        NestedParentheticalCandidateConfig,
        NestedParentheticalCandidateGenerator,
        ParentheticalCandidateConfig,
        ParentheticalCandidateGenerator,
        ReverseOrderCandidateConfig,
        ReverseOrderCandidateGenerator,
        StructuredRelationCandidateConfig,
        StructuredRelationCandidateGenerator,
    )

    if "parenthetical" not in GENERATORS:
        GENERATORS.register(
            "parenthetical",
            ParentheticalCandidateGenerator,
            config_model=ParentheticalCandidateConfig,
        )
    for key, factory, config in (
        (
            "lexical_resource",
            LexicalResourceCandidateGenerator,
            LexicalResourceCandidateConfig,
        ),
        ("reverse_order", ReverseOrderCandidateGenerator, ReverseOrderCandidateConfig),
        (
            "nested_parenthetical",
            NestedParentheticalCandidateGenerator,
            NestedParentheticalCandidateConfig,
        ),
        (
            "structured_relations",
            StructuredRelationCandidateGenerator,
            StructuredRelationCandidateConfig,
        ),
    ):
        if key not in GENERATORS:
            GENERATORS.register(key, factory, config_model=config)


register_builtin_components()

__all__ = ["GENERATORS", "register_builtin_components"]
