"""Offline JSON I/O for local PubMed/PMC article representations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from abrex.literature.mapping import ArticleResolutionResult
from abrex.literature.models import (
    Article,
    ArticleDocument,
    ArticleSection,
    ArticleStructure,
)
from abrex.resolvers.serialization import prediction_record_to_dict

ARTICLE_SCHEMA_VERSION = "local-article-v1"
ARTICLE_RESOLUTION_SCHEMA_VERSION = "article-resolutions-v1"


class ArticleSerializationError(ValueError):
    """Raised when a local article or resolution artifact is malformed."""


def article_from_dict(data: Mapping[str, object]) -> Article:
    """Parse the small, stable local article interchange representation."""

    if not isinstance(data, Mapping):
        raise TypeError("article JSON root must be an object")
    schema_version = data.get("schema_version")
    if schema_version is not None and schema_version != ARTICLE_SCHEMA_VERSION:
        raise ArticleSerializationError(
            f"Unsupported article schema version: {schema_version!r}"
        )
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, Sequence) or isinstance(raw_sections, str | bytes):
        raise ArticleSerializationError("article.sections must be a JSON array")
    sections: list[ArticleSection] = []
    for index, raw_section in enumerate(raw_sections):
        if not isinstance(raw_section, Mapping):
            raise ArticleSerializationError(
                f"article.sections[{index}] must be a JSON object"
            )
        section_id = raw_section.get("section_id", raw_section.get("id"))
        if section_id is None:
            section_id = f"section-{index}"
        text = raw_section.get("text")
        if not isinstance(section_id, str) or not section_id.strip():
            raise ArticleSerializationError(
                f"article.sections[{index}].section_id must be non-empty"
            )
        if not isinstance(text, str):
            raise ArticleSerializationError(
                f"article.sections[{index}].text must be a string"
            )
        title = raw_section.get("title")
        if title is not None and not isinstance(title, str):
            raise ArticleSerializationError(
                f"article.sections[{index}].title must be a string or null"
            )
        sections.append(
            ArticleSection(
                section_id,
                text,
                title,
                _optional_string(raw_section, "source_id"),
                _optional_int(raw_section, "source_offset"),
                _optional_int(raw_section, "source_length"),
            )
        )
    raw_structures = data.get("structures", [])
    if not isinstance(raw_structures, Sequence) or isinstance(
        raw_structures, str | bytes
    ):
        raise ArticleSerializationError("article.structures must be a JSON array")
    structures: list[ArticleStructure] = []
    for index, raw_structure in enumerate(raw_structures):
        if not isinstance(raw_structure, Mapping):
            raise ArticleSerializationError(
                f"article.structures[{index}] must be a JSON object"
            )
        attributes = raw_structure.get("attributes", [])
        if not isinstance(attributes, Sequence) or isinstance(attributes, str | bytes):
            raise ArticleSerializationError(
                f"article.structures[{index}].attributes must be an array"
            )
        pairs: list[tuple[str, str]] = []
        for pair in attributes:
            if (
                not isinstance(pair, Sequence)
                or isinstance(pair, str | bytes)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise ArticleSerializationError(
                    f"article.structures[{index}].attributes must contain string pairs"
                )
            pairs.append((pair[0], pair[1]))
        node_id = raw_structure.get("node_id")
        kind = raw_structure.get("kind")
        text = raw_structure.get("text")
        source_path = raw_structure.get("source_path")
        if not all(
            isinstance(value, str) for value in (node_id, kind, text, source_path)
        ):
            raise ArticleSerializationError(
                f"article.structures[{index}] requires string node_id, kind, text "
                "and source_path"
            )
        structures.append(
            ArticleStructure(
                cast(str, node_id),
                cast(str, kind),
                cast(str, text),
                cast(str, source_path),
                _optional_string(raw_structure, "parent_id"),
                tuple(pairs),
            )
        )
    article_id = _optional_string(data, "article_id") or _optional_string(data, "id")
    return Article(
        article_id=article_id,
        pmid=_optional_string(data, "pmid"),
        pmcid=_optional_string(data, "pmcid"),
        title=_optional_string(data, "title"),
        source_format=_optional_string(data, "source_format"),
        source_version=_optional_string(data, "source_version"),
        source_sha256=_optional_string(data, "source_sha256"),
        source_coordinate_system=(
            _optional_string(data, "source_coordinate_system") or "logical-text"
        ),
        structures=tuple(structures),
        sections=tuple(sections),
    )


def article_to_dict(article: Article) -> dict[str, object]:
    """Return the stable local article representation."""

    return {
        "schema_version": ARTICLE_SCHEMA_VERSION,
        "article_id": article.stable_id,
        "pmid": article.pmid,
        "pmcid": article.pmcid,
        "title": article.title,
        "source_format": article.source_format,
        "source_version": article.source_version,
        "source_sha256": article.source_sha256,
        "source_coordinate_system": article.source_coordinate_system,
        "structures": [
            {
                "node_id": structure.node_id,
                "kind": structure.kind,
                "text": structure.text,
                "source_path": structure.source_path,
                "parent_id": structure.parent_id,
                "attributes": [list(pair) for pair in structure.attributes],
            }
            for structure in article.structures
        ],
        "sections": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "text": section.text,
                "source_id": section.source_id,
                "source_offset": section.source_offset,
                "source_length": section.source_length,
            }
            for section in article.sections
        ],
    }


def read_article_json(path: Path) -> Article:
    """Read one locally stored article without performing network access."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArticleSerializationError(
            f"Unable to read article {path}: {error}"
        ) from error
    if not isinstance(data, Mapping):
        raise ArticleSerializationError("article JSON root must be an object")
    try:
        return article_from_dict(data)
    except (TypeError, ValueError) as error:
        raise ArticleSerializationError(f"Invalid article {path}: {error}") from error


