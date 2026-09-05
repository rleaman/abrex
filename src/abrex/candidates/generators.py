"""Built-in candidate generators."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates.base import (
    Candidate,
    CandidateDiagnostic,
    CandidateGenerationResult,
)
from abrex.domain import AnnotationProvenance, Document, TextSpan

PARENTHETICAL_GENERATOR_VERSION = "1"


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


__all__ = [
    "PARENTHETICAL_GENERATOR_VERSION",
    "ParentheticalCandidateConfig",
    "ParentheticalCandidateGenerator",
]
