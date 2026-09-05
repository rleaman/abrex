"""Registry-backed evaluation result reporting."""

from abrex.reporting.base import (
    ReportContext,
    Reporter,
    ReportingError,
    StratificationDimension,
)
from abrex.reporting.config import (
    ReportingConfig,
    create_reporters,
    reporting_config_from_resolved,
)
from abrex.reporting.registry import REPORTERS
from abrex.reporting.reporters import (
    DelimitedReporterConfig,
    ErrorTableReporter,
    HTMLErrorReporter,
    HTMLReporterConfig,
    JSONReporter,
)

__all__ = [
    "DelimitedReporterConfig",
    "ErrorTableReporter",
    "HTMLReporterConfig",
    "HTMLErrorReporter",
    "JSONReporter",
    "REPORTERS",
    "ReportContext",
    "Reporter",
    "ReportingConfig",
    "ReportingError",
    "StratificationDimension",
    "create_reporters",
    "reporting_config_from_resolved",
]
