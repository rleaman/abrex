"""Built-in candidate generators."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates.base import (
    Candidate,
    CandidateDiagnostic,
    CandidateGenerationResult,
)
from abrex.domain import AnnotationProvenance, Document, SourceTextSpan, TextSpan
from abrex.resources import FrequencyResource, ResourceVariant

if TYPE_CHECKING:
    from abrex.literature.models import ArticleDocument, ArticleStructure

PARENTHETICAL_GENERATOR_VERSION = "1"
STRUCTURAL_GENERATOR_VERSION = "1"
LEXICAL_GENERATOR_VERSION = "1"


class ParentheticalCandidateConfig(BaseModel):
    """Explicit scope controls for local ``long form (SHORT)`` enumeration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_short_form_length: int = Field(default=2, ge=1)
    maximum_short_form_length: int = Field(default=30, ge=1)
    maximum_long_form_words: int = Field(default=10, ge=1)


class ParentheticalCandidateGenerator:
    """Enumerate preceding word windows for parenthetical short forms.

    Every preceding window up to ``maximum_long_form_words`` is retained. The
    generator does not align characters or decide whether a pair is valid;
    those are resolver/scorer responsibilities. Unsupported or malformed
    parentheticals produce explicit pruning diagnostics.
    """

    identity = "parenthetical"
    version = PARENTHETICAL_GENERATOR_VERSION
    _parenthetical = re.compile(r"\((?P<contents>[^()]*)\)")
    _short_form = re.compile(r"[A-Za-z][A-Za-z0-9-]*\Z")
    _word = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

    def __init__(self, **params: object) -> None:
        self.config = ParentheticalCandidateConfig.model_validate(params)

    def generate(self, document: Document) -> CandidateGenerationResult:
        """Enumerate candidates and retain every pruning diagnostic."""

        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for match in self._parenthetical.finditer(document.text):
            contents = match.group("contents")
            short_text = contents.strip()
            short_start = match.start("contents") + (
                len(contents) - len(contents.lstrip())
            )
            short_end = short_start + len(short_text)
            if not self._short_form.fullmatch(short_text):
                diagnostics.append(
                    _pruned(
                        document,
                        "short_form_invalid",
                        "Parenthetical text is not an acronym",
                    )
                )
                continue
            if len(short_text) < self.config.minimum_short_form_length:
                diagnostics.append(
                    _pruned(
                        document,
                        "short_form_too_short",
                        "Short form is below configured minimum",
                    )
                )
                continue
            if len(short_text) > self.config.maximum_short_form_length:
                diagnostics.append(
                    _pruned(
                        document,
                        "short_form_too_long",
                        "Short form exceeds configured maximum",
                    )
                )
                continue
            words = tuple(self._word.finditer(document.text[: match.start()].rstrip()))
            if not words:
                diagnostics.append(
                    _pruned(
                        document,
                        "missing_long_form_context",
                        "No preceding word can form a long-form candidate",
                    )
                )
                continue
            selected = words[-self.config.maximum_long_form_words :]
            provenance = AnnotationProvenance(
                adapter_identity=self.identity,
                adapter_version=self.version,
                transformation_notes=("enumerated_parenthetical_window",),
            )
            for word in reversed(selected):
                long_span = TextSpan(word.start(), selected[-1].end())
                candidates.append(
                    Candidate(
                        document.document_id,
                        TextSpan(short_start, short_end),
                        long_span,
                        "parenthetical_after_long_form",
                        provenance,
                    )
                )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )


def _pruned(document: Document, code: str, message: str) -> CandidateDiagnostic:
    return CandidateDiagnostic("info", code, message, document.document_id, "pruned")


