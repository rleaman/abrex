"""Contract tests for immutable, registry-backed evaluation reporters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.config import ComponentSpec, ResolvedConfig
from abrex.domain import AbbreviationDefinition, Document, TextSpan
from abrex.evaluation import (
    DocumentEvaluation,
    EvaluationResult,
    MatchOutcome,
    MetricResult,
)
from abrex.reporting import (
    REPORTERS,
    DelimitedReporterConfig,
    ErrorTableReporter,
    HTMLErrorReporter,
    HTMLReporterConfig,
    JSONReporter,
    ReportContext,
    ReportingConfig,
    create_reporters,
)


def _context() -> ReportContext:
    gold = AbbreviationDefinition("doc", TextSpan(0, 2), TextSpan(3, 8))
    prediction = AbbreviationDefinition("doc", TextSpan(0, 2), TextSpan(3, 9))
    evaluation = EvaluationResult(
        "exact_pair",
        "1",
        (
            DocumentEvaluation(
                "doc",
                (gold,),
                (prediction,),
                (
                    MatchOutcome("doc", "fn", gold=gold),
                    MatchOutcome("doc", "fp", prediction=prediction),
                ),
            ),
        ),
        (MetricResult("pair_prf", (("tp", 0), ("fp", 1), ("fn", 1))),),
    )
    return ReportContext(
        evaluation,
        (Document("doc", "AB longform and surrounding context"),),
        (("run_id", "run-1"),),
        (("config_fingerprint", "abc"),),
    )


def test_json_report_contains_metadata_metrics_and_outcomes() -> None:
    payload = json.loads(JSONReporter().render(_context()))
    assert payload["schema_version"] == "evaluation-report-v1"
    assert payload["metadata"]["run"]["run_id"] == "run-1"
    assert payload["metrics"][0]["name"] == "pair_prf"
    assert [item["status"] for item in payload["documents"][0]["outcomes"]] == [
        "fn",
        "fp",
    ]


def test_table_and_html_reports_are_browsable_and_distinguish_errors() -> None:
    context = _context()
    table = ErrorTableReporter().render(context)
    assert "document_id\tstatus" in table
    assert "fn" in table and "fp" in table
    html = HTMLErrorReporter(context_chars=4).render(context)
    assert 'class="fn"' in html and 'class="fp"' in html
    assert "AB longform" in html
    assert "[document text unavailable]" not in html


def test_reporters_write_and_yaml_composition_use_injected_registry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.json"
    JSONReporter().write(_context(), path)
    assert json.loads(path.read_text(encoding="utf-8"))["reporter"]["key"] == "json"
    configured = ReportingConfig(
        reporters=(ComponentSpec(type="json"), ComponentSpec(type="html"))
    )
    reporters = create_reporters(configured)
    assert [reporter.identity for reporter in reporters] == [
        "json",
        "html_error_report",
    ]
    assert REPORTERS.keys() == (
        "csv",
        "error_table",
        "html",
        "html_error_report",
        "json",
        "tsv",
    )
    assert (
        create_reporters(
            ResolvedConfig.model_validate(
                {"reporting": {"reporters": [{"type": "json"}]}}
            )
        )[0].identity
        == "json"
    )


class StatusDimension:
    identity = "status"

    def classify(self, document_id: str, outcome: MatchOutcome) -> str | None:
        return outcome.status if document_id == "doc" else None


def test_context_validation_and_stratification_are_explicit() -> None:
    context = _context()
    with pytest.raises(TypeError, match="EvaluationResult"):
        ReportContext(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Document"):
        ReportContext(context.evaluation, (object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="duplicate"):
        ReportContext(context.evaluation, (Document("doc", "x"), Document("doc", "y")))
    with pytest.raises(TypeError, match="key/value"):
        ReportContext(context.evaluation, metadata=("bad",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unique"):
        ReportContext(context.evaluation, metadata=(("x", "1"), ("x", "2")))
    with pytest.raises(TypeError, match="dimensions"):
        ReportContext(context.evaluation, dimensions=(object(),))  # type: ignore[arg-type]
    enriched = ReportContext(
        context.evaluation, context.documents, dimensions=(StatusDimension(),)
    )
    payload = json.loads(JSONReporter().render(enriched))
    assert payload["stratification"]["status"]["fn"]["fn"] == 1
    assert payload["stratification"]["status"]["fn"]["tp"] == 0
    ErrorTableReporter().render(enriched)


def test_reporter_configuration_and_output_failures_are_actionable(
    tmp_path: Path,
) -> None:
    context = _context()
    assert DelimitedReporterConfig(delimiter=",").delimiter == ","
    assert HTMLReporterConfig(context_chars=0).context_chars == 0
    ErrorTableReporter(",").write(context, tmp_path / "report.csv")
    HTMLErrorReporter().write(context, tmp_path / "report.html")
    with pytest.raises(ValueError, match="delimiter"):
        ErrorTableReporter("|")
    with pytest.raises(ValueError, match="context_chars"):
        HTMLErrorReporter(-1)
    from abrex.reporting import reporting_config_from_resolved

    with pytest.raises(TypeError, match="ResolvedConfig"):
        reporting_config_from_resolved(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="mapping"):
        reporting_config_from_resolved(
            ResolvedConfig.model_validate({"reporting": "bad"})
        )
    with pytest.raises(TypeError, match="list"):
        reporting_config_from_resolved(
            ResolvedConfig.model_validate({"reporting": {"reporters": {}}})
        )
    with pytest.raises(TypeError, match="ReportingConfig"):
        create_reporters(object())  # type: ignore[arg-type]
    with pytest.raises(Exception, match="Unable to write"):
        JSONReporter().write(context, tmp_path / "missing" / "report.json")
    missing = HTMLErrorReporter().render(ReportContext(context.evaluation))
    assert "document text unavailable" in missing


def test_html_report_handles_outcome_without_spans() -> None:
    incomplete = AbbreviationDefinition("doc")
    evaluation = EvaluationResult(
        "exact_pair",
        "1",
        (
            DocumentEvaluation(
                "doc",
                (incomplete,),
                (),
                (MatchOutcome("doc", "unscoreable", gold=incomplete),),
            ),
        ),
        (),
    )
    report = ReportContext(evaluation, (Document("doc", "text"),))
    assert "no scoreable span" in HTMLErrorReporter().render(report)