def article_resolution_to_dict(result: ArticleResolutionResult) -> dict[str, object]:
    """Serialize predictions and downstream mappings deterministically."""

    return {
        "schema_version": ARTICLE_RESOLUTION_SCHEMA_VERSION,
        "article": {
            "article_id": result.article_id,
            "pmid": result.pmid,
            "pmcid": result.pmcid,
        },
        "resolver": {
            "key": result.resolver.key,
            "version": result.resolver.implementation_version,
        },
        "records": [
            {
                "document": {
                    "document_id": record.source.document.document_id,
                    "text": record.source.document.text,
                },
                "provenance": _provenance(record.source),
                "predictions": prediction_record_to_dict(
                    record.predictions, result.resolver
                ),
                "entities": [entity.to_dict() for entity in record.entities],
            }
            for record in result.records
        ],
        "diagnostics": [diagnostic.to_dict() for diagnostic in result.diagnostics],
    }


def serialize_article_resolution(result: ArticleResolutionResult) -> str:
    """Return stable indented JSON for a resolution result."""

    return (
        json.dumps(
            article_resolution_to_dict(result),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_article_resolution(result: ArticleResolutionResult, path: Path) -> None:
    """Write a resolution artifact using explicit UTF-8 encoding."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        serialize_article_resolution(result), encoding="utf-8", newline="\n"
    )


def _optional_string(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ArticleSerializationError(f"article.{key} must be a string or null")
    return value


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise ArticleSerializationError(f"article.{key} must be an integer or null")
    return value


def _provenance(source: ArticleDocument) -> dict[str, object]:
    provenance = source.provenance
    return {
        "article_id": provenance.article_id,
        "pmid": provenance.pmid,
        "pmcid": provenance.pmcid,
        "title": provenance.title,
        "segmentation_policy": provenance.segmentation_policy,
        "section_id": provenance.section_id,
        "section_title": provenance.section_title,
        "section_index": provenance.section_index,
        "section_ids": list(provenance.section_ids),
        "section_locations": [
            {
                "section_id": location.section_id,
                "canonical_span": {
                    "start": location.canonical_span.start,
                    "end": location.canonical_span.end,
                },
            }
            for location in source.section_locations
        ],
    }


__all__ = [
    "ARTICLE_RESOLUTION_SCHEMA_VERSION",
    "ARTICLE_SCHEMA_VERSION",
    "ArticleSerializationError",
    "article_from_dict",
    "article_resolution_to_dict",
    "article_to_dict",
    "read_article_json",
    "serialize_article_resolution",
    "write_article_resolution",
]
