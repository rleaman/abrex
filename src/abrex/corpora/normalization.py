"""Registry-backed canonical-record normalization steps."""

from __future__ import annotations

from dataclasses import replace

from abrex.corpora.base import NormalizationStep
from abrex.corpora.diagnostics import DiagnosticsCollector
from abrex.domain import AbbreviationDefinition, AnnotationProvenance, CorpusRecord


class TrimCapturedText:
    """Trim source-captured edge whitespace without inferring missing text.

    The canonical span remains unchanged. The original captured value remains
    available in provenance, and a repair diagnostic is emitted only when the
    trimmed value agrees with the document span.
    """

    identity = "trim_captured_text"
    version = "1"

    def normalize(
        self, record: CorpusRecord, diagnostics: DiagnosticsCollector
    ) -> CorpusRecord:
        changed: list[AbbreviationDefinition] = []
        for annotation in record.gold_annotations:
            updated = annotation
            for field_name in ("short_form_text", "long_form_text"):
                captured = getattr(updated, field_name)
                if captured is None or captured == captured.strip():
                    continue
                trimmed = captured.strip()
                span = getattr(updated, field_name.removesuffix("_text"))
                if span is None or record.document.text_for(span) != trimmed:
                    continue
                provenance = _add_note(
                    updated.provenance,
                    f"{self.identity}: trimmed {field_name} edge whitespace",
                )
                updated = replace(
                    updated, **{field_name: trimmed, "provenance": provenance}
                )
                diagnostics.add(
                    "warning",
                    "CAPTURED_TEXT_TRIMMED",
                    f"Trimmed edge whitespace from {field_name}",
                    action="repaired",
                    record_id=record.id,
                    annotation_id=(
                        provenance.source_annotation_id if provenance else None
                    ),
                    location=field_name,
                )
            changed.append(updated)
        return replace(record, gold_annotations=tuple(changed))


class IdentityNormalization:
    """Explicit no-op step useful for configuration and contract tests."""

    identity = "identity"
    version = "1"

    def normalize(
        self, record: CorpusRecord, diagnostics: DiagnosticsCollector
    ) -> CorpusRecord:
        return record


def _add_note(
    provenance: AnnotationProvenance | None, note: str
) -> AnnotationProvenance:
    if provenance is None:
        return AnnotationProvenance(transformation_notes=(note,))
    return replace(
        provenance, transformation_notes=(*provenance.transformation_notes, note)
    )


__all__ = ["IdentityNormalization", "NormalizationStep", "TrimCapturedText"]
