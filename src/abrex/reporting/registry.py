"""Registry for report renderers."""

from abrex.registry import Registry
from abrex.reporting.base import Reporter
from abrex.reporting.reporters import (
    DelimitedReporterConfig,
    ErrorTableReporter,
    HTMLErrorReporter,
    HTMLReporterConfig,
    JSONReporter,
)

REPORTERS = Registry[Reporter]("reporters")
REPORTERS.register("json", JSONReporter)
REPORTERS.register(
    "error_table",
    ErrorTableReporter,
    aliases=("tsv", "csv"),
    config_model=DelimitedReporterConfig,
)
REPORTERS.register(
    "html_error_report",
    HTMLErrorReporter,
    aliases=("html",),
    config_model=HTMLReporterConfig,
)

__all__ = ["REPORTERS"]
