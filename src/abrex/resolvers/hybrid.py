"""Transparent, evidence-preserving composition of abbreviation resolvers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.config import ComponentSpec, create_component
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
)
from abrex.resolvers.base import Resolver
from abrex.resolvers.registry import RESOLVERS

HybridStrategy = Literal["exact_union", "priority_cascade"]
ConflictPolicy = Literal["retain_all", "abstain", "priority"]
ChildFailurePolicy = Literal["raise", "abstain"]
HYBRID_VERSION = "transparent-hybrid-v1"


class HybridResolverConfig(BaseModel):
    """Typed configuration for a transparent resolver fusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    children: tuple[ComponentSpec, ...] = Field(min_length=1)
    strategy: HybridStrategy = "exact_union"
    conflict_policy: ConflictPolicy = "retain_all"
    child_failure_policy: ChildFailurePolicy = "raise"
    priority: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FusionDecision:
    """One accepted or rejected child proposal and its named rule."""

    child: str
    accepted: bool
    rule: str
    reason: str
    prediction_key: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ChildResolution:
    """Raw output from one child, retained for later inspection."""

    child: str
    predictions: tuple[AbbreviationDefinition, ...]


@dataclass(frozen=True, slots=True)
class HybridResolution:
    """Fusion result with raw child outputs and every decision."""

    document_id: str
    children: tuple[ChildResolution, ...]
    predictions: tuple[AbbreviationDefinition, ...]
    decisions: tuple[FusionDecision, ...]


class HybridResolverError(ValueError):
    """Raised when a configured hybrid child cannot produce a result."""


class TransparentHybridResolver:
    """Compose child resolvers without averaging incomparable confidence scores."""

    identity = "transparent_hybrid"
    version = HYBRID_VERSION

    def __init__(
        self,
        *,
        children: Sequence[Resolver],
        child_names: Sequence[str] | None = None,
        strategy: HybridStrategy = "exact_union",
        conflict_policy: ConflictPolicy = "retain_all",
        child_failure_policy: ChildFailurePolicy = "raise",
        priority: Sequence[str] = (),
        child_specs: Sequence[ComponentSpec] = (),
    ) -> None:
        if not children:
            raise ValueError("Hybrid resolver requires at least one child")
        names = tuple(child_names or (_child_identity(child) for child in children))
        if len(names) != len(children) or len(set(names)) != len(names):
            raise ValueError("Hybrid child names must be unique and aligned")
        if priority and set(priority) != set(names):
            raise ValueError("Hybrid priority must name every child exactly once")
        self.children = tuple(children)
        self.child_names = names
        self.strategy = strategy
        self.conflict_policy = conflict_policy
        self.child_failure_policy = child_failure_policy
        self.priority = tuple(priority) or names
        self.child_specs = tuple(child_specs)

    @property
    def cache_identity(self) -> dict[str, object]:
        """Return child identities and fusion policy for cache addressing."""

        return {
            "resolver": self.identity,
            "version": self.version,
            "strategy": self.strategy,
            "conflict_policy": self.conflict_policy,
            "child_failure_policy": self.child_failure_policy,
            "priority": self.priority,
            "children": [
                {
                    "name": name,
                    "identity": _child_cache_identity(child),
                    "config": self.child_specs[index].model_dump(mode="json")
                    if index < len(self.child_specs)
                    else None,
                }
                for index, (name, child) in enumerate(
                    zip(self.child_names, self.children, strict=True)
                )
            ],
        }

    def resolve_with_evidence(self, document: Document) -> HybridResolution:
        """Run all children and return raw outputs plus fusion decisions."""

        raw: list[ChildResolution] = []
        for name, child in zip(self.child_names, self.children, strict=True):
            try:
                predictions = tuple(child.resolve(document))
            except Exception as error:
                if self.child_failure_policy == "raise":
                    raise HybridResolverError(
                        f"Hybrid child {name!r} failed for document "
                        f"{document.document_id!r}: {error}"
                    ) from error
                raw.append(ChildResolution(name, ()))
                continue
            for prediction in predictions:
                prediction.validate_against(document)
            raw.append(ChildResolution(name, predictions))
        return self._fuse(document, tuple(raw))

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        """Return only accepted predictions under the named fusion policy."""

        return self.resolve_with_evidence(document).predictions

    def _fuse(
        self, document: Document, children: tuple[ChildResolution, ...]
    ) -> HybridResolution:
        ordered = _ordered_children(children, self.priority, self.strategy)
        accepted: list[AbbreviationDefinition] = []
        decisions: list[FusionDecision] = []
        exact: dict[tuple[object, ...], int] = {}
        conflicts: set[tuple[object, ...]] = set()
        for child in ordered:
            for prediction in child.predictions:
                key = _prediction_key(prediction)
                if key in exact:
                    index = exact[key]
                    accepted[index] = _merge_contributors(
                        accepted[index], prediction, child.child
                    )
                    decisions.append(
                        FusionDecision(
                            child.child,
                            True,
                            "exact_duplicate_merge",
                            "merged with an existing exact pair",
                            key,
                        )
                    )
                    continue
                conflict_keys = _conflict_keys(prediction)
                if any(conflict_key in conflicts for conflict_key in conflict_keys):
                    if self.conflict_policy == "abstain":
                        decisions.append(
                            FusionDecision(
                                child.child,
                                False,
                                "conflict_abstention",
                                "conflicting form retained as abstention",
                                key,
                            )
                        )
                        continue
                    if self.conflict_policy == "priority":
                        decisions.append(
                            FusionDecision(
                                child.child,
                                False,
                                "priority_conflict",
                                "higher-priority child already supplied a "
                                "conflicting form",
                                key,
                            )
                        )
                        continue
                exact[key] = len(accepted)
                conflicts.update(conflict_keys)
                accepted.append(_as_hybrid_prediction(prediction, self, child.child))
                decisions.append(
                    FusionDecision(
                        child.child,
                        True,
                        "accepted",
                        "first occurrence under fusion policy",
                        key,
                    )
                )
        return HybridResolution(
            document.document_id, children, tuple(accepted), tuple(decisions)
        )


