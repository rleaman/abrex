"""Adapter and exporter for CellLiteraturePipeline abbreviation snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora.base import (
    CorpusAdapterError,
    ParsedSourceAnnotation,
    ParsedSourceRecord,
    SourceResource,
    map_source_record,
)
from abrex.corpora.diagnostics import DiagnosticsCollector
from abrex.domain import CorpusRecord, SourceTextSpan

SNAPSHOT_SCHEMA_VERSION = "clp-abbr-snapshot-v1"
SNAPSHOT_ADAPTER_VERSION = "1"


class CLPAbbreviationSnapshotAdapter:
    """Read a compact, finalized CLP annotation derivative."""

    identity = "clp_abbr_snapshot_v1"
    version = SNAPSHOT_ADAPTER_VERSION

    def parse(
        self, resource: SourceResource, diagnostics: DiagnosticsCollector
    ) -> Iterable[ParsedSourceRecord]:
        """Parse mapped annotations and diagnose every unscorable pair."""

        if resource.location is None:
            raise CorpusAdapterError("CLP snapshot requires a source location")
        try:
            stream = resource.location.open("r", encoding="utf-8", newline=None)
        except OSError as error:
            raise CorpusAdapterError(f"Unable to open CLP snapshot: {error}") from error
        with stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise TypeError("snapshot row must be an object")
                    yield self._parse_row(row, diagnostics)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise CorpusAdapterError(
                        f"Invalid CLP snapshot row at line {line_number}: {error}"
                    ) from error

    def _parse_row(
        self, row: Mapping[str, Any], diagnostics: DiagnosticsCollector
    ) -> ParsedSourceRecord:
        if row.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema version")
        record_id = _required_string(row, "record_id")
        document_id = _required_string(row, "document_id")
        text = _string_value(row, "text")
        annotations: list[ParsedSourceAnnotation] = []
        raw_annotations = row.get("annotations", [])
        if not isinstance(raw_annotations, list):
            raise TypeError("annotations must be an array")
        for raw in raw_annotations:
            annotation = _mapping(raw, "annotation")
            annotation_id = _required_string(annotation, "annotation_id")
            mapping_status = _required_string(annotation, "mapping_status")
            if mapping_status != "mapped":
                diagnostics.add(
                    "warning",
                    "CLP_PAIR_UNSCORABLE",
                    "CLP pair did not have unique exact occurrences",
                    action="dropped",
                    record_id=record_id,
                    annotation_id=annotation_id,
                    location="pair",
                    details=(("mapping_status", mapping_status),),
                )
                continue
            short = _source_span(annotation, "short_form", "short_span")
            long = _source_span(annotation, "long_form", "long_span")
            annotations.append(ParsedSourceAnnotation(annotation_id, short, long))
        provenance = _mapping(row.get("provenance"), "provenance")
        commit = str(provenance.get("source_commit", "unknown"))
        return ParsedSourceRecord(
            record_id=record_id,
            document_id=document_id,
            text=text,
            annotations=tuple(annotations),
            source_corpus="CellLiteraturePipeline/abbr-v5-validation-v1",
            transformation_notes=(
                "development_evidence_not_untouched_validation",
                f"source_commit={commit}",
                "unique_exact_occurrences_only",
            ),
        )

    def map_record(self, source_record: ParsedSourceRecord) -> CorpusRecord:
        """Map already-canonical snapshot offsets without normalization."""

        return map_source_record(
            source_record,
            adapter_identity=self.identity,
            adapter_version=self.version,
        )


def export_clp_snapshot(
    *,
    items_path: Path,
    annotations_path: Path,
    output_path: Path,
    manifest_path: Path,
    source_commit: str,
    evaluation_summary_path: Path | None = None,
) -> dict[str, object]:
    """Export finalized CLP annotations as a compact canonical derivative."""

    items_value = _read_json_value(items_path)
    annotations_value = _read_json_value(annotations_path)
    if not isinstance(items_value, list):
        raise ValueError("CLP items source must contain an array")
    if not isinstance(annotations_value, dict):
        raise ValueError("CLP annotations source must contain an object")
    annotations_by_id = annotations_value.get("annotations")
    if not isinstance(annotations_by_id, dict):
        raise ValueError("CLP annotations source requires annotations mapping")
    rows: list[dict[str, object]] = []
    mapped_pairs = 0
    unscorable_pairs = 0
    positive_sections = 0
    negative_sections = 0
    for raw_item in items_value:
        item = _mapping(raw_item, "item")
        item_id = _required_string(item, "id")
        annotation = _mapping(annotations_by_id.get(item_id), "final annotation")
        if annotation.get("done") is not True:
            raise ValueError(f"CLP annotation is not finalized: {item_id}")
        row, row_mapped, row_unscorable = _snapshot_row(item, annotation, source_commit)
        rows.append(row)
        mapped_pairs += row_mapped
        unscorable_pairs += row_unscorable
        if annotation.get("section_decision") == "valid_abbreviation_section":
            positive_sections += 1
        else:
            negative_sections += 1
    output_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in sorted(rows, key=lambda value: str(value["record_id"]))
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8", newline="\n")
    sources: dict[str, object] = {
        "repository": "CellLiteraturePipeline",
        "commit": source_commit,
        "items_sha256": _sha256_file(items_path),
        "annotations_sha256": _sha256_file(annotations_path),
    }
    if evaluation_summary_path is not None:
        sources["evaluation_summary_sha256"] = _sha256_file(evaluation_summary_path)
    manifest: dict[str, object] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "dataset_id": "abbr-v5-validation-v1",
        "evidence_class": "development",
        "source": sources,
        "artifact": {
            "path": output_path.name,
            "sha256": hashlib.sha256(output_text.encode("utf-8")).hexdigest(),
        },
        "counts": {
            "sections": len(rows),
            "positive_sections": positive_sections,
            "negative_sections": negative_sections,
            "mapped_pairs": mapped_pairs,
            "unscorable_pairs": unscorable_pairs,
        },
        "mapping_policy": "unique exact occurrence within declared source passages",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _snapshot_row(
    item: Mapping[str, Any], annotation: Mapping[str, Any], source_commit: str
) -> tuple[dict[str, object], int, int]:
    item_id = _required_string(item, "id")
    source = _mapping(item.get("source"), "source")
    context = _mapping(item.get("document_context"), "document_context")
    raw_passages = context.get("passages")
    raw_indexes = context.get("annotated_passage_indexes")
    if not isinstance(raw_passages, list) or not isinstance(raw_indexes, list):
        raise TypeError("document_context requires passages and annotated indexes")
    selected_indexes = {int(value) for value in raw_indexes}
    passages = [
        _mapping(value, "passage")
        for value in raw_passages
        if int(_mapping(value, "passage")["index"]) in selected_indexes
    ]
    passages.sort(key=lambda value: int(value["index"]))
    text_parts: list[str] = []
    passage_starts: dict[int, int] = {}
    compact_passages: list[dict[str, object]] = []
    cursor = 0
    for passage in passages:
        passage_text = _string_value(passage, "text")
        index = int(passage["index"])
        if text_parts:
            cursor += 1
        passage_starts[index] = cursor
        text_parts.append(passage_text)
        compact_passages.append(
            {
                "index": index,
                "canonical_start": cursor,
                "source_offset": int(passage.get("offset", 0)),
                "section_type": str(passage.get("section_type", "")),
                "type": str(passage.get("type", "")),
                "text": passage_text,
            }
        )
        cursor += len(passage_text)
    text = "\n".join(text_parts)
    compact_annotations: list[dict[str, object]] = []
    mapped = 0
    unscorable = 0
    raw_pairs = annotation.get("pairs", [])
    if not isinstance(raw_pairs, list):
        raise TypeError("annotation pairs must be an array")
    passage_by_index = {int(value["index"]): value for value in passages}
    for pair_index, raw_pair in enumerate(raw_pairs):
        pair = _mapping(raw_pair, "pair")
        short_form = _required_string(pair, "short_form")
        long_form = _required_string(pair, "long_form")
        raw_source_indexes = pair.get("source_passage_indexes", [])
        if not isinstance(raw_source_indexes, list):
            raise TypeError("source_passage_indexes must be an array")
        source_indexes = tuple(int(value) for value in raw_source_indexes)
        short_span = _unique_occurrence(
            short_form, source_indexes, passage_by_index, passage_starts
        )
        long_span = _unique_occurrence(
            long_form, source_indexes, passage_by_index, passage_starts
        )
        if short_span is not None and long_span is not None:
            mapping_status = "mapped"
            mapped += 1
        else:
            mapping_status = (
                "ambiguous_or_missing_short_form"
                if short_span is None
                else "ambiguous_or_missing_long_form"
            )
            unscorable += 1
        compact_annotations.append(
            {
                "annotation_id": f"{item_id}:pair:{pair_index}",
                "short_form": short_form,
                "long_form": long_form,
                "short_span": list(short_span) if short_span is not None else None,
                "long_span": list(long_span) if long_span is not None else None,
                "mapping_status": mapping_status,
                "source_passage_indexes": list(source_indexes),
                "source_first": pair.get("source_first"),
                "source_second": pair.get("source_second"),
                "orientation": pair.get("orientation"),
            }
        )
    source_document_id = _required_string(source, "document_id")
    return (
        {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "record_id": item_id,
            "document_id": f"clp:{source_document_id}:{int(source['start_index'])}",
            "text": text,
            "passages": compact_passages,
            "decision": annotation.get("section_decision"),
            "selection_tags": item.get("selection_tags", []),
            "annotations": compact_annotations,
            "provenance": {
                "source_commit": source_commit,
                "source_filename": source.get("filename"),
                "source_document_id": source_document_id,
                "source_start_index": int(source["start_index"]),
            },
        },
        mapped,
        unscorable,
    )


def _unique_occurrence(
    value: str,
    passage_indexes: Sequence[int],
    passages: Mapping[int, Mapping[str, Any]],
    starts: Mapping[int, int],
) -> tuple[int, int] | None:
    matches: list[tuple[int, int]] = []
    for index in passage_indexes:
        passage = passages.get(index)
        if passage is None:
            continue
        text = _string_value(passage, "text")
        cursor = 0
        while True:
            found = text.find(value, cursor)
            if found < 0:
                break
            start = starts[index] + found
            matches.append((start, start + len(value)))
            cursor = found + 1
    return matches[0] if len(matches) == 1 else None


def _source_span(
    annotation: Mapping[str, Any], text_key: str, span_key: str
) -> SourceTextSpan:
    text = _required_string(annotation, text_key)
    raw_span = annotation.get(span_key)
    if (
        not isinstance(raw_span, list)
        or len(raw_span) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, int) for value in raw_span
        )
    ):
        raise TypeError(f"{span_key} must be a two-integer array")
    return SourceTextSpan(raw_span[0], raw_span[1], text)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise TypeError(f"{key} must be a non-empty string")
    return result


def _string_value(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise TypeError(f"{key} must be a string")
    return result


def _read_json_value(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CLPAbbreviationSnapshotAdapter",
    "SNAPSHOT_SCHEMA_VERSION",
    "export_clp_snapshot",
]
