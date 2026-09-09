"""Pilot-local source extraction with primary-article identity scoping."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from abrex.literature.parsers import parse_pubmed_xml
from abrex.literature.pilot_models import LicenseEvidence


class PilotSourceError(ValueError):
    """Raised when a selected source cannot support the pilot contract."""


@dataclass(frozen=True, slots=True)
class ParsedSection:
    section_id: str
    heading: str
    source_kind: str
    text: str
    source_locator: str


@dataclass(frozen=True, slots=True)
class ParsedStructure:
    structure_id: str
    kind: str
    text: str
    source_path: str
    section_id: str | None = None
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedPilotArticle:
    title: str
    pmid: str | None
    pmcid: str | None
    sections: tuple[ParsedSection, ...]
    structures: tuple[ParsedStructure, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BioCPassage:
    passage_id: str
    document_id: str
    text: str
    offset: int | None
    section_type: str | None


def extract_cc_by_license(payload: bytes, expected_pmcid: str) -> LicenseEvidence:
    """Return exact CC BY evidence from the selected primary article metadata."""

    article = _primary_article(_parse(payload))
    meta = _article_meta(article)
    observed = _article_ids(meta).get("pmc") or _article_ids(meta).get("pmcid")
    if _normalize_pmcid(observed) != _normalize_pmcid(expected_pmcid):
        raise PilotSourceError(
            f"JATS identity mismatch: requested {expected_pmcid}, observed {observed}"
        )
    licenses: list[LicenseEvidence] = []
    license_node_signatures: list[tuple[str, str]] = []
    license_index = 0
    for node in meta.iter():
        if _local(node.tag) != "license":
            continue
        license_index += 1
        text = _element_text(node).strip()
        node_haystack = text.lower()
        if re.search(
            r"non[- ]?commercial|no[- ]?derivatives?|share[- ]?alike|"
            r"\bby[- ]?(?:nc|nd|sa)\b|\bcc0\b|publicdomain",
            node_haystack,
        ):
            raise PilotSourceError("primary article has restricted license evidence")
        refs = [
            child
            for child in node.iter()
            if _local(child.tag) in {"license_ref", "ext-link"}
        ]
        urls = tuple(
            value
            for child in refs
            for value in (
                child.attrib.get("href", "").strip(),
                child.attrib.get("{http://www.w3.org/1999/xlink}href", "").strip(),
                (child.text or "").strip(),
            )
            if value and (value.startswith("http://") or value.startswith("https://"))
        )
        for url in dict.fromkeys(urls):
            if _is_exact_cc_by(url, text):
                match = re.search(r"/licenses/by/(\d+(?:\.\d+)?)(?:/|$)", url.lower())
                licenses.append(
                    LicenseEvidence(
                        family="CC BY",
                        version=match.group(1) if match else None,
                        url=url,
                        text=text,
                        source_path=(
                            f"article/front/article-meta/permissions/license[{license_index}]"
                        ),
                    )
                )
        license_node_signatures.append((text, "|".join(urls)))
    unique = {(item.url, item.text): item for item in licenses}
    if not unique:
        raise PilotSourceError("primary article has no exact CC BY license evidence")
    # A separate restricted or conflicting license node makes eligibility
    # ambiguous.  Never select based on the first permissive node encountered.
    if len(license_node_signatures) != 1:
        raise PilotSourceError("primary article has conflicting license nodes")
    if len({item.version for item in unique.values()}) > 1:
        raise PilotSourceError("primary article has conflicting CC BY license versions")
    return next(iter(unique.values()))


def _is_exact_cc_by(url: str | None, text: str | None) -> bool:
    """Accept attribution-only Creative Commons licenses and reject variants."""

    haystack = f"{url or ''} {text or ''}".lower()
    exact_url = bool(
        re.search(
            r"creativecommons\.org/licenses/by/(?:\d+(?:\.\d+)?/?)?(?:\s|$)", haystack
        )
    )
    exact_text = bool(
        re.search(
            r"creative\s+commons\s+attribution(?:\s+license)?(?:\s+\d+(?:\.\d+)?)?",
            haystack,
        )
        or re.search(r"\bcc\s*[- ]?by(?:\s+\d+(?:\.\d+)?)?\b", haystack)
    )
    restricted = bool(
        re.search(
            r"\bby[- ]?(?:nc|nd|sa)\b|\bcc0\b|publicdomain|"
            r"non[- ]?commercial|no[- ]?derivatives?|share[- ]?alike",
            haystack,
        )
    )
    return (exact_url or exact_text) and not restricted


def parse_pmc_jats(payload: bytes, expected_pmcid: str) -> ParsedPilotArticle:
    """Extract only the requested primary JATS article and nonduplicated sections."""

    article = _primary_article(_parse(payload))
    meta = _article_meta(article)
    identifiers = _article_ids(meta)
    pmcid = _normalize_pmcid(identifiers.get("pmc") or identifiers.get("pmcid"))
    if pmcid != _normalize_pmcid(expected_pmcid):
        raise PilotSourceError(
            f"JATS identity mismatch: requested {expected_pmcid}, observed {pmcid}"
        )
    pmid = identifiers.get("pmid")
    title_node = _first_descendant(_child(meta, "title-group"), "article-title")
    title = _element_text(title_node).strip() if title_node is not None else ""
    if not title:
        raise PilotSourceError("primary JATS article has no title")

    sections: list[ParsedSection] = []
    structures: list[ParsedStructure] = []
    diagnostics: list[str] = []
    used_ids: set[str] = set()

    def add_section(
        text: str, heading: str, source_kind: str, locator: str
    ) -> str | None:
        if not text:
            return None
        base = _slug(locator)
        section_id = base
        suffix = 2
        while section_id in used_ids:
            section_id = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(section_id)
        sections.append(ParsedSection(section_id, heading, source_kind, text, locator))
        return section_id

    add_section(
        title, "Title", "title", "article/front/article-meta/title-group/article-title"
    )
    abstracts = [node for node in meta if _local(node.tag) == "abstract"]
    for index, abstract in enumerate(abstracts, 1):
        text = _element_text(abstract)
        add_section(
            text,
            "Abstract" if index == 1 else f"Abstract {index}",
            "abstract",
            f"article/front/article-meta/abstract[{index}]",
        )

    body = _child(article, "body")
    if body is not None:
        _extract_body(
            body,
            "article/body",
            "Body",
            add_section,
            structures,
            diagnostics,
        )
    if not sections:
        raise PilotSourceError("primary JATS article has no usable sections")
    return ParsedPilotArticle(
        title=title,
        pmid=pmid,
        pmcid=pmcid,
        sections=tuple(sections),
        structures=tuple(structures),
        diagnostics=tuple(diagnostics),
    )


def parse_pubmed_source(payload: bytes, expected_pmid: str) -> ParsedPilotArticle:
    """Use the strict PubMed parser and retain title/abstract as separate sections."""

    parsed = parse_pubmed_xml(payload, include_title=True)
    article = parsed.article
    if article.pmid != expected_pmid:
        raise PilotSourceError(
            f"PubMed identity mismatch: requested {expected_pmid}, "
            f"observed {article.pmid}"
        )
    sections = tuple(
        ParsedSection(
            section.section_id,
            section.title or ("Title" if section.section_id == "title" else "Abstract"),
            "title" if section.section_id == "title" else "abstract",
            section.text,
            section.source_id or section.section_id,
        )
        for section in article.sections
    )
    if not any(
        section.source_kind == "abstract" and section.text.strip()
        for section in sections
    ):
        raise PilotSourceError("PubMed record has no nonempty abstract")
    return ParsedPilotArticle(
        title=article.title
        or next(section.text for section in sections if section.source_kind == "title"),
        pmid=article.pmid,
        pmcid=article.pmcid,
        sections=sections,
        diagnostics=tuple(item.code for item in parsed.diagnostics),
    )


def parse_bioc_xml(payload: bytes) -> tuple[BioCPassage, ...]:
    """Read Unicode BioC XML passages without mapping them onto JATS offsets."""

    root = _parse(payload)
    passages: list[BioCPassage] = []
    for document_index, document in enumerate(
        (node for node in root.iter() if _local(node.tag) == "document"), 1
    ):
        identifier_node = _child(document, "id")
        document_id = (
            _element_text(identifier_node).strip() or f"document-{document_index}"
        )
        passage_index = 0
        for passage in document:
            if _local(passage.tag) != "passage":
                continue
            passage_index += 1
            text_node = _child(passage, "text")
            if text_node is None:
                continue
            text = text_node.text or ""
            offset_text = _element_text(_child(passage, "offset")).strip()
            try:
                offset = int(offset_text) if offset_text else None
            except ValueError as error:
                raise PilotSourceError(
                    "BioC passage offset is not an integer"
                ) from error
            infons = {
                node.attrib.get("key", ""): _element_text(node)
                for node in passage
                if _local(node.tag) == "infon"
            }
            section_type = infons.get("section_type") or infons.get("type")
            passages.append(
                BioCPassage(
                    f"{document_id}/passage-{passage_index}",
                    document_id,
                    text,
                    offset,
                    section_type,
                )
            )
    if not passages:
        raise PilotSourceError("BioC XML has no text passages")
    return tuple(passages)


def _extract_body(
    node: ET.Element,
    path: str,
    heading: str,
    add_section: object,
    structures: list[ParsedStructure],
    diagnostics: list[str],
) -> None:
    add = add_section
    counts: dict[str, int] = {}
    for child in node:
        tag = _local(child.tag)
        counts[tag] = counts.get(tag, 0) + 1
        child_path = f"{path}/{tag}[{counts[tag]}]"
        if tag in {"sub-article", "ref-list"}:
            diagnostics.append(f"excluded-nonprimary-structure:{child_path}")
            continue
        if tag == "sec":
            title_node = _child(child, "title")
            child_heading = (
                _element_text(title_node).strip() if title_node is not None else heading
            )
            _extract_body(
                child,
                child_path,
                child_heading or heading,
                add,
                structures,
                diagnostics,
            )
            continue
        if tag == "title":
            continue
        if tag == "p":
            add(_element_text(child), heading, "paragraph", child_path)  # type: ignore[operator]
            continue
        if tag == "table-wrap":
            _extract_table(child, child_path, heading, add, structures)
            continue
        if tag == "def-list":
            _extract_definitions(child, child_path, heading, add, structures)
            continue
        if tag == "fig":
            _extract_figure(child, child_path, heading, add, structures, diagnostics)
            continue
        if tag == "fn":
            text = _element_text(child)
            section_id = add(text, heading, "footnote", child_path)  # type: ignore[operator]
            structures.append(
                ParsedStructure(
                    _slug(child_path), "footnote", text, child_path, section_id
                )
            )
            continue
        _extract_body(child, child_path, heading, add, structures, diagnostics)


def _extract_table(
    table_wrap: ET.Element,
    path: str,
    heading: str,
    add: object,
    structures: list[ParsedStructure],
) -> None:
    table_id = _slug(path)
    caption = _child(table_wrap, "caption")
    caption_text = _element_text(caption) if caption is not None else ""
    structures.append(ParsedStructure(table_id, "table", caption_text, path))
    if caption is not None and caption_text:
        locator = f"{path}/caption"
        section_id = add(caption_text, heading, "caption", locator)  # type: ignore[operator]
        structures.append(
            ParsedStructure(
                f"{table_id}-caption",
                "caption",
                caption_text,
                locator,
                section_id,
                table_id,
            )
        )
    cell_index = 0
    for cell in table_wrap.iter():
        tag = _local(cell.tag)
        if tag not in {"th", "td"}:
            continue
        cell_index += 1
        text = _element_text(cell)
        kind = "table-header-cell" if tag == "th" else "table-cell"
        locator = f"{path}/table/{tag}[{cell_index}]"
        section_id = add(text, heading, kind, locator)  # type: ignore[operator]
        structures.append(
            ParsedStructure(
                f"{table_id}-{tag}-{cell_index}",
                kind,
                text,
                locator,
                section_id,
                table_id,
            )
        )
    for foot_index, foot in enumerate(
        (node for node in table_wrap.iter() if _local(node.tag) == "table-wrap-foot"), 1
    ):
        text = _element_text(foot)
        locator = f"{path}/table-wrap-foot[{foot_index}]"
        section_id = add(text, heading, "table-footnote", locator)  # type: ignore[operator]
        structures.append(
            ParsedStructure(
                f"{table_id}-foot-{foot_index}",
                "table-footnote",
                text,
                locator,
                section_id,
                table_id,
            )
        )


def _extract_definitions(
    definition_list: ET.Element,
    path: str,
    heading: str,
    add: object,
    structures: list[ParsedStructure],
) -> None:
    list_id = _slug(path)
    structures.append(
        ParsedStructure(
            list_id, "definition-list", _element_text(definition_list), path
        )
    )
    for kind, tag in (("definition-term", "term"), ("definition", "def")):
        index = 0
        for node in definition_list.iter():
            if _local(node.tag) != tag:
                continue
            index += 1
            text = _element_text(node)
            locator = f"{path}/{tag}[{index}]"
            section_id = add(text, heading, kind, locator)  # type: ignore[operator]
            structures.append(
                ParsedStructure(
                    f"{list_id}-{tag}-{index}", kind, text, locator, section_id, list_id
                )
            )


def _extract_figure(
    figure: ET.Element,
    path: str,
    heading: str,
    add: object,
    structures: list[ParsedStructure],
    diagnostics: list[str],
) -> None:
    figure_id = _slug(path)
    caption = _child(figure, "caption")
    text = _element_text(caption) if caption is not None else ""
    structures.append(ParsedStructure(figure_id, "figure", text, path))
    if text:
        locator = f"{path}/caption"
        section_id = add(text, heading, "caption", locator)  # type: ignore[operator]
        structures.append(
            ParsedStructure(
                f"{figure_id}-caption", "caption", text, locator, section_id, figure_id
            )
        )
    if any(_local(node.tag) == "graphic" for node in figure.iter()):
        diagnostics.append(f"unsupported-image-asset:{path}")


def _primary_article(root: ET.Element) -> ET.Element:
    if _local(root.tag) == "article":
        return root
    candidates = [child for child in root if _local(child.tag) == "article"]
    if len(candidates) != 1:
        raise PilotSourceError(
            "JATS source must contain exactly one primary article; "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _article_meta(article: ET.Element) -> ET.Element:
    front = _child(article, "front")
    meta = _child(front, "article-meta") if front is not None else None
    if meta is None:
        raise PilotSourceError("primary JATS article has no front/article-meta")
    return meta


def _article_ids(meta: ET.Element) -> dict[str, str]:
    return {
        node.attrib.get("pub-id-type", "").lower(): _element_text(node).strip()
        for node in meta
        if _local(node.tag) == "article-id" and _element_text(node).strip()
    }


def _normalize_pmcid(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned if cleaned.startswith("PMC") else f"PMC{cleaned}"


def _parse(payload: bytes) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except (ET.ParseError, UnicodeError) as error:
        raise PilotSourceError(f"invalid XML: {error}") from error


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(node: ET.Element | None, tag: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if _local(child.tag) == tag), None)


def _first_descendant(node: ET.Element | None, tag: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node.iter() if _local(child.tag) == tag), None)


def _element_text(node: ET.Element | None) -> str:
    return "" if node is None else "".join(node.itertext())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "section"


__all__ = [
    "BioCPassage",
    "ParsedPilotArticle",
    "ParsedSection",
    "ParsedStructure",
    "PilotSourceError",
    "_is_exact_cc_by",
    "extract_cc_by_license",
    "parse_bioc_xml",
    "parse_pmc_jats",
    "parse_pubmed_source",
]