class LexicalResourceCandidateConfig(BaseModel):
    """Bounds and local resources for exact lexical candidate enumeration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_paths: tuple[Path, ...] = Field(min_length=1)
    maximum_window: int = Field(default=240, ge=1)


class LexicalResourceCandidateGenerator:
    """Pair exact resource variants only when both forms occur locally.

    Aggregate resources propose evidence, never definitions.  Every emitted
    candidate therefore contains canonical spans for both exact occurrences;
    a resource row with no local long-form occurrence is not emitted.
    """

    identity = "lexical_resource"
    version = LEXICAL_GENERATOR_VERSION

    def __init__(self, **params: object) -> None:
        self.config = LexicalResourceCandidateConfig.model_validate(params)
        self.resources = tuple(
            FrequencyResource(path) for path in self.config.resource_paths
        )

    @property
    def cache_identity(self) -> str:
        """Return a content-aware identity for reproducible candidate reuse."""

        sources = ",".join(
            f"{summary.source_label}:{summary.source_sha256}"
            for summary in (resource.summary() for resource in self.resources)
        )
        return f"{self.identity}:{self.version}:{self.config.maximum_window}:{sources}"

    def generate(self, document: Document) -> CandidateGenerationResult:
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for resource in self.resources:
            summary = resource.summary()
            for short_key in self._short_keys(document, resource):
                variants = resource.lookup(short_key)
                for variant in variants:
                    short_occurrences = tuple(
                        _occurrences(document.text, variant.short_form_raw)
                    )
                    long_occurrences = tuple(
                        _occurrences(document.text, variant.long_form_raw)
                    )
                    if not short_occurrences or not long_occurrences:
                        diagnostics.append(
                            _pruned(
                                document,
                                "resource_pair_not_local",
                                "Resource variant lacked one or both exact local spans",
                            )
                        )
                        continue
                    for short_start, short_end in short_occurrences:
                        for long_start, long_end in long_occurrences:
                            if (
                                abs(short_start - long_start)
                                > self.config.maximum_window
                            ):
                                continue
                            candidates.append(
                                Candidate(
                                    document.document_id,
                                    TextSpan(short_start, short_end),
                                    TextSpan(long_start, long_end),
                                    "resource_local_window",
                                    _resource_provenance(variant, summary.source_label),
                                )
                            )
        if not candidates:
            diagnostics.append(
                _pruned(
                    document,
                    "resource_no_local_pair",
                    "No resource pair had two local spans",
                )
            )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )

    @staticmethod
    def _short_keys(document: Document, resource: FrequencyResource) -> tuple[str, ...]:
        # Query keys are obtained from the resource itself, preserving its
        # configured normalization policy without guessing it here.
        keys: set[str] = set()
        for match in re.finditer(r"[A-Za-z][A-Za-z0-9-]{1,29}", document.text):
            keys.add(match.group(0))
        return tuple(sorted(keys))


def _occurrences(text: str, value: str) -> list[tuple[int, int]]:
    if not value:
        return []
    return [
        (match.start(), match.end()) for match in re.finditer(re.escape(value), text)
    ]


def _resource_provenance(
    variant: ResourceVariant, source_label: str
) -> AnnotationProvenance:
    return AnnotationProvenance(
        source_corpus="lexical_resource",
        source_record_id=f"{variant.source_label}:{variant.source_sha256}",
        original_short_form=SourceTextSpan(text=variant.short_form_raw),
        original_long_form=SourceTextSpan(text=variant.long_form_raw),
        adapter_identity="lexical_resource",
        adapter_version=LEXICAL_GENERATOR_VERSION,
        transformation_notes=(
            f"resource_source={source_label}",
            "exact_local_occurrences",
        ),
    )


class ReverseOrderCandidateConfig(BaseModel):
    """Bounds for ``(SHORT) long form`` and separator constructions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_gap: int = Field(default=160, ge=1)
    maximum_long_form_words: int = Field(default=12, ge=1)


