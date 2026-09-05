"""Built-in JSON, delimited-table, and HTML reporters."""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import Document
from abrex.evaluation import MatchOutcome
from abrex.reporting.base import ReportContext, Reporter, ReportingError
from abrex.reporting.common import (
    definition_dict,
    document_count_by_status,
    metadata_dict,
    metric_dicts,
    outcome_dict,
    outcome_rows,
    strata,
)


def _write(reporter: Reporter, context: ReportContext, path: Path) -> None:
    try:
        path.write_text(reporter.render(context), encoding="utf-8", newline="\n")
    except (OSError, UnicodeError) as error:
        raise ReportingError(
            f"Unable to write {reporter.identity} report {path}: {error}"
        ) from error


class JSONReporter:
    identity = "json"
    version = "1"

    def render(self, context: ReportContext) -> str:
        payload = {
            "schema_version": "evaluation-report-v1",
            "reporter": {"key": self.identity, "version": self.version},
            "metadata": metadata_dict(context),
            "metrics": metric_dicts(context),
            "documents": [
                {
                    "document_id": item.document_id,
                    "counts": document_count_by_status(item),
                    "outcomes": [outcome_dict(outcome) for outcome in item.outcomes],
                }
                for item in context.evaluation.documents
            ],
            "stratification": strata(context),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    def write(self, context: ReportContext, path: Path) -> None:
        _write(self, context, path)


class DelimitedReporterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    delimiter: Literal["\t", ","] = "\t"


class ErrorTableReporter:
    identity = "error_table"
    version = "1"

    def __init__(self, delimiter: str = "\t") -> None:
        if delimiter not in ("\t", ","):
            raise ValueError("delimiter must be tab or comma")
        self.delimiter = delimiter

    def render(self, context: ReportContext) -> str:
        stream = io.StringIO(newline="")
        fields = (
            "document_id",
            "status",
            "gold_index",
            "prediction_index",
            "gold",
            "prediction",
        )
        writer = csv.DictWriter(
            stream, fieldnames=fields, delimiter=self.delimiter, lineterminator="\n"
        )
        writer.writeheader()
        for row in outcome_rows(context):
            writer.writerow(
                {
                    key: json.dumps(row.get(key), ensure_ascii=False, sort_keys=True)
                    if key in ("gold", "prediction")
                    else row.get(key, "")
                    for key in fields
                }
            )
        return stream.getvalue()

    def write(self, context: ReportContext, path: Path) -> None:
        _write(self, context, path)


class HTMLReporterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    context_chars: int = Field(default=120, ge=0)


class HTMLErrorReporter:
    identity = "html_error_report"
    version = "1"

    def __init__(self, context_chars: int = 120) -> None:
        if context_chars < 0:
            raise ValueError("context_chars must be non-negative")
        self.context_chars = context_chars

    def render(self, context: ReportContext) -> str:
        documents = context.document_map
        rows: list[str] = []
        for document_evaluation in context.evaluation.documents:
            for outcome in document_evaluation.outcomes:
                rows.append(self._row(outcome, documents.get(outcome.document_id)))
        header = (
            '<!doctype html>\n<html><head><meta charset="utf-8">'
            "<title>Abbreviation error report</title>\n"
            "<style>body{font:14px sans-serif} .tp{background:#e8f5e9}"
            ".fp{background:#ffebee}.fn{background:#fff3e0}"
            ".unscoreable{background:#eeeeee} td{padding:.4rem;"
            "vertical-align:top} code{white-space:pre-wrap}</style></head>\n"
            "<body><h1>Abbreviation error report</h1><pre>"
        )
        table = (
            "</pre><table><thead><tr><th>Document</th><th>Status</th>"
            "<th>Gold</th><th>Prediction</th><th>Context</th>"
            "</tr></thead><tbody>"
        )
        metadata = html.escape(
            json.dumps(
                metadata_dict(context), ensure_ascii=False, indent=2, sort_keys=True
            )
        )
        return (
            header
            + metadata
            + table
            + "".join(rows)
            + "</tbody></table></body></html>\n"
        )

    def _row(self, outcome: MatchOutcome, document: Document | None) -> str:
        status = outcome.status
        context = self._context(outcome, document)
        return (
            f'<tr class="{status}"><td>{html.escape(outcome.document_id)}</td>'
            f"<td><strong>{status.upper()}</strong></td>"
            f"<td>{html.escape(str(definition_dict(outcome.gold)))}</td>"
            f"<td>{html.escape(str(definition_dict(outcome.prediction)))}</td>"
            f"<td><code>{html.escape(context)}</code></td></tr>"
        )

    def _context(self, outcome: MatchOutcome, document: Document | None) -> str:
        if document is None:
            return "[document text unavailable]"
        spans = [
            getattr(annotation, field)
            for annotation in (outcome.gold, outcome.prediction)
            if annotation is not None
            for field in ("short_form", "long_form")
            if getattr(annotation, field) is not None
        ]
        if not spans:
            return "[no scoreable span]"
        start = max(0, min(span.start for span in spans) - self.context_chars)
        end = min(
            len(document.text),
            max(span.end for span in spans) + self.context_chars,
        )
        return document.text[start:end]

    def write(self, context: ReportContext, path: Path) -> None:
        _write(self, context, path)


__all__ = [
    "DelimitedReporterConfig",
    "ErrorTableReporter",
    "HTMLReporterConfig",
    "HTMLErrorReporter",
    "JSONReporter",
]
