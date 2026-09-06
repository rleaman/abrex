"""Adapters for the user-supplied historical abbreviation corpora.

The adapters deliberately do not download data.  BioC sources are parsed as
documents, passages, annotations, and relations; SDU JSON sources are parsed
as token-level BIO labels.  The latter necessarily reconstructs character
offsets from tokens and records that fact in provenance.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from abrex.corpora.base import (
    CorpusAdapterError,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    map_source_record,
)
from abrex.corpora.diagnostics import DiagnosticsCollector
from abrex.domain import CorpusRecord, SourceTextSpan


class BioCCorpusAdapter:
    """Read BioC XML or JSON with abbreviation relation annotations."""

    def __init__(self, *, dataset_variant: str = "bioc") -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        self.dataset_variant = dataset_variant

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "1"

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        path = _require_path(resource)
        try:
            suffix = path.suffix.lower()
            if resource.format == "json" or suffix == ".json":
                return _parse_bioc_json(path, self.dataset_variant, diagnostics)
            return _parse_bioc_xml(path, self.dataset_variant, diagnostics)
        except (OSError, UnicodeError, ET.ParseError, json.JSONDecodeError) as error:
            raise CorpusAdapterError(
                f"Unable to parse BioC source {path}: {error}"
            ) from error

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        return map_source_record(
            source_record,
            adapter_identity=self.identity,
            adapter_version=self.version,
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
    """Read SDU@AAAI-22 AE JSON with inclusive character ranges."""

    def __init__(self, *, dataset_variant: str = "sdu_aaai22_ai") -> None:
        if not dataset_variant.strip():
            raise ValueError("dataset_variant must not be empty")
        self.dataset_variant = dataset_variant

    @property
    def identity(self) -> str:
        return self.dataset_variant

    version = "1"

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
            result.append(
                _sdu_extraction_record(item, str(index), self.dataset_variant)
            )
        return result

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        return map_source_record(
            source_record, adapter_identity=self.identity, adapter_version=self.version
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
    text = item.get("text")
    acronyms = item.get("acronyms")
    long_forms = item.get("long-forms", item.get("long_forms"))
    if (
        not isinstance(text, str)
        or not isinstance(acronyms, list)
        or not isinstance(long_forms, list)
        or len(acronyms) != len(long_forms)
    ):
        raise CorpusAdapterError(
            "SDU AE row requires text and equal-length acronym/long-form arrays"
        )
    annotations = tuple(
        ParsedSourceAnnotation(
            f"sdu-ae-{index}",
            _inclusive_source_span(acronym, text, "acronym"),
            _inclusive_source_span(long_form, text, "long-form"),
        )
        for index, (acronym, long_form) in enumerate(
            zip(acronyms, long_forms, strict=True)
        )
    )
    identifier = str(item.get("id") or fallback)
    return ParsedSourceRecord(identifier, identifier, text, annotations, variant)


def _token_start(tokens: list[object], index: int, separator: str) -> int:
    return sum(
        len(token) + len(separator)
        for token in tokens[:index]
        if isinstance(token, str)
    )


def _inclusive_source_span(value: object, text: str, label: str) -> SourceTextSpan:
    if (
        not isinstance(value, list | tuple)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise CorpusAdapterError(f"SDU AE {label} range must contain two integers")
    start, inclusive_end = value
    assert isinstance(start, int) and isinstance(inclusive_end, int)
    if start < 0 or inclusive_end < start or inclusive_end >= len(text):
        raise CorpusAdapterError(f"SDU AE {label} range is outside document text")
    end = inclusive_end + 1
    return SourceTextSpan(start, end, text[start:end])


def _require_path(resource: SourceResource) -> Path:
    if resource.location is None:
        raise CorpusAdapterError("Historical corpus adapters require source.location")
    if not resource.location.is_file():
        raise CorpusAdapterError(f"Source file does not exist: {resource.location}")
    return resource.location


def _parse_bioc_xml(
    path: Path, variant: str, diagnostics: DiagnosticsCollector
) -> tuple[ParsedSourceRecord, ...]:
    root = ET.parse(path).getroot()
    records: list[ParsedSourceRecord] = []
    for document in root.iter("document"):
        passages = list(document.findall("passage"))
        text = "".join((passage.findtext("text") or "") for passage in passages)
        # BioC passage offsets are absolute; preserve them and use the full
        # document text when it is available.
        if passages and any(p.find("offset") is not None for p in passages):
            end = max(
                int(p.findtext("offset") or "0") + len(p.findtext("text") or "")
                for p in passages
            )
            chars = [" "] * end
            for passage in passages:
                offset = int(passage.findtext("offset") or "0")
                value = passage.findtext("text") or ""
                chars[offset : offset + len(value)] = value
            text = "".join(chars)
        annotations = _bioc_xml_annotations(document, text, variant)
        document_id = document.findtext("id") or f"{variant}-{len(records)}"
        records.append(
            ParsedSourceRecord(document_id, document_id, text, annotations, variant)
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
    path: Path, variant: str, diagnostics: DiagnosticsCollector
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
        text, annotations = _bioc_json_document(passages, variant)
        document_id = str(document.get("id") or f"{variant}-{index}")
        records.append(
            ParsedSourceRecord(document_id, document_id, text, annotations, variant)
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
    document: ET.Element, text: str, variant: str
) -> tuple[ParsedSourceAnnotation, ...]:
    entities: dict[str, SourceTextSpan] = {}
    roles: dict[str, str] = {}
    for annotation in document.iter("annotation"):
        identifier = annotation.get("id") or str(len(entities))
        location = annotation.find("location")
        if location is None:
            continue
        start, length = (
            int(location.get("offset", "0")),
            int(location.get("length", "0")),
        )
        entities[identifier] = SourceTextSpan(
            start, start + length, annotation.findtext("text")
        )
        roles[identifier] = _role(_infons_xml(annotation).get("type", ""))
    pairs = _relations_xml(document)
    return _pair_entities(entities, roles, pairs, variant)


def _bioc_json_document(
    passages: list[object], variant: str
) -> tuple[str, tuple[ParsedSourceAnnotation, ...]]:
    entities: dict[str, SourceTextSpan] = {}
    roles: dict[str, str] = {}
    all_relations: list[tuple[str, str]] = []
    max_end = 0
    passage_values: list[tuple[int, str]] = []
    for passage in passages:
        if not isinstance(passage, dict):
            raise CorpusAdapterError("BioC passage must be an object")
        passage_offset = int(passage.get("offset", 0))
        passage_text = passage.get("text", "")
        if isinstance(passage_text, str):
            passage_values.append((passage_offset, passage_text))
            max_end = max(max_end, passage_offset + len(passage_text))
        for annotation in passage.get("annotations", []):
            if not isinstance(annotation, dict):
                continue
            identifier = str(annotation.get("id") or len(entities))
            locations = annotation.get("locations", [])
            location = locations[0] if isinstance(locations, list) and locations else {}
            if not isinstance(location, dict):
                continue
            start, length = (
                int(location.get("offset", 0)),
                int(location.get("length", 0)),
            )
            value = annotation.get("text")
            entities[identifier] = SourceTextSpan(
                start, start + length, value if isinstance(value, str) else None
            )
            infons = annotation.get("infons", {})
            roles[identifier] = (
                _role(str(infons.get("type", ""))) if isinstance(infons, dict) else ""
            )
            max_end = max(max_end, start + length)
        for relation in passage.get("relations", []):
            if isinstance(relation, dict):
                nodes = relation.get("nodes", [])
                if isinstance(nodes, list):
                    role_ids = {
                        _role(str(node.get("role", ""))): str(node.get("refid"))
                        for node in nodes
                        if isinstance(node, dict)
                    }
                    if role_ids.get("short") and role_ids.get("long"):
                        all_relations.append((role_ids["short"], role_ids["long"]))
    chars = [" "] * max_end
    for start, value in passage_values:
        chars[start : start + len(value)] = value
    for span in entities.values():
        if span.text is not None and span.start is not None and span.end is not None:
            chars[span.start : span.end] = span.text
    return "".join(chars), _pair_entities(entities, roles, all_relations, variant)


def _infons_xml(annotation: ET.Element) -> dict[str, str]:
    return {
        infon.get("key", "").lower(): (infon.text or "")
        for infon in annotation.findall("infon")
    }


def _relations_xml(document: ET.Element) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for relation in document.iter("relation"):
        nodes = relation.findall("node")
        ids = {_role(node.get("role", "")): node.get("refid", "") for node in nodes}
        if ids.get("short") and ids.get("long"):
            result.append((ids["short"], ids["long"]))
    return result


def _pair_entities(
    entities: Mapping[str, SourceTextSpan],
    roles: Mapping[str, str],
    relations: Iterable[tuple[str, str]],
    variant: str,
) -> tuple[ParsedSourceAnnotation, ...]:
    pairs = list(relations)
    if not pairs:
        shorts = [key for key, role in roles.items() if role == "short"]
        longs = [key for key, role in roles.items() if role == "long"]
        pairs = list(zip(shorts, longs, strict=False))
    return tuple(
        ParsedSourceAnnotation(
            f"{variant}-{index}", entities.get(short), entities.get(long)
        )
        for index, (short, long) in enumerate(pairs)
        if short in entities and long in entities
    )


def _role(value: str) -> str:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    if normalized in {"short", "short form", "shortform", "abbreviation", "sf"}:
        return "short"
    if normalized in {"long", "long form", "longform", "expansion", "lf"}:
        return "long"
    return normalized


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
