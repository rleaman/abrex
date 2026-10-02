"""Deterministic table/list candidates informed by the CLP v5.1 parser."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from abrex.candidates.base import (
    Candidate,
    CandidateDiagnostic,
    CandidateGenerationResult,
)
from abrex.domain import AnnotationProvenance, Document, SourceTextSpan, TextSpan

if TYPE_CHECKING:
    from abrex.literature.models import ArticleDocument, ArticleStructure

CLP_TABLE_VERSION = "5.1-abrex.1"


class CLPTableCandidateConfig(BaseModel):
    """Explicit limits for two-column table and list parsing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_rows: int = Field(default=500, ge=1)
    maximum_cell_characters: int = Field(default=500, ge=1)


class CLPTableCandidateGenerator:
    """Emit uniquely mapped pairs from deterministic two-column structures."""

    identity = "clp_table_v5_1"
    version = CLP_TABLE_VERSION
    _short_form = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+./_α-ωΑ-Ω-]{0,29}$")
    _row_path = re.compile(r"(?P<row>.+/tr\[\d+\])/(?:td|th)\[\d+\]$")

    def __init__(self, **params: object) -> None:
        self.config = CLPTableCandidateConfig.model_validate(params)

    def generate(self, document: Document) -> CandidateGenerationResult:
        """Parse tab/newline-flattened two-column material."""

        rows = _text_rows(document.text, self.config.maximum_rows)
        return self._from_rows(document, rows, construction="clp_flat_two_column")

    def generate_article(self, article: ArticleDocument) -> CandidateGenerationResult:
        """Parse exact table rows retained by the JATS structure adapter."""

        grouped: dict[str, list[ArticleStructure]] = defaultdict(list)
        diagnostics: list[CandidateDiagnostic] = []
        for structure in article.structures:
            if structure.kind not in {"table-cell", "table-header-cell"}:
                continue
            match = self._row_path.match(structure.source_path)
            if match is None:
                diagnostics.append(
                    _diagnostic(
                        article.document,
                        "clp_table_unknown_row",
                        f"Could not identify row for {structure.source_path}",
                    )
                )
                continue
            grouped[match.group("row")].append(structure)
        rows = [
            tuple(cell.text.strip() for cell in cells)
            for _, cells in sorted(grouped.items())
            if len(cells) == 2
        ][: self.config.maximum_rows]
        result = self._from_rows(
            article.document, rows, construction="clp_jats_two_column"
        )
        return CandidateGenerationResult(
            result.document_id,
            result.candidates,
            tuple(diagnostics) + result.diagnostics,
        )

    def _from_rows(
        self,
        document: Document,
        rows: Iterable[tuple[str, ...]],
        *,
        construction: str,
    ) -> CandidateGenerationResult:
        candidates: list[Candidate] = []
        diagnostics: list[CandidateDiagnostic] = []
        for row_number, row in enumerate(rows, start=1):
            if len(row) != 2 or not all(row):
                diagnostics.append(
                    _diagnostic(
                        document,
                        "clp_table_malformed_row",
                        f"Row {row_number} is not a non-empty two-cell row",
                    )
                )
                continue
            if any(len(value) > self.config.maximum_cell_characters for value in row):
                diagnostics.append(
                    _diagnostic(
                        document,
                        "clp_table_cell_too_long",
                        f"Row {row_number} exceeds the configured cell limit",
                    )
                )
                continue
            oriented = self._orient(row[0], row[1])
            if oriented is None:
                diagnostics.append(
                    _diagnostic(
                        document,
                        "clp_table_orientation_unknown",
                        f"Row {row_number} has no deterministic orientation",
                    )
                )
                continue
            short, long = oriented
            short_span = _unique_span(document.text, short)
            long_span = _unique_span(document.text, long)
            if short_span is None or long_span is None:
                diagnostics.append(
                    _diagnostic(
                        document,
                        "clp_table_unmapped",
                        f"Row {row_number} lacks unique exact source occurrences",
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
                        source_corpus="CellLiteraturePipeline/rules-v5.1",
                        original_short_form=SourceTextSpan(text=short),
                        original_long_form=SourceTextSpan(text=long),
                        adapter_identity=self.identity,
                        adapter_version=self.version,
                        transformation_notes=(
                            "deterministic_two_column_rule",
                            "unique_exact_occurrences_only",
                        ),
                    ),
                )
            )
        if not candidates:
            diagnostics.append(
                _diagnostic(
                    document,
                    "clp_table_no_candidates",
                    "No deterministic exact table/list pair was emitted",
                )
            )
        return CandidateGenerationResult(
            document.document_id, tuple(candidates), tuple(diagnostics)
        )

    def _orient(self, first: str, second: str) -> tuple[str, str] | None:
        first_short = self._short_form.fullmatch(first) is not None
        second_short = self._short_form.fullmatch(second) is not None
        if first_short and not second_short:
            return first, second
        if second_short and not first_short:
            return second, first
        return None


def _text_rows(text: str, maximum_rows: int) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for line in text.splitlines():
        cells = tuple(value.strip() for value in line.split("\t") if value.strip())
        if len(cells) == 2:
            rows.append(cells)
        elif len(cells) > 2 and len(cells) % 2 == 0:
            rows.extend(
                tuple(cells[index : index + 2]) for index in range(0, len(cells), 2)
            )
        if len(rows) >= maximum_rows:
            break
    return tuple(rows[:maximum_rows])


def _unique_span(text: str, value: str) -> TextSpan | None:
    matches = tuple(re.finditer(re.escape(value), text))
    if len(matches) != 1:
        return None
    return TextSpan(matches[0].start(), matches[0].end())


def _diagnostic(document: Document, code: str, message: str) -> CandidateDiagnostic:
    return CandidateDiagnostic("info", code, message, document.document_id, "pruned")


__all__ = ["CLPTableCandidateConfig", "CLPTableCandidateGenerator"]
