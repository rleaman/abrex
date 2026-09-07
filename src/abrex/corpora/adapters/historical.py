"""Adapters for the user-supplied historical abbreviation corpora.

The adapters deliberately do not download data. BioC sources are parsed as
documents, passages, annotations, and relations. SDU@AAAI-21 sources use
token-level BIO labels and therefore reconstruct character offsets from
tokens; SDU@AAAI-22 sources provide independent half-open acronym and
long-form character spans.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from abrex.corpora.base import (
    CorpusAdapterError,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    map_source_record,
)
from abrex.corpora.diagnostics import DiagnosticsCollector
from abrex.domain import CorpusRecord, SourceTextSpan

BioCPairingPolicy = Literal["relations_only", "relations_or_order_fallback"]
BioCTextPolicy = Literal["preserve_source", "overlay_annotation_text"]
BioCLocationPolicy = Literal["first_location", "reject_discontinuous"]


@dataclass(frozen=True, slots=True)
class _BioCEntity:
    """One BioC annotation without collapsing source identifiers."""

    identifier: str
    source_identifier: str
    span: SourceTextSpan
    role: str
    ordinal: int


class BioCCorpusAdapter:
    """Read BioC XML or JSON with explicit, auditable pairing semantics.

    The original BioC benchmark exports use ``LongForm``/``ShortForm``
    relation nodes.  A named ``relations_or_order_fallback`` policy is
    retained for documents without relation nodes because this is the source
    contract used by the historical exports.  It is never used by the SDU
    adapters, whose independent lists have a different scientific meaning.
    """

    def __init__(
        self,
        *,
        dataset_variant: str = "bioc",
        pairing_policy: BioCPairingPolicy = "relations_or_order_fallback",
        text_policy: BioCTextPolicy = "preserve_source",
        location_policy: BioCLocationPolicy = "first_location",
    ) -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        if pairing_policy not in ("relations_only", "relations_or_order_fallback"):
            raise ValueError(f"Unsupported BioC pairing_policy: {pairing_policy!r}")
        if text_policy not in ("preserve_source", "overlay_annotation_text"):
            raise ValueError(f"Unsupported BioC text_policy: {text_policy!r}")
        if location_policy not in ("first_location", "reject_discontinuous"):
            raise ValueError(f"Unsupported BioC location_policy: {location_policy!r}")
        self.dataset_variant = dataset_variant
        self.pairing_policy = pairing_policy
        self.text_policy = text_policy
        self.location_policy = location_policy

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "2"

    @property
    def policy_identity(self) -> str:
        """Return the stable semantic policy identity for provenance."""

        return ":".join(
            (
                f"pairing={self.pairing_policy}",
                f"text={self.text_policy}",
                f"locations={self.location_policy}",
            )
        )

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        path = _require_path(resource)
        try:
            suffix = path.suffix.lower()
            if resource.format == "json" or suffix == ".json":
                return _parse_bioc_json(
                    path,
                    self.dataset_variant,
                    diagnostics,
                    pairing_policy=self.pairing_policy,
                    text_policy=self.text_policy,
                    location_policy=self.location_policy,
                )
            return _parse_bioc_xml(
                path,
                self.dataset_variant,
                diagnostics,
                pairing_policy=self.pairing_policy,
                text_policy=self.text_policy,
                location_policy=self.location_policy,
            )
        except (OSError, UnicodeError, ET.ParseError, json.JSONDecodeError) as error:
            raise CorpusAdapterError(
                f"Unable to parse BioC source {path}: {error}"
            ) from error

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        record = map_source_record(
            source_record,
            adapter_identity=self.identity,
            adapter_version=self.version,
        )
        note = f"bioc semantic policy: {self.policy_identity}"
        return replace(
            record,
            provenance=replace(
                record.provenance,
                transformation_notes=(*source_record.transformation_notes, note),
            )
            if record.provenance is not None
            else None,
            gold_annotations=tuple(
                replace(
                    annotation,
                    provenance=(
                        replace(
                            annotation.provenance,
                            transformation_notes=(
                                *annotation.provenance.transformation_notes,
                                note,
                            ),
                        )
                        if annotation.provenance is not None
                        else None
                    ),
                )
                for annotation in record.gold_annotations
            ),
        )


class SDUAcronymIdentificationAdapter:
    """Read SDU@AAAI-21/22 acronym-identification JSON files."""

    def __init__(
        self, *, dataset_variant: str = "sdu_aaai21_ai", token_separator: str = " "
    ) -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        if not token_separator:
            raise ValueError("token_separator must not be empty")
        self.dataset_variant = dataset_variant
        self.token_separator = token_separator

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        path = _require_path(resource)
        try:
            with path.open(encoding="utf-8") as stream:
                raw: object = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CorpusAdapterError(
                f"Unable to parse SDU source {path}: {error}"
            ) from error
        if not isinstance(raw, list):
            raise CorpusAdapterError("SDU source must be a JSON array")
        result: list[ParsedSourceRecord] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                diagnostics.add(
                    "error",
                    "SDU_ROW_INVALID",
                    "Expected an object",
                    action="dropped",
                    record_id=str(index),
                )
                continue
            result.append(
                _sdu_record(
                    item, str(index), self.dataset_variant, self.token_separator
                )
            )
        return result

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        record = map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )
        note = "reconstructed character offsets from token sequence"
        return replace(
            record,
            gold_annotations=tuple(
                replace(
                    annotation,
                    provenance=replace(
                        annotation.provenance,
                        transformation_notes=(note,),
                    ),
                )
                for annotation in record.gold_annotations
                if annotation.provenance is not None
            ),
        )


class SDUAcronymDisambiguationAdapter:
    """Read SDU@AAAI-21 AD rows with an acronym index and expansion text.

    AD examples do not necessarily contain the expansion in the sentence.
    The canonical representation therefore stores the acronym span and the
    expansion as source text without inventing a long-form document offset.
    """

    def __init__(
        self, *, dataset_variant: str = "sdu_aaai21_ad", token_separator: str = " "
    ) -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        if not token_separator:
            raise ValueError("token_separator must not be empty")
        self.dataset_variant = dataset_variant
        self.token_separator = token_separator

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        raw = _load_json_array(resource, "SDU AD")
        result: list[ParsedSourceRecord] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                diagnostics.add(
                    "error",
                    "SDU_AD_ROW_INVALID",
                    "Expected an object",
                    action="dropped",
                    record_id=str(index),
                )
                continue
            result.append(
                _sdu_disambiguation_record(
                    item, str(index), self.dataset_variant, self.token_separator
                )
            )
        return result

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        record = map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )
        note = "source expansion has no document span; preserved as text"
        return replace(
            record,
            gold_annotations=tuple(
                replace(
                    annotation,
                    provenance=replace(
                        annotation.provenance,
                        transformation_notes=(note,),
                    ),
                )
                for annotation in record.gold_annotations
                if annotation.provenance is not None
            ),
        )


class SDUAcronymExtractionAdapter:
    """Read SDU@AAAI-22 AE JSON with independent half-open span lists.

    The source stores acronym and long-form annotations as separate lists; it
    does not define a pairing between the two lists.  Each source span is
    therefore represented as its own canonical definition, with only the
    corresponding form populated.  No pairing is inferred from list order.
    """

    def __init__(self, *, dataset_variant: str = "sdu_aaai22_ae") -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        self.dataset_variant = dataset_variant

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "2"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        raw = _load_json_array(resource, "SDU AE")
        result: list[ParsedSourceRecord] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                diagnostics.add(
                    "error",
                    "SDU_AE_ROW_INVALID",
                    "Expected an object",
                    action="dropped",
                    record_id=str(index),
                )
                continue
            try:
                result.append(
                    _sdu_extraction_record(item, str(index), self.dataset_variant)
                )
            except CorpusAdapterError as error:
                diagnostics.add(
                    "error",
                    "SDU_AE_ROW_INVALID",
                    str(error),
                    action="dropped",
                    record_id=_source_identifier(item, str(index)),
                )
        return result

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        record = map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )
        note = "source acronym and long-form spans preserved independently"
        return replace(
            record,
            gold_annotations=tuple(
                replace(
                    annotation,
                    provenance=replace(
                        annotation.provenance,
                        transformation_notes=(note,),
                    ),
                )
                for annotation in record.gold_annotations
                if annotation.provenance is not None
            ),
        )


class DelimitedPairCorpusAdapter:
    """Read explicit tab-separated pair rows used by corrected corpora.

    Rows are ``record_id<TAB>document_text<TAB>short_start<TAB>short_end<TAB>
    long_start<TAB>long_end``.  A two-column ``short<TAB>long`` row is accepted
    only when ``document_template`` is configured; this makes reconstruction a
    visible configuration choice rather than an implicit scientific decision.
    """

    def __init__(
        self, *, dataset_variant: str, document_template: str | None = None
    ) -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        self.dataset_variant = dataset_variant
        self.document_template = document_template

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        path = _require_path(resource)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            raise CorpusAdapterError(
                f"Unable to parse pair source {path}: {error}"
            ) from error
        records: list[ParsedSourceRecord] = []
        for number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            try:
                records.append(
                    _pair_record(
                        fields, number, self.dataset_variant, self.document_template
                    )
                )
            except ValueError as error:
                diagnostics.add(
                    "error",
                    "PAIR_ROW_INVALID",
                    str(error),
                    action="dropped",
                    record_id=str(number),
                    location=f"line {number}",
                )
        return records

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        record = map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
        )
        if self.document_template is None:
            return record
        note = "reconstructed document text from configured document_template"
        return replace(
            record,
            gold_annotations=tuple(
                replace(
                    annotation,
                    provenance=replace(
                        annotation.provenance,
                        transformation_notes=(note,),
                    ),
                )
                for annotation in record.gold_annotations
                if annotation.provenance is not None
            ),
        )


def _load_json_array(resource: SourceResource, label: str) -> list[object]:
    path = _require_path(resource)
    try:
        with path.open(encoding="utf-8") as stream:
            raw: object = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CorpusAdapterError(
            f"Unable to parse {label} source {path}: {error}"
        ) from error
    if not isinstance(raw, list):
        raise CorpusAdapterError(f"{label} source must be a JSON array")
    return raw


def _sdu_disambiguation_record(
    item: Mapping[str, Any], fallback: str, variant: str, separator: str
) -> ParsedSourceRecord:
    tokens = item.get("tokens")
    acronym = item.get("acronym")
    expansion = item.get("expansion")
    if (
        not isinstance(tokens, list)
        or any(not isinstance(token, str) for token in tokens)
        or isinstance(acronym, bool)
        or not isinstance(acronym, int)
        or not 0 <= acronym < len(tokens)
        or not isinstance(expansion, str)
        or not expansion.strip()
    ):
        raise CorpusAdapterError(
            "SDU AD row requires string tokens, a valid acronym index, and expansion"
        )
    text = separator.join(tokens)
    short_start = _token_start(tokens, acronym, separator)
    annotation = ParsedSourceAnnotation(
        "sdu-ad-0",
        SourceTextSpan(
            short_start, short_start + len(tokens[acronym]), tokens[acronym]
        ),
        SourceTextSpan(text=expansion),
    )
    identifier = str(item.get("id") or fallback)
    return ParsedSourceRecord(identifier, identifier, text, (annotation,), variant)


def _sdu_extraction_record(
    item: Mapping[str, Any], fallback: str, variant: str
) -> ParsedSourceRecord:
    identifier = item.get("ID")
    text = item.get("text")
    acronyms = item.get("acronyms", [])
    long_forms = item.get("long-forms", item.get("long_forms", []))
    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or not isinstance(text, str)
        or not isinstance(acronyms, list)
        or not isinstance(long_forms, list)
    ):
        raise CorpusAdapterError(
            "SDU AE row requires a non-empty ID, text, and acronym/long-form arrays"
        )
    annotations = tuple(
        [
            ParsedSourceAnnotation(
                f"sdu-ae-short-{index}",
                _half_open_source_span(acronym, text, "acronym"),
                None,
            )
            for index, acronym in enumerate(acronyms)
        ]
        + [
            ParsedSourceAnnotation(
                f"sdu-ae-long-{index}",
                None,
                _half_open_source_span(long_form, text, "long-form"),
            )
            for index, long_form in enumerate(long_forms)
        ]
    )
    source_identifier = str(identifier)
    return ParsedSourceRecord(
        source_identifier, source_identifier, text, annotations, variant
    )


def _token_start(tokens: list[object], index: int, separator: str) -> int:
    return sum(
        len(token) + len(separator)
        for token in tokens[:index]
        if isinstance(token, str)
    )


def _half_open_source_span(value: object, text: str, label: str) -> SourceTextSpan:
    if (
        not isinstance(value, list | tuple)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise CorpusAdapterError(f"SDU AE {label} range must contain two integers")
    start, end = value
    assert isinstance(start, int) and isinstance(end, int)
    if start < 0 or end < start or end > len(text):
        raise CorpusAdapterError(f"SDU AE {label} range is outside document text")
    return SourceTextSpan(start, end, text[start:end])


def _source_identifier(item: Mapping[str, Any], fallback: str) -> str:
    """Return the official uppercase SDU AE identifier for diagnostics."""

    value = item.get("ID")
    if value is not None and str(value).strip():
        return str(value)
    return fallback


def _require_path(resource: SourceResource) -> Path:
    if resource.location is None:
        raise CorpusAdapterError("Historical corpus adapters require source.location")
    if not resource.location.is_file():
        raise CorpusAdapterError(f"Source file does not exist: {resource.location}")
    return resource.location


def _parse_bioc_xml(
    path: Path,
    variant: str,
    diagnostics: DiagnosticsCollector,
    *,
    pairing_policy: BioCPairingPolicy,
    text_policy: BioCTextPolicy,
    location_policy: BioCLocationPolicy,
) -> tuple[ParsedSourceRecord, ...]:
    root = ET.parse(path).getroot()
    records: list[ParsedSourceRecord] = []
    for document in root.iter("document"):
        passages = list(document.findall("passage"))
        document_id = document.findtext("id") or f"{variant}-{len(records)}"
        text, overlaps = _render_bioc_passages(
            tuple(
                (
                    _integer_text(passage.findtext("offset"), default=0),
                    passage.findtext("text") or "",
                )
                for passage in passages
            )
        )
        for location, message in overlaps:
            diagnostics.add(
                "warning",
                "BIOC_PASSAGE_TEXT_OVERLAP",
                message,
                record_id=document_id,
                location=location,
            )
        annotations = _bioc_xml_annotations(
            document,
            text,
            variant,
            document_id,
            diagnostics,
            pairing_policy=pairing_policy,
            text_policy=text_policy,
            location_policy=location_policy,
        )
        transformations: tuple[str, ...] = ()
        if text_policy == "overlay_annotation_text":
            text, changed = _overlay_annotation_text(text, annotations)
            if changed:
                transformations = ("bioc_annotation_text_overlay: equal-length text",)
        records.append(
            ParsedSourceRecord(
                document_id,
                document_id,
                text,
                annotations,
                variant,
                transformations,
            )
        )
    diagnostics.add(
        "info",
        "BIOC_SOURCE_PARSED",
        f"Parsed {len(records)} BioC documents",
        record_id=variant,
        location="source",
    )
    return tuple(records)


def _parse_bioc_json(
    path: Path,
    variant: str,
    diagnostics: DiagnosticsCollector,
    *,
    pairing_policy: BioCPairingPolicy,
    text_policy: BioCTextPolicy,
    location_policy: BioCLocationPolicy,
) -> tuple[ParsedSourceRecord, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    documents = raw.get("documents", []) if isinstance(raw, dict) else raw
    if not isinstance(documents, list):
        raise CorpusAdapterError("BioC JSON must contain a documents array")
    records: list[ParsedSourceRecord] = []
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise CorpusAdapterError(f"BioC document {index} must be an object")
        passages = document.get("passages", [])
        if not isinstance(passages, list):
            raise CorpusAdapterError(f"BioC document {index} passages must be an array")
        document_id = str(document.get("id") or f"{variant}-{index}")
        text, annotations, transformations = _bioc_json_document(
            passages,
            variant,
            document_id,
            diagnostics,
            pairing_policy=pairing_policy,
            text_policy=text_policy,
            location_policy=location_policy,
        )
        records.append(
            ParsedSourceRecord(
                document_id,
                document_id,
                text,
                annotations,
                variant,
                transformations,
            )
        )
    diagnostics.add(
        "info",
        "BIOC_SOURCE_PARSED",
        f"Parsed {len(records)} BioC documents",
        record_id=variant,
        location="source",
    )
    return tuple(records)


def _bioc_xml_annotations(
    document: ET.Element,
    text: str,
    variant: str,
    document_id: str,
    diagnostics: DiagnosticsCollector,
    *,
    pairing_policy: BioCPairingPolicy,
    text_policy: BioCTextPolicy,
    location_policy: BioCLocationPolicy,
) -> tuple[ParsedSourceAnnotation, ...]:
    del text_policy  # XML annotation text is never an input-text repair by default.
    entities: list[_BioCEntity] = []
    for ordinal, annotation in enumerate(document.iter("annotation")):
        source_identifier = annotation.get("id")
        identifier = source_identifier or f"__missing_annotation_id_{ordinal}"
        if source_identifier is None:
            diagnostics.add(
                "warning",
                "BIOC_ANNOTATION_ID_MISSING",
                "Annotation has no source identifier; assigned a scoped synthetic ID",
                action="repaired",
                record_id=document_id,
                annotation_id=identifier,
            )
        span = _bioc_xml_span(
            annotation,
            document_id,
            diagnostics,
            location_policy=location_policy,
        )
        if span is None:
            continue
        entities.append(
            _BioCEntity(
                identifier,
                identifier,
                span,
                _annotation_role(source_identifier, _infons_xml(annotation)),
                ordinal,
            )
        )
        _diagnose_annotation_text(
            span,
            annotation.findtext("text"),
            text,
            diagnostics,
            document_id,
            identifier,
        )
    return _pair_entities(
        entities,
        _relations_xml(document, document_id, diagnostics),
        variant,
        document_id,
        diagnostics,
        relation_nodes_present=any(True for _ in document.iter("relation")),
        pairing_policy=pairing_policy,
    )


def _bioc_json_document(
    passages: list[object],
    variant: str,
    document_id: str,
    diagnostics: DiagnosticsCollector,
    *,
    pairing_policy: BioCPairingPolicy,
    text_policy: BioCTextPolicy,
    location_policy: BioCLocationPolicy,
) -> tuple[str, tuple[ParsedSourceAnnotation, ...], tuple[str, ...]]:
    entities: list[_BioCEntity] = []
    all_relations: list[tuple[str, str]] = []
    passage_values: list[tuple[int, str]] = []
    transformations: list[str] = []
    relation_nodes_present = False
    for passage_index, passage in enumerate(passages):
        if not isinstance(passage, dict):
            raise CorpusAdapterError("BioC passage must be an object")
        passage_offset = int(passage.get("offset", 0))
        passage_text = passage.get("text", "")
        if isinstance(passage_text, str):
            passage_values.append((passage_offset, passage_text))
        annotations = passage.get("annotations", [])
        if not isinstance(annotations, list):
            raise CorpusAdapterError("BioC passage annotations must be an array")
        for annotation_index, annotation in enumerate(annotations):
            if not isinstance(annotation, dict):
                diagnostics.add(
                    "warning",
                    "BIOC_ANNOTATION_INVALID",
                    "BioC annotation must be an object",
                    action="dropped",
                    record_id=document_id,
                    location=f"passages[{passage_index}].annotations[{annotation_index}]",
                )
                continue
            source_identifier_value = annotation.get("id")
            identifier = str(
                source_identifier_value or f"__missing_annotation_id_{len(entities)}"
            )
            if source_identifier_value is None:
                diagnostics.add(
                    "warning",
                    "BIOC_ANNOTATION_ID_MISSING",
                    (
                        "Annotation has no source identifier; assigned a scoped "
                        "synthetic ID"
                    ),
                    action="repaired",
                    record_id=document_id,
                    annotation_id=identifier,
                )
            locations = annotation.get("locations", [])
            location = _bioc_json_location(
                locations,
                identifier,
                document_id,
                diagnostics,
                location_policy=location_policy,
            )
            if location is None:
                continue
            start, length = location
            value = annotation.get("text")
            span = SourceTextSpan(
                start,
                start + length,
                value if isinstance(value, str) else None,
            )
            infons = annotation.get("infons", {})
            entities.append(
                _BioCEntity(
                    identifier,
                    identifier,
                    span,
                    _annotation_role(
                        str(source_identifier_value)
                        if source_identifier_value is not None
                        else None,
                        infons if isinstance(infons, dict) else {},
                    ),
                    len(entities),
                )
            )
        relations = passage.get("relations", [])
        if not isinstance(relations, list):
            raise CorpusAdapterError("BioC passage relations must be an array")
        relation_nodes_present = relation_nodes_present or bool(relations)
        all_relations.extend(
            _relations_json(relations, document_id, diagnostics, passage_index)
        )
    text, overlaps = _render_bioc_passages(tuple(passage_values))
    for overlap_location, message in overlaps:
        diagnostics.add(
            "warning",
            "BIOC_PASSAGE_TEXT_OVERLAP",
            message,
            record_id=document_id,
            location=overlap_location,
        )
    for entity in entities:
        _diagnose_annotation_text(
            entity.span,
            entity.span.text,
            text,
            diagnostics,
            document_id,
            entity.source_identifier,
        )
    if text_policy == "overlay_annotation_text":
        chars = list(text)
        changed = False
        for entity in entities:
            if entity.span.text is not None:
                assert entity.span.start is not None and entity.span.end is not None
                if len(entity.span.text) == entity.span.end - entity.span.start:
                    chars[entity.span.start : entity.span.end] = entity.span.text
                    changed = True
        text = "".join(chars)
        if changed:
            transformations.append("bioc_annotation_text_overlay: equal-length text")
    return (
        text,
        _pair_entities(
            entities,
            all_relations,
            variant,
            document_id,
            diagnostics,
            relation_nodes_present=relation_nodes_present,
            pairing_policy=pairing_policy,
        ),
        tuple(transformations),
    )


def _infons_xml(annotation: ET.Element) -> dict[str, str]:
    return {
        infon.get("key", "").lower(): (infon.text or "")
        for infon in annotation.findall("infon")
    }


def _relations_xml(
    document: ET.Element, document_id: str, diagnostics: DiagnosticsCollector
) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for index, relation in enumerate(document.iter("relation")):
        nodes = relation.findall("node")
        ids = _relation_ids(
            tuple(
                (
                    _role(node.get("role", "")),
                    node.get("refid", ""),
                )
                for node in nodes
            ),
            document_id,
            diagnostics,
            f"relations[{index}]",
        )
        if ids is not None:
            result.append(ids)
    return result


def _relations_json(
    relations: list[object],
    document_id: str,
    diagnostics: DiagnosticsCollector,
    passage_index: int,
) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for relation_index, relation in enumerate(relations):
        if not isinstance(relation, dict):
            diagnostics.add(
                "warning",
                "BIOC_RELATION_INVALID",
                "BioC relation must be an object",
                action="dropped",
                record_id=document_id,
                location=f"passages[{passage_index}].relations[{relation_index}]",
            )
            continue
        nodes = relation.get("nodes", [])
        if not isinstance(nodes, list):
            diagnostics.add(
                "warning",
                "BIOC_RELATION_INVALID",
                "BioC relation nodes must be an array",
                action="dropped",
                record_id=document_id,
                location=f"passages[{passage_index}].relations[{relation_index}]",
            )
            continue
        parsed_nodes: list[tuple[str, str]] = []
        for node in nodes:
            if isinstance(node, dict):
                parsed_nodes.append(
                    (_role(str(node.get("role", ""))), str(node.get("refid", "")))
                )
        parsed = _relation_ids(
            tuple(parsed_nodes),
            document_id,
            diagnostics,
            f"passages[{passage_index}].relations[{relation_index}]",
        )
        if parsed is not None:
            result.append(parsed)
    return result


def _relation_ids(
    nodes: tuple[tuple[str, str], ...],
    document_id: str,
    diagnostics: DiagnosticsCollector,
    location: str,
) -> tuple[str, str] | None:
    shorts = [refid for role, refid in nodes if role == "short" and refid]
    longs = [refid for role, refid in nodes if role == "long" and refid]
    if len(shorts) == 1 and len(longs) == 1:
        return shorts[0], longs[0]
    diagnostics.add(
        "warning",
        "BIOC_RELATION_INVALID",
        "BioC relation must contain exactly one short and one long endpoint",
        action="dropped",
        record_id=document_id,
        location=location,
        details=(
            ("short_endpoints", str(len(shorts))),
            ("long_endpoints", str(len(longs))),
        ),
    )
    return None


def _pair_entities(
    entities: list[_BioCEntity],
    relations: Iterable[tuple[str, str]],
    variant: str,
    document_id: str,
    diagnostics: DiagnosticsCollector,
    *,
    relation_nodes_present: bool,
    pairing_policy: BioCPairingPolicy,
) -> tuple[ParsedSourceAnnotation, ...]:
    relations_list = list(relations)
    by_id: dict[str, list[_BioCEntity]] = {}
    for entity in entities:
        by_id.setdefault(entity.identifier, []).append(entity)
    for identifier, matches in by_id.items():
        if len(matches) > 1:
            diagnostics.add(
                "warning",
                "BIOC_DUPLICATE_ANNOTATION_ID",
                (
                    f"Source annotation ID {identifier!r} occurs more than once; "
                    "relation lookup is ambiguous"
                ),
                record_id=document_id,
                annotation_id=identifier,
                details=(("occurrences", str(len(matches))),),
            )

    output: list[ParsedSourceAnnotation] = []
    referenced: set[int] = set()
    if relations_list:
        for index, (short_id, long_id) in enumerate(relations_list):
            short_matches = by_id.get(short_id, [])
            long_matches = by_id.get(long_id, [])
            if len(short_matches) != 1 or len(long_matches) != 1:
                diagnostics.add(
                    "warning",
                    "BIOC_RELATION_ENDPOINT_UNRESOLVED",
                    (
                        "Relation endpoint is missing or has a duplicate source ID; "
                        "relation not paired"
                    ),
                    action="dropped",
                    record_id=document_id,
                    details=(
                        ("short_refid", short_id),
                        ("long_refid", long_id),
                        ("short_matches", str(len(short_matches))),
                        ("long_matches", str(len(long_matches))),
                    ),
                )
                continue
            short_entity, long_entity = short_matches[0], long_matches[0]
            referenced.update((short_entity.ordinal, long_entity.ordinal))
            output.append(
                ParsedSourceAnnotation(
                    f"{variant}-{index}", short_entity.span, long_entity.span
                )
            )
    elif not relation_nodes_present and pairing_policy == "relations_or_order_fallback":
        shorts = [entity for entity in entities if entity.role == "short"]
        longs = [entity for entity in entities if entity.role == "long"]
        pair_count = min(len(shorts), len(longs))
        if shorts or longs:
            diagnostics.add(
                "info",
                "BIOC_ORDER_FALLBACK_USED",
                (
                    "No BioC relation nodes were present; paired source entities "
                    "by order under the named historical policy"
                ),
                record_id=document_id,
                details=(
                    ("short_entities", str(len(shorts))),
                    ("long_entities", str(len(longs))),
                    ("paired_entities", str(pair_count)),
                ),
            )
        for index in range(pair_count):
            short_entity, long_entity = shorts[index], longs[index]
            referenced.update((short_entity.ordinal, long_entity.ordinal))
            output.append(
                ParsedSourceAnnotation(
                    f"{variant}-fallback-{index}",
                    short_entity.span,
                    long_entity.span,
                )
            )
    elif entities and not relation_nodes_present:
        diagnostics.add(
            "info",
            "BIOC_RELATIONS_ABSENT",
            (
                "No BioC relation nodes were present; source entities were "
                "retained independently"
            ),
            record_id=document_id,
        )

    for entity in entities:
        if entity.ordinal in referenced:
            continue
        if entity.role not in {"short", "long"}:
            diagnostics.add(
                "warning",
                "BIOC_UNPAIRED_ENTITY",
                "Source annotation was not paired and its role is not scoreable",
                action="dropped",
                record_id=document_id,
                annotation_id=entity.source_identifier,
            )
            continue
        diagnostics.add(
            "warning",
            "BIOC_UNPAIRED_ENTITY",
            (
                "Source short/long annotation has no paired counterpart; retained "
                "as a partial annotation"
            ),
            record_id=document_id,
            annotation_id=entity.source_identifier,
        )
        output.append(
            ParsedSourceAnnotation(
                f"{variant}-unpaired-{entity.ordinal}",
                entity.span if entity.role == "short" else None,
                entity.span if entity.role == "long" else None,
            )
        )
    return tuple(output)


def _role(value: str) -> str:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    if normalized in {"short", "short form", "shortform", "abbreviation", "sf"}:
        return "short"
    if normalized in {"long", "long form", "longform", "expansion", "lf"}:
        return "long"
    return normalized


def _annotation_role(identifier: str | None, infons: Mapping[str, object]) -> str:
    """Resolve a source entity role without treating arbitrary IDs as proof."""

    raw_type = infons.get("type", "")
    role = _role(str(raw_type))
    if role in {"short", "long"}:
        return role
    if identifier is not None:
        prefix = identifier.upper()
        if prefix.startswith(("SF", "LF")):
            return "short" if prefix.startswith("SF") else "long"
    return role


def _bioc_xml_span(
    annotation: ET.Element,
    document_id: str,
    diagnostics: DiagnosticsCollector,
    *,
    location_policy: BioCLocationPolicy,
) -> SourceTextSpan | None:
    locations = annotation.findall("location")
    identifier = annotation.get("id")
    if not locations:
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_MISSING",
            "BioC annotation has no location and was not mapped to a canonical span",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    if len(locations) > 1:
        diagnostics.add(
            "warning",
            "BIOC_MULTIPLE_LOCATIONS",
            (
                "BioC annotation has discontinuous locations; the configured "
                "location policy was applied"
            ),
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
            details=(
                ("location_count", str(len(locations))),
                ("policy", location_policy),
                (
                    "locations",
                    ";".join(
                        f"{item.get('offset', '')}:{item.get('length', '')}"
                        for item in locations
                    ),
                ),
            ),
        )
        if location_policy == "reject_discontinuous":
            return None
    location = locations[0]
    try:
        start = int(location.get("offset", "0"))
        length = int(location.get("length", "0"))
    except (TypeError, ValueError) as error:
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_INVALID",
            f"BioC annotation location is not integer-valued: {error}",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    if start < 0 or length < 0:
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_INVALID",
            "BioC annotation location must have non-negative offset and length",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    return SourceTextSpan(start, start + length, annotation.findtext("text"))


def _bioc_json_location(
    locations: object,
    identifier: str,
    document_id: str,
    diagnostics: DiagnosticsCollector,
    *,
    location_policy: BioCLocationPolicy,
) -> tuple[int, int] | None:
    if not isinstance(locations, list) or not locations:
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_MISSING",
            "BioC annotation has no location and was not mapped to a canonical span",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    if len(locations) > 1:
        diagnostics.add(
            "warning",
            "BIOC_MULTIPLE_LOCATIONS",
            (
                "BioC annotation has discontinuous locations; the configured "
                "location policy was applied"
            ),
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
            details=(
                ("location_count", str(len(locations))),
                ("policy", location_policy),
            ),
        )
        if location_policy == "reject_discontinuous":
            return None
    location = locations[0]
    if not isinstance(location, dict):
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_INVALID",
            "BioC annotation location must be an object",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    offset, length = location.get("offset", 0), location.get("length", 0)
    if (
        isinstance(offset, bool)
        or isinstance(length, bool)
        or not isinstance(offset, int)
        or not isinstance(length, int)
        or offset < 0
        or length < 0
    ):
        diagnostics.add(
            "warning",
            "BIOC_ANNOTATION_LOCATION_INVALID",
            "BioC annotation location must have non-negative integer offset and length",
            action="dropped",
            record_id=document_id,
            annotation_id=identifier,
        )
        return None
    return offset, length


def _diagnose_annotation_text(
    span: SourceTextSpan,
    annotation_text: str | None,
    document_text: str,
    diagnostics: DiagnosticsCollector,
    document_id: str,
    identifier: str | None,
) -> None:
    if annotation_text is None or span.start is None or span.end is None:
        return
    observed = document_text[span.start : span.end]
    if observed == annotation_text:
        return
    diagnostics.add(
        "warning",
        "BIOC_ANNOTATION_TEXT_MISMATCH",
        (
            "BioC annotation text differs from source document text; source text "
            "was preserved"
        ),
        record_id=document_id,
        annotation_id=identifier,
        details=(
            ("source_text", annotation_text),
            ("document_text", observed),
        ),
    )


def _render_bioc_passages(
    passages: tuple[tuple[int, str], ...],
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Render absolute-offset BioC passages without annotation-text overlay."""

    if not passages:
        return "", ()
    max_end = max(offset + len(value) for offset, value in passages)
    if any(offset < 0 for offset, _ in passages):
        raise CorpusAdapterError("BioC passage offsets must be non-negative")
    chars = [" "] * max_end
    occupied = [False] * max_end
    overlaps: list[tuple[str, str]] = []
    for passage_index, (offset, value) in enumerate(passages):
        for relative, character in enumerate(value):
            position = offset + relative
            existing = chars[position]
            if occupied[position] and existing != character:
                overlaps.append(
                    (
                        f"passages[{passage_index}]",
                        (
                            "BioC passages overlap with conflicting source text; "
                            "earlier text was preserved"
                        ),
                    )
                )
                continue
            chars[position] = character
            occupied[position] = True
    return "".join(chars), tuple(overlaps)