def create_hybrid_resolver(
    *,
    children: Sequence[ComponentSpec | dict[str, Any]],
    strategy: HybridStrategy = "exact_union",
    conflict_policy: ConflictPolicy = "retain_all",
    child_failure_policy: ChildFailurePolicy = "raise",
    priority: Sequence[str] = (),
) -> TransparentHybridResolver:
    """Construct a recursively configured hybrid through the resolver registry."""

    config = HybridResolverConfig(
        children=tuple(ComponentSpec.model_validate(child) for child in children),
        strategy=strategy,
        conflict_policy=conflict_policy,
        child_failure_policy=child_failure_policy,
        priority=tuple(priority),
    )
    built = tuple(_create_child(spec, ()) for spec in config.children)
    names = tuple(_child_identity(child) for child in built)
    return TransparentHybridResolver(
        children=built,
        child_names=names,
        strategy=config.strategy,
        conflict_policy=config.conflict_policy,
        child_failure_policy=config.child_failure_policy,
        priority=config.priority,
        child_specs=config.children,
    )


def _create_child(spec: ComponentSpec, stack: tuple[str, ...]) -> Resolver:
    if spec.type == "transparent_hybrid":
        if spec.type in stack:
            raise HybridResolverError(
                "Cyclic hybrid configuration: " + " -> ".join((*stack, spec.type))
            )
        params = HybridResolverConfig.model_validate(spec.params)
        children = tuple(
            _create_child(child, (*stack, spec.type)) for child in params.children
        )
        return TransparentHybridResolver(
            children=children,
            child_names=tuple(_child_identity(child) for child in children),
            strategy=params.strategy,
            conflict_policy=params.conflict_policy,
            child_failure_policy=params.child_failure_policy,
            priority=params.priority,
            child_specs=params.children,
        )
    return create_component(spec, RESOLVERS)


def _ordered_children(
    children: Sequence[ChildResolution],
    priority: Sequence[str],
    strategy: HybridStrategy,
) -> tuple[ChildResolution, ...]:
    if strategy == "exact_union":
        return tuple(children)
    by_name = {child.child: child for child in children}
    return tuple(by_name[name] for name in priority)


