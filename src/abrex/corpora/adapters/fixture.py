"""Small embedded fixture adapter used to prove the corpus architecture."""

from __future__ import annotations

from collections.abc import Iterable

from abrex.corpora.base import (
    CorpusAdapter,
    CorpusAdapterError,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    map_source_record,
)
from abrex.corpora.diagnostics import DiagnosticsCollector
from abrex.domain import CorpusRecord, SourceTextSpan


class FixtureCorpusAdapter:
    """Adapter with clean, malformed, and repairable embedded source records."""

    identity = "fixture"
    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        """Parse the deterministic embedded fixture source."""

        if resource.location is not None:
            raise CorpusAdapterError(
                "The embedded fixture adapter does not read filesystem resources"
            )
        diagnostics.add(
            "info",
            "FIXTURE_SOURCE_SELECTED",
            "Using the embedded fixture source",
            record_id=resource.identifier,
            location="source",
        )
        return _fixture_records()

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        """Map fixture Unicode offsets through the common source mapper."""

        return map_source_record(
            source_record,
            adapter_identity=self.identity,
            adapter_version=self.version,
        )


def _fixture_records() -> tuple[ParsedSourceRecord, ...]:
    clean_text = "Tumor necrosis factor (TNF) is a cytokine."
    clean_long_start = clean_text.index("Tumor")
    clean_long_end = clean_text.index(" (TNF)")
    clean_short_start = clean_text.index("TNF")

    malformed_text = "Interleukin 6 (IL-6) is a signaling molecule."
    malformed_long_start = malformed_text.index("Interleukin")

    repairable_text = "Magnetic resonance imaging (MRI) is useful."
    repairable_long_start = repairable_text.index("Magnetic")
    repairable_long_end = repairable_text.index(" (MRI)")
    repairable_short_start = repairable_text.index("MRI")

    return (
        ParsedSourceRecord(
            record_id="clean-1",
            document_id="fixture-clean-1",
            text=clean_text,
            source_corpus="fixture",
            annotations=(
                ParsedSourceAnnotation(
                    annotation_id="clean-ann-1",
                    short_form=SourceTextSpan(
                        clean_short_start, clean_short_start + 3, "TNF"
                    ),
                    long_form=SourceTextSpan(
                        clean_long_start,
                        clean_long_end,
                        clean_text[clean_long_start:clean_long_end],
                    ),
                ),
            ),
        ),
        ParsedSourceRecord(
            record_id="malformed-1",
            document_id="fixture-malformed-1",
            text=malformed_text,
            source_corpus="fixture",
            annotations=(
                ParsedSourceAnnotation(
                    annotation_id="malformed-ann-1",
                    short_form=SourceTextSpan(
                        malformed_text.index("IL-6"),
                        malformed_text.index("IL-6") + 4,
                        "IL-6",
                    ),
                    long_form=SourceTextSpan(
                        malformed_long_start,
                        len(malformed_text) + 1,
                        malformed_text[malformed_long_start:],
                    ),
                ),
            ),
        ),
        ParsedSourceRecord(
            record_id="repairable-1",
            document_id="fixture-repairable-1",
            text=repairable_text,
            source_corpus="fixture",
            annotations=(
                ParsedSourceAnnotation(
                    annotation_id="repairable-ann-1",
                    short_form=SourceTextSpan(
                        repairable_short_start,
                        repairable_short_start + 3,
                        " MRI ",
                    ),
                    long_form=SourceTextSpan(
                        repairable_long_start,
                        repairable_long_end,
                        repairable_text[repairable_long_start:repairable_long_end],
                    ),
                ),
            ),
        ),
    )


__all__ = ["CorpusAdapter", "FixtureCorpusAdapter"]
