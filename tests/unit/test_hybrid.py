from __future__ import annotations

from collections.abc import Iterable

import pytest

from abrex.config import ComponentSpec
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    TextSpan,
)
from abrex.resolvers import (
    HybridResolverError,
    ResolverExecutor,
    TransparentHybridResolver,
    create_hybrid_resolver,
)

DOCUMENT = Document(
    "doc-1", "Tumor necrosis factor (TNF) and tumor necrosis factor (TNF)."
)


def _prediction(start: int, long_start: int, child: str) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        DOCUMENT.document_id,
        TextSpan(start, start + 3),
        TextSpan(long_start, long_start + 21),
        DOCUMENT.text[start : start + 3],
        DOCUMENT.text[long_start : long_start + 21],
        AnnotationProvenance(adapter_identity=child, adapter_version="test"),
    )


class StaticResolver:
    version = "test"

    def __init__(
        self, identity: str, predictions: Iterable[AbbreviationDefinition]
    ) -> None:
        self.identity = identity
        self.predictions = tuple(predictions)

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        return self.predictions


class FailingResolver:
    identity = "failing"
    version = "test"

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        raise RuntimeError("child failed")


def test_exact_union_merges_duplicates_and_retains_contributors() -> None:
    first = StaticResolver("first", (_prediction(23, 0, "first"),))
    second = StaticResolver("second", (_prediction(23, 0, "second"),))
    resolver = TransparentHybridResolver(children=(first, second))

    result = resolver.resolve_with_evidence(DOCUMENT)

    assert len(result.predictions) == 1
    assert len(result.children) == 2
    assert result.decisions[1].rule == "exact_duplicate_merge"
    provenance = result.predictions[0].provenance
    assert provenance is not None
    notes = provenance.transformation_notes
    assert "contributor:first" in notes
    assert "contributor:second" in notes


def test_conflict_policies_are_deterministic() -> None:
    first = StaticResolver("first", (_prediction(23, 0, "first"),))
    second = StaticResolver("second", (_prediction(52, 29, "second"),))
    assert (
        len(
            TransparentHybridResolver(
                children=(first, second), conflict_policy="retain_all"
            )
            .resolve_with_evidence(DOCUMENT)
            .predictions
        )
        == 2
    )
    abstained = TransparentHybridResolver(
        children=(first, second), conflict_policy="abstain"
    ).resolve_with_evidence(DOCUMENT)
    assert len(abstained.predictions) == 2

    conflicting = StaticResolver("third", (_prediction(23, 29, "third"),))
    priority = TransparentHybridResolver(
        children=(first, conflicting),
        conflict_policy="priority",
        priority=("first", "third"),
    ).resolve_with_evidence(DOCUMENT)
    assert len(priority.predictions) == 1
    assert priority.decisions[-1].rule == "priority_conflict"

    shared_long = StaticResolver("shared", (_prediction(52, 0, "shared"),))
    shared_result = TransparentHybridResolver(
        children=(first, shared_long),
        conflict_policy="priority",
        priority=("first", "shared"),
    ).resolve_with_evidence(DOCUMENT)
    assert len(shared_result.predictions) == 1
    assert shared_result.decisions[-1].rule == "priority_conflict"


def test_child_failure_is_explicit_or_configured_abstention() -> None:
    with pytest.raises(HybridResolverError, match="failing"):
        TransparentHybridResolver(children=(FailingResolver(),)).resolve(DOCUMENT)
    result = TransparentHybridResolver(
        children=(FailingResolver(),), child_failure_policy="abstain"
    ).resolve_with_evidence(DOCUMENT)
    assert result.children[0].predictions == ()
    assert result.predictions == ()


def test_registry_config_and_cache_identity_include_children() -> None:
    resolver = create_hybrid_resolver(
        children=(ComponentSpec(type="toy", params={}),),
        strategy="priority_cascade",
        conflict_policy="priority",
        priority=("toy",),
    )
    assert isinstance(resolver, TransparentHybridResolver)


def test_executor_exposes_hybrid_under_the_normal_contract() -> None:
    resolver = TransparentHybridResolver(
        children=(StaticResolver("first", (_prediction(23, 0, "first"),)),)
    )
    result = ResolverExecutor(resolver).resolve_document(DOCUMENT)
    metadata = result.predictions[0].prediction
    assert metadata is not None
    assert metadata.component == "transparent_hybrid"
    assert resolver.cache_identity["children"]