def _prediction_key(prediction: AbbreviationDefinition) -> tuple[object, ...]:
    return (
        prediction.document_id,
        _span_tuple(prediction.short_form),
        _span_tuple(prediction.long_form),
    )


def _conflict_keys(
    prediction: AbbreviationDefinition,
) -> tuple[tuple[object, ...], ...]:
    keys: list[tuple[object, ...]] = []
    if prediction.short_form is not None:
        keys.append(
            (prediction.document_id, "short", _span_tuple(prediction.short_form))
        )
    if prediction.long_form is not None:
        keys.append((prediction.document_id, "long", _span_tuple(prediction.long_form)))
    return tuple(keys)


def _span_tuple(span: object) -> tuple[int, int] | None:
    if span is None:
        return None
    return span.start, span.end  # type: ignore[attr-defined]


def _merge_contributors(
    original: AbbreviationDefinition, duplicate: AbbreviationDefinition, child: str
) -> AbbreviationDefinition:
    first = original.provenance or AnnotationProvenance()
    second = duplicate.provenance or AnnotationProvenance()
    provenance = AnnotationProvenance(
        source_corpus=first.source_corpus,
        source_record_id=first.source_record_id,
        source_annotation_id=first.source_annotation_id,
        original_short_form=first.original_short_form,
        original_long_form=first.original_long_form,
        adapter_identity=first.adapter_identity,
        adapter_version=first.adapter_version,
        transformation_notes=(
            *first.transformation_notes,
            f"contributor:{child}",
            _provenance_json(second),
        ),
    )
    return AbbreviationDefinition(
        original.document_id,
        original.short_form,
        original.long_form,
        original.short_form_text,
        original.long_form_text,
        provenance,
        original.prediction,
    )


def _as_hybrid_prediction(
    prediction: AbbreviationDefinition, resolver: TransparentHybridResolver, child: str
) -> AbbreviationDefinition:
    provenance = prediction.provenance or AnnotationProvenance()
    metadata = prediction.prediction or PredictionMetadata()
    merged_provenance = AnnotationProvenance(
        source_corpus=provenance.source_corpus,
        source_record_id=provenance.source_record_id,
        source_annotation_id=provenance.source_annotation_id,
        original_short_form=provenance.original_short_form,
        original_long_form=provenance.original_long_form,
        adapter_identity=resolver.identity,
        adapter_version=resolver.version,
        transformation_notes=(*provenance.transformation_notes, f"contributor:{child}"),
    )
    return AbbreviationDefinition(
        prediction.document_id,
        prediction.short_form,
        prediction.long_form,
        prediction.short_form_text,
        prediction.long_form_text,
        merged_provenance,
        PredictionMetadata(
            confidence=metadata.confidence,
            score=metadata.score,
            component=resolver.identity,
            component_version=resolver.version,
            model_artifact_fingerprint=_fingerprint(resolver.cache_identity),
            feature_config_fingerprint=_fingerprint(resolver.cache_identity),
        ),
    )


def _child_identity(child: Resolver) -> str:
    identity = getattr(child, "identity", None)
    if not isinstance(identity, str) or not identity:
        raise ValueError("Hybrid children must expose a non-empty identity")
    return identity


def _child_cache_identity(child: Resolver) -> object:
    identity = getattr(child, "cache_identity", None)
    if callable(identity):
        identity = identity()
    return identity or {
        "identity": _child_identity(child),
        "version": getattr(child, "version", "unknown"),
    }


def _provenance_json(provenance: AnnotationProvenance) -> str:
    return "contributor_provenance:" + json.dumps(
        {
            "adapter_identity": provenance.adapter_identity,
            "adapter_version": provenance.adapter_version,
            "source_corpus": provenance.source_corpus,
            "source_record_id": provenance.source_record_id,
            "source_annotation_id": provenance.source_annotation_id,
            "transformation_notes": provenance.transformation_notes,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


__all__ = [
    "ChildResolution",
    "FusionDecision",
    "HYBRID_VERSION",
    "HybridResolution",
    "HybridResolverConfig",
    "HybridResolverError",
    "TransparentHybridResolver",
    "create_hybrid_resolver",
]
