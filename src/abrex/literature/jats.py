"""Offline JATS reader that keeps table and definition structure visible."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from abrex.literature.models import Article, ArticleSection, ArticleStructure
from abrex.literature.parsers import (
    ArticleParseDiagnostic,
    ArticleParseError,
    ArticleParseResult,
)


def read_jats_xml(path: Path, *, include_title: bool = False) -> ArticleParseResult:
    """Read one local JATS article and retain its original byte digest."""

    try:
        payload = path.read_bytes()
    except (OSError, UnicodeError) as error:
        raise ArticleParseError(f"unable to read source {path}: {error}") from error
    return parse_jats_xml(payload, include_title=include_title)


def parse_jats_xml(
    payload: bytes | str, *, include_title: bool = False
) -> ArticleParseResult:
    """Parse JATS logical text and structural elements without flattening cells."""

    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, UnicodeError) as error:
        raise ArticleParseError(f"invalid JATS XML: {error}") from error
    nodes = tuple(_walk(root))
    article_ids = {
        node.attrib.get("pub-id-type", "").lower(): _text(node)
        for _, node in nodes
        if _local(node.tag) == "article-id" and _text(node)
    }
    pmid = article_ids.get("pmid")
    pmcid = article_ids.get("pmc") or article_ids.get("pmcid")
    article_id = pmcid or pmid or root.attrib.get("id")
    if not article_id:
        raise ArticleParseError("JATS article has no stable id")
    title_node = next(
        (node for _, node in nodes if _local(node.tag) == "article-title"), None
    )
    title = _element_text(title_node) if title_node is not None else None
    sections: list[ArticleSection] = []
    structures: list[ArticleStructure] = []
    diagnostics: list[ArticleParseDiagnostic] = []
    used_ids: set[str] = set()

    if include_title and title:
        sections.append(
            ArticleSection(
                "title", title, "Title", "front/article-title", 0, len(title)
            )
        )
    for path, node in nodes:
        tag = _local(node.tag)
        if tag == "abstract":
            abstract_id = _node_id(path, "abstract")
            abstract_text = _element_text(node)
            if abstract_text:
                section_id = _unique(_slug(abstract_id), used_ids, diagnostics)
                sections.append(
                    ArticleSection(
                        section_id,
                        abstract_text,
                        "Abstract",
                        path,
                        0,
                        len(abstract_text),
                    )
                )
        elif tag == "p" and not _under(
            path, {"table-wrap", "caption", "table-wrap-foot", "def-list"}
        ):
            text = _element_text(node)
            if text:
                section_id = _unique(_slug(path), used_ids, diagnostics)
                sections.append(
                    ArticleSection(section_id, text, None, path, 0, len(text))
                )

    for path, table in nodes:
        if _local(table.tag) == "table-wrap":
            table_id = _node_id(path, "table")
            structures.append(
                _structure(
                    table_id,
                    "table",
                    _element_text(_child(table, "caption")),
                    path,
                    attributes=table.attrib,
                )
            )
            caption = _child(table, "caption")
            if caption is not None and _element_text(caption):
                caption_id = f"{table_id}/caption"
                text = _element_text(caption)
                structures.append(
                    _structure(caption_id, "caption", text, f"{path}/caption", table_id)
                )
                section_id = _unique(_slug(caption_id), used_ids, diagnostics)
                sections.append(
                    ArticleSection(
                        section_id, text, "Caption", f"{path}/caption", 0, len(text)
                    )
                )
            table_node = _child(table, "table")
            if table_node is None:
                diagnostics.append(
                    ArticleParseDiagnostic(
                        "unsupported-table", f"{path} has no table grid"
                    )
                )
            else:
                for row_path, row in _descendants(
                    table_node, "tr", path=f"{path}/table"
                ):
                    for cell_path, cell in _descendants(
                        row, {"th", "td"}, path=row_path
                    ):
                        text = _element_text(cell)
                        cell_id = _node_id(cell_path, "cell")
                        kind = (
                            "table-header-cell"
                            if _local(cell.tag) == "th"
                            else "table-cell"
                        )
                        structures.append(
                            _structure(
                                cell_id, kind, text, cell_path, table_id, cell.attrib
                            )
                        )
                        if text:
                            section_id = _unique(_slug(cell_id), used_ids, diagnostics)
                            sections.append(
                                ArticleSection(
                                    section_id, text, kind, cell_path, 0, len(text)
                                )
                            )
            for foot_path, foot in _descendants(table, "table-wrap-foot", path=path):
                text = _element_text(foot)
                structures.append(
                    _structure(
                        _node_id(foot_path, "footnote"),
                        "table-footnote",
                        text,
                        foot_path,
                        table_id,
                    )
                )
                if text:
                    section_id = _unique(
                        _slug(_node_id(foot_path, "footnote")), used_ids, diagnostics
                    )
                    sections.append(
                        ArticleSection(
                            section_id, text, "Table footnote", foot_path, 0, len(text)
                        )
                    )

    for path, definition_list in nodes:
        if _local(definition_list.tag) != "def-list":
            continue
        list_id = _node_id(path, "definition-list")
        structures.append(
            _structure(list_id, "definition-list", _element_text(definition_list), path)
        )
        terms = tuple(_descendants(definition_list, "term", path=path))
        definitions = tuple(_descendants(definition_list, "def", path=path))
        for index, (term_path, term) in enumerate(terms):
            text = _element_text(term)
            structures.append(
                _structure(
                    f"{list_id}/term/{index + 1}",
                    "definition-term",
                    text,
                    term_path,
                    list_id,
                )
            )
            if text:
                section_id = _unique(
                    _slug(f"{list_id}-term-{index + 1}"), used_ids, diagnostics
                )
                sections.append(
                    ArticleSection(
                        section_id, text, "Definition term", term_path, 0, len(text)
                    )
                )
        for index, (definition_path, definition) in enumerate(definitions):
            text = _element_text(definition)
            structures.append(
                _structure(
                    f"{list_id}/definition/{index + 1}",
                    "definition",
                    text,
                    definition_path,
                    list_id,
                )
            )
            if text:
                section_id = _unique(
                    _slug(f"{list_id}-definition-{index + 1}"), used_ids, diagnostics
                )
                sections.append(
                    ArticleSection(
                        section_id, text, "Definition", definition_path, 0, len(text)
                    )
                )

    for path, figure in nodes:
        if _local(figure.tag) == "fig" and any(
            _local(node.tag) == "graphic" for node in figure.iter()
        ):
            structures.append(
                _structure(
                    _node_id(path, "figure"),
                    "unsupported-image-asset",
                    _element_text(figure),
                    path,
                )
            )
            diagnostics.append(
                ArticleParseDiagnostic(
                    "unsupported-image-asset",
                    (
                        f"image pixels are not parsed for {path}; caption text, "
                        "if present, is retained"
                    ),
                )
            )
    if not sections:
        raise ArticleParseError("JATS article has no usable textual sections")
    return ArticleParseResult(
        Article(
            article_id=article_id,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            source_format="jats-xml",
            source_version=root.attrib.get("article-version"),
            source_sha256=hashlib.sha256(raw).hexdigest(),
            source_coordinate_system="logical-text",
            sections=tuple(sections),
            structures=tuple(structures),
        ),
        tuple(diagnostics),
    )


def _walk(root: ET.Element, path: str = "article") -> Iterator[tuple[str, ET.Element]]:
    yield path, root
    counts: dict[str, int] = {}
    for child in root:
        tag = _local(child.tag)
        counts[tag] = counts.get(tag, 0) + 1
        yield from _walk(child, f"{path}/{tag}[{counts[tag]}]")


def _descendants(
    root: ET.Element, tags: str | set[str], *, path: str
) -> Iterator[tuple[str, ET.Element]]:
    wanted = {tags} if isinstance(tags, str) else tags
    for candidate_path, candidate in _walk(root, path):
        if candidate_path == path:
            continue
        if _local(candidate.tag) in wanted:
            yield candidate_path, candidate


def _children(root: ET.Element, tag: str) -> tuple[ET.Element, ...]:
    return tuple(child for child in root if _local(child.tag) == tag)


def _child(root: ET.Element, tag: str) -> ET.Element | None:
    return next(iter(_children(root, tag)), None)


def _under(path: str, tags: set[str]) -> bool:
    return any(part.split("[", 1)[0] in tags for part in path.split("/"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(node: ET.Element | None) -> str:
    return "".join(node.itertext()) if node is not None else ""


def _text(node: ET.Element) -> str:
    return _element_text(node).strip()


def _node_id(path: str, kind: str) -> str:
    return f"{kind}:{path}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "node"


def _unique(
    candidate: str, used: set[str], diagnostics: list[ArticleParseDiagnostic]
) -> str:
    if candidate not in used:
        used.add(candidate)
        return candidate
    index = 2
    while f"{candidate}-{index}" in used:
        index += 1
    selected = f"{candidate}-{index}"
    used.add(selected)
    diagnostics.append(
        ArticleParseDiagnostic(
            "duplicate-section-id",
            f"duplicate section {candidate!r}; used {selected!r}",
        )
    )
    return selected


def _structure(
    node_id: str,
    kind: str,
    text: str,
    source_path: str,
    parent_id: str | None = None,
    attributes: dict[str, str] | None = None,
) -> ArticleStructure:
    return ArticleStructure(
        node_id=node_id,
        kind=kind,
        text=text,
        source_path=source_path,
        parent_id=parent_id,
        attributes=tuple(
            sorted((key, value) for key, value in (attributes or {}).items())
        ),
    )


__all__ = ["parse_jats_xml", "read_jats_xml"]