class ReverseOrderCandidateGenerator:
    """Enumerate reverse-order and separator-defined candidate pairs."""

    identity = "reverse_order"
    version = STRUCTURAL_GENERATOR_VERSION
    _short = re.compile(r"[A-Za-z][A-Za-z0-9-]{1,29}")
    _word = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

    def __init__(self, **params: object) -> None:
        self.config = ReverseOrderCandidateConfig.model_validate(params)

    def generate(self, document: Document) -> CandidateGenerationResult:
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for match in re.finditer(r"\((?P<short>[^()]*)\)", document.text):
            short = match.group("short").strip()
            if not self._short.fullmatch(short):
                diagnostics.append(
                    _pruned(
                        document,
                        "reverse_short_invalid",
                        "Reverse-order parenthetical is not an acronym",
                    )
                )
                continue
            start = match.end()
            words = tuple(
                self._word.finditer(
                    document.text[start : start + self.config.maximum_gap]
                )
            )
            if not words:
                diagnostics.append(
                    _pruned(
                        document,
                        "reverse_long_missing",
                        "Reverse-order construction has no following context",
                    )
                )
                continue
            selected = words[: self.config.maximum_long_form_words]
            long_start = start + selected[0].start()
            long_end = start + selected[-1].end()
            candidates.append(
                _candidate(
                    document,
                    match.start("short"),
                    match.end("short"),
                    long_start,
                    long_end,
                    "reverse_order",
                    match.group(0),
                )
            )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )


class NestedParentheticalCandidateConfig(BaseModel):
    """Bounds for nested parenthetical text enumeration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_depth: int = Field(default=4, ge=1)
    maximum_long_form_words: int = Field(default=12, ge=1)


class NestedParentheticalCandidateGenerator:
    """Enumerate acronym-like inner parentheses and their local preceding text."""

    identity = "nested_parenthetical"
    version = STRUCTURAL_GENERATOR_VERSION
    _short = re.compile(r"[A-Za-z][A-Za-z0-9-]{1,29}")
    _word = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

    def __init__(self, **params: object) -> None:
        self.config = NestedParentheticalCandidateConfig.model_validate(params)

    def generate(self, document: Document) -> CandidateGenerationResult:
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        depth = 0
        for index, character in enumerate(document.text):
            if character == "(":
                depth += 1
            elif character == ")":
                depth = max(0, depth - 1)
            if character != "(" or depth < 2:
                continue
            end = document.text.find(")", index + 1)
            if end < 0:
                diagnostics.append(
                    _pruned(
                        document, "nested_unclosed", "Nested parenthetical is unclosed"
                    )
                )
                continue
            short = document.text[index + 1 : end].strip()
            if not self._short.fullmatch(short):
                continue
            words = tuple(self._word.finditer(document.text[:index].rstrip()))
            selected = words[-self.config.maximum_long_form_words :]
            if not selected:
                diagnostics.append(
                    _pruned(
                        document,
                        "nested_long_missing",
                        "Nested acronym has no preceding words",
                    )
                )
                continue
            candidates.append(
                _candidate(
                    document,
                    index + 1,
                    end,
                    selected[0].start(),
                    selected[-1].end(),
                    "nested_parenthetical",
                    "nested",
                )
            )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )


class StructuredRelationCandidateConfig(BaseModel):
    """Complexity bounds for table and definition-list candidate enumeration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_structures_per_parent: int = Field(default=64, ge=1)
    maximum_text_length: int = Field(default=1000, ge=1)


