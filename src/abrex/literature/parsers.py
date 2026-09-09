"""Strict offline readers for PubMed XML and BioC JSON source files."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from abrex.literature.models import Article, ArticleSection


class ArticleParseError(ValueError):
    """Raised when a source article cannot be parsed without guessing."""


@dataclass(frozen=True, slots=True)
class ArticleParseDiagnostic:
    """Visible parser issue that did not prevent a usable article result."""

    code: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class ArticleParseResult:
    """An article plus non-silent source coverage diagnostics."""

    article: Article
    diagnostics: tuple[ArticleParseDiagnostic, ...] = ()


def read_pubmed_xml(path: Path, *, include_title: bool = False) -> ArticleParseResult:
    """Read one local PubMed XML file and attach its exact byte digest."""

    payload = _read_bytes(path)
    return parse_pubmed_xml(payload, include_title=include_title)


def parse_pubmed_xml(
    payload: bytes | str, *, include_title: bool = False
) -> ArticleParseResult:
    """Parse a PubMed XML article without whitespace normalization.

    XML entities and inline element markup are resolved to their logical text
    by the XML parser. The source digest still identifies the original bytes;
    logical text is the explicit coordinate system for the resulting sections.
    Titles are metadata by default and enter canonical sections only when the
    caller explicitly enables ``include_title``.
    """

    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, UnicodeError) as error:
        raise ArticleParseError(f"invalid PubMed XML: {error}") from error
    articles = [
        node for node in root.iter() if _local_name(node.tag) == "PubmedArticle"
    ]
    if len(articles) > 1:
        raise ArticleParseError("PubMed source must contain exactly one article")
    article_node = articles[0] if articles else root
    citation = _child_local(article_node, "MedlineCitation")
    if citation is None:
        citation = article_node
    primary_article = _child_local(citation, "Article")
    if primary_article is None:
        primary_article = citation
    pmid_node = _child_local(citation, "PMID")
    pmid = _text(pmid_node)
    if not pmid:
        raise ArticleParseError("PubMed XML has no PMID")
    title_node = _child_local(primary_article, "ArticleTitle")
    title = _element_text(title_node) if title_node is not None else None
    pubmed_data = _child_local(article_node, "PubmedData")
    primary_ids = _child_local(pubmed_data, "ArticleIdList")
    id_nodes = [] if primary_ids is None else list(primary_ids)
    pmcid = next(
        (
            _text(node)
            for node in id_nodes
            if _local_name(node.tag) == "ArticleId"
            and node.attrib.get("IdType", "").lower() in {"pmc", "pmcid"}
        ),
        None,
    )
    version = pmid_node.attrib.get("Version") if pmid_node is not None else None
    abstract_nodes = [
        node
        for abstract in primary_article
        if _local_name(abstract.tag) == "Abstract"
        for node in abstract
        if _local_name(node.tag) == "AbstractText"
    ]
    sections: list[ArticleSection] = []
    diagnostics: list[ArticleParseDiagnostic] = []
    if include_title and title:
        sections.append(
            ArticleSection("title", title, "Title", "ArticleTitle", 0, len(title))
        )
    abstract_count = 0
    for index, node in enumerate(abstract_nodes):
        text = _element_text(node)
        if not text.strip():
            diagnostics.append(
                ArticleParseDiagnostic(
                    "empty-abstract-passage", f"AbstractText[{index}] has no text"
                )
            )
            continue
        label = node.attrib.get("Label") or node.attrib.get("NlmCategory")
        section_id = _slug(label) if label else f"abstract-{index}"
        section_id = _unique_id(
            section_id, {section.section_id for section in sections}, diagnostics
        )
        sections.append(
            ArticleSection(
                section_id, text, label, f"AbstractText[{index}]", 0, len(text)
            )
        )
        abstract_count += 1
    if not abstract_count:
        raise ArticleParseError("PubMed XML has no non-empty abstract passages")
    return ArticleParseResult(
        Article(
            article_id=pmcid or pmid,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            source_format="pubmed-xml",
            source_version=version,
            source_sha256=_sha256(raw),
            source_coordinate_system="logical-text",
            sections=tuple(sections),
        ),
        tuple(diagnostics),
    )


def read_bioc_json(path: Path, *, include_title: bool = False) -> ArticleParseResult:
    """Read one local BioC JSON file without contacting NCBI."""

    payload = _read_bytes(path)
    return parse_bioc_json(payload, include_title=include_title)


def parse_bioc_json(
    payload: bytes | str, *, include_title: bool = False
) -> ArticleParseResult:
    """Parse one BioC document while retaining passage coordinates and IDs."""

    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ArticleParseError(f"invalid BioC JSON: {error}") from error
    collections = data if isinstance(data, list) else [data]
    documents = [
        document
        for collection in collections
        if isinstance(collection, Mapping)
        for document in collection.get("documents", [])
        if isinstance(document, Mapping)
    ]
    if len(documents) != 1:
        raise ArticleParseError(
            f"BioC source must contain exactly one document, found {len(documents)}"
        )
    document = documents[0]
    infons = document.get("infons")
    document_infons = infons if isinstance(infons, Mapping) else {}
    document_id = _string_or_none(document.get("id"))
    pmid = _first_identifier(document_infons, "pmid")
    pmcid = _first_identifier(document_infons, "pmcid")
    article_id = document_id or pmcid or pmid
    if article_id is None:
        raise ArticleParseError("BioC document has no stable id, PMID, or PMCID")
    version = next(
        (
            _string_or_none(collection.get("version"))
            for collection in collections
            if isinstance(collection, Mapping)
        ),
        None,
    )
    diagnostics: list[ArticleParseDiagnostic] = []
    sections: list[ArticleSection] = []
    used_ids: set[str] = set()
    title: str | None = None
    raw_passages = document.get("passages")
    if not isinstance(raw_passages, list):
        raise ArticleParseError("BioC document.passages must be an array")
    for index, raw_passage in enumerate(raw_passages):
        if not isinstance(raw_passage, Mapping):
            diagnostics.append(
                ArticleParseDiagnostic(
                    "unsupported-passage", f"passage[{index}] is not an object"
                )
            )
            continue
        text = raw_passage.get("text")
        if not isinstance(text, str) or not text:
            diagnostics.append(
                ArticleParseDiagnostic(
                    "unsupported-passage", f"passage[{index}] has no non-empty text"
                )
            )
            continue
        passage_infons = raw_passage.get("infons")
        passage_infons = passage_infons if isinstance(passage_infons, Mapping) else {}
        passage_type = _string_or_none(passage_infons.get("type"))
        source_id = _string_or_none(raw_passage.get("id")) or f"passage-{index}"
        section_id = _slug(source_id)
        section_id = _unique_id(section_id, used_ids, diagnostics)
        if passage_type and passage_type.lower() == "title":
            title = title or text
            if not include_title:
                continue
        offset = _nonnegative_int(raw_passage.get("offset"), "offset", index)
        length = _nonnegative_int(raw_passage.get("length"), "length", index)
        if length is None:
            length = len(text)
        section_title = _string_or_none(passage_infons.get("section")) or passage_type
        sections.append(
            ArticleSection(section_id, text, section_title, source_id, offset, length)
        )
    if not sections:
        raise ArticleParseError("BioC document has no usable passages")
    return ArticleParseResult(
        Article(
            article_id=article_id,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            source_format="bioc-json",
            source_version=version,
            source_sha256=_sha256(raw),
            source_coordinate_system="bioc-character-offsets",
            sections=tuple(sections),
        ),
        tuple(diagnostics),
    )


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, UnicodeError) as error:
        raise ArticleParseError(f"unable to read source {path}: {error}") from error


def _child_local(root: ET.Element | None, name: str) -> ET.Element | None:
    if root is None:
        return None
    return next((node for node in root if _local_name(node.tag) == name), None)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ET.Element | None) -> str | None:
    return node.text.strip() if node is not None and node.text else None


def _element_text(node: ET.Element | None) -> str:
    return "".join(node.itertext()) if node is not None else ""


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "passage"


def _unique_id(
    candidate: str,
    used: set[str],
    diagnostics: list[ArticleParseDiagnostic],
) -> str:
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix = 2
    while f"{candidate}-{suffix}" in used:
        suffix += 1
    selected = f"{candidate}-{suffix}"
    used.add(selected)
    diagnostics.append(
        ArticleParseDiagnostic(
            "duplicate-passage-id",
            f"duplicate passage identifier {candidate!r}; used {selected!r}",
        )
    )
    return selected


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _first_identifier(infons: Mapping[object, object], key: str) -> str | None:
    for candidate in (key, key.upper(), key.lower()):
        value = _string_or_none(infons.get(candidate))
        if value:
            return value
    return None


def _nonnegative_int(value: object, field: str, index: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArticleParseError(
            f"BioC passage[{index}].{field} must be a non-negative integer"
        )
    return value


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "ArticleParseDiagnostic",
    "ArticleParseError",
    "ArticleParseResult",
    "parse_bioc_json",
    "parse_pubmed_xml",
    "read_bioc_json",
    "read_pubmed_xml",
]
