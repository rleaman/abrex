"""Extensible corpus adapters and canonical-record normalization."""

from abrex.corpora.adapters import FixtureCorpusAdapter
from abrex.corpora.base import (
    CorpusAdapter,
    CorpusAdapterError,
    CorpusBuildError,
    CorpusBuildResult,
    CorpusError,
    CorpusPipeline,
    NormalizationPipeline,
    NormalizationStep,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    map_source_record,
)
from abrex.corpora.config import (
    CorpusConfig,
    SourceResourceConfig,
    corpus_config_from_resolved,
    create_corpus_pipeline,
)
from abrex.corpora.diagnostics import (
    AdapterDiagnostic,
    DiagnosticsCollector,
    DiagnosticsSummary,
)
from abrex.corpora.normalization import IdentityNormalization, TrimCapturedText
from abrex.corpora.registry import CORPUS_ADAPTERS, NORMALIZERS

__all__ = [
    "AdapterDiagnostic",
    "CorpusAdapter",
    "CorpusAdapterError",
    "CorpusBuildError",
    "CorpusBuildResult",
    "CorpusConfig",
    "CorpusError",
    "CorpusPipeline",
    "CORPUS_ADAPTERS",
    "DiagnosticsCollector",
    "DiagnosticsSummary",
    "FixtureCorpusAdapter",
    "IdentityNormalization",
    "NORMALIZERS",
    "NormalizationPipeline",
    "NormalizationStep",
    "ParsedSourceAnnotation",
    "ParsedSourceRecord",
    "SourceResource",
    "SourceResourceConfig",
    "TrimCapturedText",
    "corpus_config_from_resolved",
    "create_corpus_pipeline",
    "map_source_record",
]