class StructuredRelationCandidateGenerator:
    """Enumerate same-row and term/definition candidates from T027 structures."""

    identity = "structured_relations"
    version = STRUCTURAL_GENERATOR_VERSION
    _short = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,29}$")

    def __init__(self, **params: object) -> None:
        self.config = StructuredRelationCandidateConfig.model_validate(params)

    def generate(self, document: Document) -> CandidateGenerationResult:
        return CandidateGenerationResult(
            document.document_id,
            (),
            (
                _pruned(
                    document,
                    "structure_metadata_required",
                    "Table and definition-list structures require "
                    "ArticleDocument metadata",
                ),
            ),
        )

    def generate_article(self, article: ArticleDocument) -> CandidateGenerationResult:
        document = article.document
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        groups: dict[str, list[ArticleStructure]] = defaultdict(list)
        for structure in article.structures:
            if len(structure.text) <= self.config.maximum_text_length:
                groups[_relation_group(structure)].append(structure)
            else:
                diagnostics.append(
                    _pruned(
                        document,
                        "structure_text_too_long",
                        f"Skipped {structure.node_id} above text bound",
                    )
                )
        for structures in sorted(
            groups.values(), key=lambda value: tuple(item.node_id for item in value)
        ):
            for left_index, left in enumerate(
                structures[: self.config.maximum_structures_per_parent]
            ):
                for right in structures[
                    left_index + 1 : self.config.maximum_structures_per_parent
                ]:
                    pair = _structured_pair(left, right)
                    if pair is None:
                        continue
                    short_text, long_text, construction = pair
                    short_span = _locate(article, short_text)
                    long_span = _locate(article, long_text)
                    if short_span is None or long_span is None:
                        diagnostics.append(
                            _pruned(
                                document,
                                "structure_unmapped",
                                f"Could not map {left.node_id} and {right.node_id} "
                                "to canonical offsets",
                            )
                        )
                        continue
                    candidates.append(
                        Candidate(
                            document.document_id,
                            short_span,
                            long_span,
                            construction,
                            AnnotationProvenance(
                                adapter_identity=self.identity,
                                adapter_version=self.version,
                                transformation_notes=(
                                    f"source_path:{left.source_path}",
                                    f"source_path:{right.source_path}",
                                    "parent_id:"
                                    f"{left.parent_id or right.parent_id or ''}",
                                ),
                            ),
                        )
                    )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )


def _relation_group(structure: ArticleStructure) -> str:
    """Return a stable row/list-item grouping key from a T027 source path."""

    if structure.kind.startswith("table-"):
        return re.split(r"/(?:th|td)\[", structure.source_path, maxsplit=1)[0]
    if structure.kind in {"definition-term", "definition"}:
        return re.sub(r"/(?:term|definition)/\d+$", "/item", structure.node_id)
    return structure.parent_id or structure.node_id


def _structured_pair(
    first: ArticleStructure, second: ArticleStructure
) -> tuple[str, str, str] | None:
    first_text, second_text = first.text.strip(), second.text.strip()
    if _looks_short(first_text) and _looks_long(second_text):
        return first_text, second_text, "structured_relation"
    if _looks_short(second_text) and _looks_long(first_text):
        return second_text, first_text, "structured_relation"
    return None


def _looks_short(value: str) -> bool:
    return bool(StructuredRelationCandidateGenerator._short.fullmatch(value))


def _looks_long(value: str) -> bool:
    return len(value.split()) >= 2


def _locate(article: ArticleDocument, value: str) -> TextSpan | None:
    positions = [location.canonical_span for location in article.section_locations]
    for section in positions:
        start = article.document.text.find(value, section.start, section.end)
        if start >= 0:
            return TextSpan(start, start + len(value))
    return None


def _candidate(
    document: Document,
    short_start: int,
    short_end: int,
    long_start: int,
    long_end: int,
    construction: str,
    note: str,
) -> Candidate:
    return Candidate(
        document.document_id,
        TextSpan(short_start, short_end),
        TextSpan(long_start, long_end),
        construction,
        AnnotationProvenance(
            adapter_identity=construction,
            adapter_version=STRUCTURAL_GENERATOR_VERSION,
            transformation_notes=(note,),
        ),
    )


__all__ = [
    "PARENTHETICAL_GENERATOR_VERSION",
    "ParentheticalCandidateConfig",
    "ParentheticalCandidateGenerator",
    "ReverseOrderCandidateConfig",
    "ReverseOrderCandidateGenerator",
    "NestedParentheticalCandidateConfig",
    "NestedParentheticalCandidateGenerator",
    "StructuredRelationCandidateConfig",
    "StructuredRelationCandidateGenerator",
    "LEXICAL_GENERATOR_VERSION",
    "LexicalResourceCandidateConfig",
    "LexicalResourceCandidateGenerator",
]