def _overlay_annotation_text(
    text: str, annotations: Iterable[ParsedSourceAnnotation]
) -> tuple[str, bool]:
    """Apply only equal-length annotation text overlays as a named repair."""

    chars = list(text)
    changed = False
    for annotation in annotations:
        for span, value in (
            (
                annotation.short_form,
                annotation.short_form.text if annotation.short_form else None,
            ),
            (
                annotation.long_form,
                annotation.long_form.text if annotation.long_form else None,
            ),
        ):
            if span is None or value is None or span.start is None or span.end is None:
                continue
            if len(value) != span.end - span.start:
                continue
            chars[span.start : span.end] = value
            changed = True
    return "".join(chars), changed


def _integer_text(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as error:
        raise CorpusAdapterError(
            f"BioC passage offset must be an integer: {value!r}"
        ) from error


def _sdu_record(
    item: Mapping[str, Any], fallback: str, variant: str, separator: str
) -> ParsedSourceRecord:
    tokens = item.get("tokens")
    labels = item.get("labels")
    if (
        not isinstance(tokens, list)
        or not isinstance(labels, list)
        or len(tokens) != len(labels)
        or any(
            not isinstance(token, str) or not isinstance(label, str)
            for token, label in zip(tokens, labels, strict=False)
        )
    ):
        raise CorpusAdapterError(
            "SDU row requires equal-length string tokens and labels"
        )
    text = separator.join(tokens)
    spans: dict[str, SourceTextSpan] = {}
    active: dict[str, int] = {}
    offset = 0
    for token, label in zip(tokens, labels, strict=True):
        token_start = offset
        previous_end = max(0, token_start - len(separator))
        kind = label.split("-", 1)[-1].lower() if "-" in label else ""
        if label.startswith("B-") and kind in {"short", "long"}:
            _finish_sdu_span(spans, active, kind, previous_end, text)
            active[kind] = token_start
        elif kind not in {"short", "long"} or not label.startswith("I-"):
            for previous in tuple(active):
                _finish_sdu_span(spans, active, previous, previous_end, text)
        offset += len(token)
        if offset < len(text):
            offset += len(separator)
    for kind in tuple(active):
        _finish_sdu_span(spans, active, kind, len(text), text)
    annotation = ParsedSourceAnnotation("sdu-0", spans.get("short"), spans.get("long"))
    return ParsedSourceRecord(
        str(item.get("id") or fallback),
        str(item.get("id") or fallback),
        text,
        (annotation,),
        variant,
    )


def _finish_sdu_span(
    spans: dict[str, SourceTextSpan],
    active: dict[str, int],
    kind: str,
    end: int,
    text: str,
) -> None:
    start = active.pop(kind, None)
    if start is not None:
        spans[kind] = SourceTextSpan(start, end, text[start:end])


def _pair_record(
    fields: list[str], number: int, variant: str, template: str | None
) -> ParsedSourceRecord:
    if len(fields) == 6:
        record_id, text, short_start, short_end, long_start, long_end = fields
        return ParsedSourceRecord(
            record_id or str(number),
            record_id or str(number),
            text,
            (
                ParsedSourceAnnotation(
                    str(number),
                    SourceTextSpan(
                        int(short_start),
                        int(short_end),
                        text[int(short_start) : int(short_end)],
                    ),
                    SourceTextSpan(
                        int(long_start),
                        int(long_end),
                        text[int(long_start) : int(long_end)],
                    ),
                ),
            ),
            variant,
        )
    if len(fields) == 2 and template is not None:
        short, long = fields
        text = template.format(short=short, long=long)
        short_position, long_position = text.index(short), text.index(long)
        return ParsedSourceRecord(
            str(number),
            str(number),
            text,
            (
                ParsedSourceAnnotation(
                    str(number),
                    SourceTextSpan(short_position, short_position + len(short), short),
                    SourceTextSpan(long_position, long_position + len(long), long),
                ),
            ),
            variant,
        )
    raise ValueError("expected 6 fields, or 2 fields with document_template")


__all__ = [
    "BioCCorpusAdapter",
    "DelimitedPairCorpusAdapter",
    "SDUAcronymDisambiguationAdapter",
    "SDUAcronymExtractionAdapter",
    "SDUAcronymIdentificationAdapter",
]
