"""Document-local abbreviation mention propagation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import AbbreviationDefinition, TextSpan
from abrex.literature.models import ArticleDocument


class MentionLinkConfig(BaseModel):
    """Explicit scope, ordering, and surface matching policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["article", "section"] = "article"
    ordering: Literal["nearest_preceding", "nearest_any"] = "nearest_preceding"
    conflict_policy: Literal["abstain", "nearest"] = "abstain"
    case_sensitive: bool = False
    allow_plural: bool = False
    context_characters: int = Field(default=80, ge=0)


MentionStatus = Literal["linked", "ambiguous", "abstain", "undefined"]


@dataclass(frozen=True, slots=True)
class MentionLink:
    """One mention outcome with optional chosen definition and diagnostics."""

    article_id: str
    document_id: str
    mention_span: TextSpan
    mention_text: str
    short_form: str
    status: MentionStatus
    definition: AbbreviationDefinition | None
    candidate_definition_indices: tuple[int, ...]
    scope: str
    evidence: tuple[str, ...]
    ambiguity_reason: str | None = None


def link_mentions(
    source: ArticleDocument,
    definitions: tuple[AbbreviationDefinition, ...],
    config: MentionLinkConfig | None = None,
) -> tuple[MentionLink, ...]:
    """Link repeated local surface mentions without inventing definitions."""

    policy = config or MentionLinkConfig()
    document = source.document
    indexed: dict[str, list[tuple[int, AbbreviationDefinition]]] = {}
    for index, definition in enumerate(definitions):
        if definition.short_form is None or definition.long_form is None:
            continue
        definition.validate_against(document)
        surface = document.text_for(definition.short_form)
        indexed.setdefault(_key(surface, policy.case_sensitive), []).append(
            (index, definition)
        )
    results: list[MentionLink] = []
    for _short_form, candidates in sorted(indexed.items()):
        surfaces = {
            document.text_for(item.short_form)
            for _, item in candidates
            if item.short_form is not None
        }
        for surface in sorted(surfaces):
            pattern = re.escape(surface) + (r"s?" if policy.allow_plural else "")
            for match in re.finditer(
                pattern,
                document.text,
                flags=0 if policy.case_sensitive else re.IGNORECASE,
            ):
                span = TextSpan(match.start(), match.end())
                eligible = [
                    (index, definition)
                    for index, definition in candidates
                    if _in_scope(source, definition.short_form, span, policy.scope)
                    and (
                        policy.ordering == "nearest_any"
                        or _definition_start(definition) <= span.start
                    )
                ]
                eligible.sort(
                    key=lambda item: _definition_start(item[1]),
                    reverse=True,
                )
                if not eligible:
                    status: MentionStatus = (
                        "undefined"
                        if policy.ordering == "nearest_preceding"
                        else "abstain"
                    )
                    results.append(
                        _link(
                            source,
                            span,
                            match.group(0),
                            surface,
                            status,
                            (),
                            policy,
                            None,
                            "no eligible local definition",
                        )
                    )
                    continue
                nearest_start = _definition_start(eligible[0][1])
                tied = [
                    item
                    for item in eligible
                    if _definition_start(item[1]) == nearest_start
                ]
                if len(tied) > 1 and policy.conflict_policy == "abstain":
                    results.append(
                        _link(
                            source,
                            span,
                            match.group(0),
                            surface,
                            "ambiguous",
                            tuple(item[0] for item in tied),
                            policy,
                            None,
                            "multiple definitions at the selected position",
                        )
                    )
                else:
                    chosen = tied[0]
                    results.append(
                        _link(
                            source,
                            span,
                            match.group(0),
                            surface,
                            "linked",
                            tuple(item[0] for item in tied),
                            policy,
                            chosen[1],
                            None,
                        )
                    )
    return tuple(results)


def _in_scope(
    source: ArticleDocument,
    definition_span: TextSpan | None,
    mention: TextSpan,
    scope: str,
) -> bool:
    if definition_span is None:
        return False
    if scope == "article":
        return True
    definition_location = source.location_for_span(definition_span)
    mention_location = source.location_for_span(mention)
    return (
        definition_location is not None
        and mention_location is not None
        and definition_location[0] == mention_location[0]
    )


def _link(
    source: ArticleDocument,
    span: TextSpan,
    mention_text: str,
    short_form: str,
    status: MentionStatus,
    indices: tuple[int, ...],
    policy: MentionLinkConfig,
    definition: AbbreviationDefinition | None,
    reason: str | None,
) -> MentionLink:
    return MentionLink(
        source.provenance.article_id,
        source.document.document_id,
        span,
        mention_text,
        short_form,
        status,
        definition,
        indices,
        policy.scope,
        ("exact_mention_span", "local_definition_scope")
        if definition is not None
        else (),
        reason,
    )


def _key(value: str, case_sensitive: bool) -> str:
    return value if case_sensitive else value.casefold()


def _definition_start(definition: AbbreviationDefinition) -> int:
    assert definition.short_form is not None
    return definition.short_form.start


__all__ = ["MentionLink", "MentionLinkConfig", "MentionStatus", "link_mentions"]
