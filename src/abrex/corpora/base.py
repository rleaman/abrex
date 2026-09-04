"""Contracts and application service for corpus adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from abrex.corpora.diagnostics import DiagnosticsCollector, DiagnosticsSummary
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    SourceTextSpan,
    TextSpan,
)


class CorpusError(ValueError):
    """Base class for corpus adapter and pipeline failures."""


class CorpusAdapterError(CorpusError):
    """Raised when a source cannot be parsed or an adapter cannot run."""


class CorpusBuildError(CorpusError):
    """Raised by strict builds after dirty records have been diagnosed."""

    def __init__(self, message: str, diagnostics: DiagnosticsSummary) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class SourceResource:
    """A stable description of the source consumed by one adapter.

    ``location`` is optional because adapters may consume an embedded or
    service-provided resource. The adapter owns the meaning of the location
    and of its source-coordinate system.
    """

    identifier: str
    location: Path | None = None
    format: str | None = None
    metadata: Mapping[str, str] | tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("Source resource identifier must not be empty")
        if self.location is not None and not isinstance(self.location, Path):
            raise TypeError("Source resource location must be a pathlib.Path or None")
        if self.format is not None and not isinstance(self.format, str):
            raise TypeError("Source resource format must be a string or None")
        if isinstance(self.metadata, Mapping):
            metadata = tuple(sorted(self.metadata.items()))
            object.__setattr__(self, "metadata", metadata)
        if not isinstance(self.metadata, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(part, str) for part in item)
            for item in self.metadata
        ):
            raise TypeError("Source resource metadata must be a tuple of string pairs")

    @classmethod
    def from_path(
        cls,
        identifier: str,
        location: Path,
        *,
        format: str | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> SourceResource:
        """Construct a descriptor for a filesystem source."""

        return cls(identifier, location, format, metadata)


@dataclass(frozen=True, slots=True)
class ParsedSourceAnnotation:
    """Typed source fields produced by an adapter parser."""

    annotation_id: str | None = None
    short_form: SourceTextSpan | None = None
    long_form: SourceTextSpan | None = None


@dataclass(frozen=True, slots=True)
class ParsedSourceRecord:
    """A parsed source record before canonical mapping and normalization."""

    record_id: str
    document_id: str
    text: str
    annotations: Sequence[ParsedSourceAnnotation] = ()
    source_corpus: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise ValueError("Parsed record_id must not be empty")
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("Parsed document_id must not be empty")
        if not isinstance(self.text, str):
            raise TypeError("Parsed source text must be a string")
        if not isinstance(self.annotations, Sequence):
            raise TypeError(
                "Parsed annotations must be a sequence of source annotations"
            )
        annotations = tuple(self.annotations)
        if any(
            not isinstance(item, ParsedSourceAnnotation) for item in self.annotations
        ):
            raise TypeError("Parsed annotations must contain source annotations")
        object.__setattr__(self, "annotations", annotations)
        if self.source_corpus is not None and not isinstance(self.source_corpus, str):
            raise TypeError("Parsed source_corpus must be a string or None")


@runtime_checkable
class CorpusAdapter(Protocol):
    """Plugin contract for parsing and mapping one corpus source."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        """Parse source syntax into typed source records."""

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        """Map one parsed source record into canonical domain concepts."""


@runtime_checkable
class NormalizationStep(Protocol):
    """Plugin contract for one explicit canonical-record transformation."""

    @property
    def identity(self) -> str: ...

    @property
    def version(self) -> str: ...

    def normalize(
        self, record: CorpusRecord, diagnostics: DiagnosticsCollector
    ) -> CorpusRecord:
        """Return a new record and report every repair or transformation."""


class NormalizationPipeline:
    """Apply individually selected normalization steps in declared order."""

    def __init__(self, steps: Sequence[NormalizationStep] = ()) -> None:
        self.steps = tuple(steps)

    @property
    def identities(self) -> tuple[str, ...]:
        """Return the stable identities of the ordered steps."""

        return tuple(step.identity for step in self.steps)

    def apply(
        self, record: CorpusRecord, diagnostics: DiagnosticsCollector
    ) -> CorpusRecord:
        """Return the record after all configured steps have run."""

        for step in self.steps:
            record = step.normalize(record, diagnostics)
        return record


@dataclass(frozen=True, slots=True)
class CorpusBuildResult:
    """Canonical records and diagnostics from one deterministic build."""

    records: tuple[CorpusRecord, ...]
    diagnostics: DiagnosticsSummary
    source: SourceResource
    adapter_identity: str
    adapter_version: str
    normalizer_identities: tuple[str, ...]

    def diagnostics_json(self) -> str:
        """Return the machine-readable diagnostics artifact contents."""

        return self.diagnostics.to_json()


def map_source_record(
    source_record: ParsedSourceRecord, *, adapter_identity: str, adapter_version: str
) -> CorpusRecord:
    """Map source coordinates into canonical coordinates for same-text sources.

    This helper is intentionally only for adapters whose source coordinates are
    already Unicode Python character offsets. Adapters with another coordinate
    system must implement their own mapping and preserve the original values in
    provenance.
    """

    document = Document(source_record.document_id, source_record.text)
    definitions: list[AbbreviationDefinition] = []
    for annotation in source_record.annotations:
        short_form = _canonical_span(annotation.short_form)
        long_form = _canonical_span(annotation.long_form)
        provenance = AnnotationProvenance(
            source_corpus=source_record.source_corpus,
            source_record_id=source_record.record_id,
            source_annotation_id=annotation.annotation_id,
            original_short_form=annotation.short_form,
            original_long_form=annotation.long_form,
            adapter_identity=adapter_identity,
            adapter_version=adapter_version,
        )
        definitions.append(
            AbbreviationDefinition(
                document_id=source_record.document_id,
                short_form=short_form,
                long_form=long_form,
                short_form_text=_source_text(annotation.short_form),
                long_form_text=_source_text(annotation.long_form),
                provenance=provenance,
            )
        )
    return CorpusRecord(
        document=document,
        gold_annotations=tuple(definitions),
        record_id=source_record.record_id,
        provenance=AnnotationProvenance(
            source_corpus=source_record.source_corpus,
            source_record_id=source_record.record_id,
            adapter_identity=adapter_identity,
            adapter_version=adapter_version,
        ),
    )


def _canonical_span(source_span: SourceTextSpan | None) -> TextSpan | None:
    if source_span is None or not source_span.has_coordinates:
        return None
    assert source_span.start is not None and source_span.end is not None
    return TextSpan(source_span.start, source_span.end)


def _source_text(source_span: SourceTextSpan | None) -> str | None:
    return source_span.text if source_span is not None else None


class CorpusPipeline:
    """Compose an adapter and ordered normalizers into a corpus build."""

    def __init__(
        self,
        adapter: CorpusAdapter,
        normalizers: Sequence[NormalizationStep] = (),
        *,
        strict: bool = False,
    ) -> None:
        self.adapter = adapter
        self.normalizers = tuple(normalizers)
        self.normalization_pipeline = NormalizationPipeline(self.normalizers)
        self.strict = strict

    def build(self, resource: SourceResource) -> CorpusBuildResult:
        """Build valid records, diagnosing expected dirty-source failures."""

        collector = DiagnosticsCollector()
        try:
            source_records = tuple(self.adapter.parse(resource, collector))
        except CorpusAdapterError:
            raise
        except (OSError, UnicodeError) as error:
            raise CorpusAdapterError(
                f"Unable to parse source {resource.identifier!r}: {error}"
            ) from error

        mapped: list[CorpusRecord] = []
        for source_record in source_records:
            if not isinstance(source_record, ParsedSourceRecord):
                raise TypeError(
                    "CorpusAdapter.parse must yield ParsedSourceRecord values"
                )
            try:
                record = self.adapter.map_record(source_record)
                record = self.normalization_pipeline.apply(record, collector)
                record.validate()
            except (CorpusError, TypeError, ValueError) as error:
                collector.add(
                    "error",
                    "RECORD_DROPPED",
                    str(error),
                    action="dropped",
                    record_id=source_record.record_id,
                    location="record",
                )
                continue
            mapped.append(record)

        ordered = tuple(sorted(mapped, key=_record_sort_key))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous.id == current.id:
                collector.add(
                    "warning",
                    "DUPLICATE_RECORD_ID",
                    f"Record identifier {current.id!r} occurs more than once",
                    record_id=current.id,
                    location="record_id",
                )

        summary = collector.summary()
        if self.strict and any(
            item.severity == "error" for item in summary.diagnostics
        ):
            raise CorpusBuildError(
                f"Strict corpus build for {resource.identifier!r} had errors", summary
            )
        return CorpusBuildResult(
            records=ordered,
            diagnostics=summary,
            source=resource,
            adapter_identity=self.adapter.identity,
            adapter_version=self.adapter.version,
            normalizer_identities=self.normalization_pipeline.identities,
        )


def _record_sort_key(record: CorpusRecord) -> tuple[object, ...]:
    """Return a source-order-independent key while preserving duplicate rows."""

    annotations = tuple(
        (
            _span_key(annotation.short_form),
            _span_key(annotation.long_form),
            annotation.short_form_text,
            annotation.long_form_text,
            annotation.provenance.source_annotation_id
            if annotation.provenance is not None
            else None,
        )
        for annotation in record.gold_annotations
    )
    return (record.id, record.document.document_id, record.document.text, annotations)


def _span_key(span: TextSpan | None) -> tuple[int, int] | None:
    return None if span is None else (span.start, span.end)
