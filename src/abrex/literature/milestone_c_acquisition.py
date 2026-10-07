"""Bounded source-only acquisition service for campaign Milestone C."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from abrex.literature.blind_review import read_blind_packet, write_blind_packet
from abrex.literature.fresh_sampling import (
    ExclusionLedger,
    FreshArticleGroup,
    FreshSamplingError,
    SourcePassage,
    assert_prediction_free,
    load_exclusion_ledger,
    segment_prose,
)
from abrex.literature.milestone_c_sampling import (
    MilestoneCSampleConfig,
    build_milestone_c_packet,
    config_fingerprint,
    mapping_keys,
    selected_passage,
)
from abrex.literature.pilot_sampling import (
    BoundedClient,
    PilotLimitError,
    RequestBudget,
    deterministic_uid_draws,
    discover_uid_frame,
)
from abrex.literature.pilot_sources import (
    ParsedPilotArticle,
    PilotSourceError,
    extract_cc_by_license,
    parse_pmc_jats,
    parse_pubmed_source,
)
from abrex.literature.review_models import (
    AnnotationState,
    ReviewStructure,
    empty_annotation_state,
    validate_annotation_state,
)

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_ABBR_HEADING = re.compile(r"^abbr(?:eviation)?s?\.?$", re.IGNORECASE)


class CachedBoundedClient:
    """Cache immutable responses by URL while retaining bounded network calls."""

    def __init__(self, client: BoundedClient, cache_dir: Path) -> None:
        self.client = client
        self.cache_dir = cache_dir
        self.cache_hits = 0

    def get(self, url: str, *, metadata: bool = False) -> bytes:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{key}.response"
        if path.is_file():
            self.cache_hits += 1
            return path.read_bytes()
        payload = self.client.get(url, metadata=metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        return payload

    def inventory(self) -> dict[str, int]:
        """Summarize the durable URL-addressed response cache."""

        files = tuple(self.cache_dir.glob("*.response"))
        return {
            "entries": len(files),
            "bytes": sum(path.stat().st_size for path in files),
        }


def acquire_milestone_c_sample(config: MilestoneCSampleConfig) -> dict[str, object]:
    """Draw, acquire, freeze, and package the approved source-only sample."""

    root = Path(config.output_dir)
    delivery = Path(config.delivery_dir)
    manifest_path = delivery / "source-manifest-v1.json"
    if manifest_path.is_file():
        return validate_existing_sample(manifest_path)
    protocol_path = Path(config.protocol_path)
    protocol_bytes = protocol_path.read_bytes()
    if _sha(protocol_bytes) != config.protocol_sha256:
        raise FreshSamplingError("Milestone C protocol hash differs from config")
    protocol = json.loads(protocol_bytes)
    if protocol.get("status") != "approved_and_frozen":
        raise FreshSamplingError("Milestone C protocol is not approved and frozen")
    ledger = load_exclusion_ledger(Path(value) for value in config.exclusion_paths)
    exclusions = _mapping(protocol.get("exclusions"), "protocol exclusions")
    if list(ledger.pmids) != exclusions.get("pmids") or list(ledger.pmcids) != (
        exclusions.get("pmcids")
    ):
        raise FreshSamplingError(
            "current exclusion ledger differs from frozen protocol"
        )

    started = _now()
    root.mkdir(parents=True, exist_ok=True)
    delivery.mkdir(parents=True, exist_ok=True)
    budget = RequestBudget()
    bounded = BoundedClient(cast(Any, config), budget)
    client = CachedBoundedClient(bounded, root / "response-cache")
    frame = discover_uid_frame(
        "pmc", cast(Any, client), ceiling=config.uid_search_ceiling
    )
    draws = deterministic_uid_draws(
        config.seed,
        "campaign-2026-10-milestone-c-linked-pmc-groups",
        frame.upper_bound,
        config.maximum_attempts_per_stratum * 2,
    )
    representative: list[FreshArticleGroup] = []
    structural: list[FreshArticleGroup] = []
    attempts: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    structural_details: dict[str, dict[str, object]] = {}
    used_pmids: set[str] = set()
    used_pmcids: set[str] = set()
    draw_cursor = 0

    draw_cursor = _acquire_representative(
        draws,
        draw_cursor,
        config,
        client,
        budget,
        ledger,
        representative,
        attempts,
        sources,
        used_pmids,
        used_pmcids,
        root,
        started,
    )
    _acquire_structural(
        draws,
        draw_cursor,
        config,
        client,
        budget,
        ledger,
        structural,
        attempts,
        sources,
        structural_details,
        used_pmids,
        used_pmcids,
        root,
        started,
    )
    complete = (
        len(representative) == config.representative_groups
        and len(structural) == config.structural_groups
    )
    if not complete:
        report = _incomplete(
            config,
            frame.model_dump(mode="json"),
            ledger,
            attempts,
            representative,
            structural,
            budget,
            client.cache_hits,
        )
        _write_json(delivery / "incomplete-source-manifest.json", report)
        return report

    packet = build_milestone_c_packet(representative, structural, config)
    assert_prediction_free(packet)
    forbidden = {
        "suggestions",
        "method_ids",
        "method_diagnostics",
        "confidence",
        "prediction",
        "candidate",
        "gold",
        "gold_annotations",
        "answer",
        "label",
        "resolver",
    }
    leaked = sorted(mapping_keys(packet.model_dump(mode="json")) & forbidden)
    if leaked:
        raise FreshSamplingError(f"blind packet contains forbidden fields: {leaked}")

    packet_path = delivery / "review-packet-blind-v1.json"
    state_path = delivery / "review-packet-blind-v1.annotations.json"
    sidecar_path = delivery / "source-structure-sidecar-v1.json"
    clp_request_path = delivery / "clp-rules-only-request-v1.json"
    write_blind_packet(packet, packet_path)
    state = empty_annotation_state(packet.annotation_packet())
    _write_json(state_path, state.model_dump(mode="json"))
    sidecar = _build_structure_sidecar(
        packet, structural, structural_details, config, root, delivery
    )
    _write_json(sidecar_path, sidecar)
    clp_request = _build_clp_request(packet, sidecar, config)
    _write_json(clp_request_path, clp_request)

    manifest: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-source-manifest-v1",
        "status": "complete_source_only_sample_frozen",
        "started_at": started,
        "finished_at": _now(),
        "population_scope": (
            "seeded numeric-PMC-UID frame restricted to exact-CC-BY primary "
            "articles with linked PMIDs and the source availability required by "
            "each stratum; it is not representative of all PubMed"
        ),
        "protocol": {
            "path": config.protocol_path,
            "sha256": config.protocol_sha256,
            "approval_response": protocol["approval"]["response"],
        },
        "config": config.model_dump(mode="json"),
        "config_sha256": config_fingerprint(config),
        "frame": frame.model_dump(mode="json"),
        "exclusions": ledger.model_dump(mode="json"),
        "attempts": attempts,
        "sources": sources,
        "limits": _limits(budget, client.cache_hits),
        "response_cache": {
            **client.inventory(),
            "path": client.cache_dir.as_posix(),
            "interpretation": (
                "one content-preserved response per successful URL; the final "
                "freeze replay reused these records without new network calls"
            ),
        },
        "counts": {
            "attempts": len(attempts),
            "excluded": sum(item["outcome"] == "excluded" for item in attempts),
            "failed": sum(item["outcome"] == "failed" for item in attempts),
            "article_groups": len(representative) + len(structural),
            "representative_groups": len(representative),
            "structural_groups": len(structural),
            "cases": len(packet.cases),
            "pmc_prose": sum(case.source_kind == "pmc_prose" for case in packet.cases),
            "pubmed_abstract": sum(
                case.source_kind == "pubmed_abstract" for case in packet.cases
            ),
            "table_or_list": sum(
                case.source_kind == "table_or_list" for case in packet.cases
            ),
        },
        "selection": {
            "replacement_rule": (
                "replace only documented source-ineligible or failed-fetch groups "
                "by continuing the single seeded UID order; never inspect apparent "
                "abbreviation content"
            ),
            "representative": {
                "groups": [group.group_id for group in representative],
                "selection_inputs": [
                    "seeded numeric PMC UID order",
                    "exact CC BY license evidence",
                    "linked PMID/PMCID identity",
                    "one source-length PMC prose segment",
                    "one linked PubMed abstract segment",
                ],
            },
            "structural_challenge": {
                "groups": [group.group_id for group in structural],
                "selection_inputs": [
                    "continued seeded numeric PMC UID order",
                    "exact CC BY license evidence",
                    "linked PMID/PMCID identity and stratum disjointness",
                    "source-declared table, definition-list, or ABBR heading",
                ],
                "reported_separately": True,
            },
        },
        "packet": _artifact(packet_path),
        "empty_state": {**_artifact(state_path), "annotation_count": 0},
        "structure_sidecar": _artifact(sidecar_path),
        "clp_rules_only_request": _artifact(clp_request_path),
        "blindness": {
            "evaluated_methods_run": False,
            "candidate_generators_run": False,
            "token_enrichment_used": False,
            "predictions_exposed": False,
            "selection_used_source_structure_only": True,
            "incidental_exposure": [],
        },
    }
    _write_json(manifest_path, manifest)
    return manifest


def _acquire_representative(
    draws: tuple[int, ...],
    start: int,
    config: MilestoneCSampleConfig,
    client: CachedBoundedClient,
    budget: RequestBudget,
    ledger: ExclusionLedger,
    groups: list[FreshArticleGroup],
    attempts: list[dict[str, object]],
    sources: list[dict[str, object]],
    used_pmids: set[str],
    used_pmcids: set[str],
    root: Path,
    started: str,
) -> int:
    cursor = start
    while cursor < len(draws) and len(groups) < config.representative_groups:
        uid = draws[cursor]
        cursor += 1
        pmcid = f"PMC{uid}"
        if cursor - start > config.maximum_attempts_per_stratum:
            budget.reached.append("maximum_attempts_representative")
            break
        try:
            if ledger.excludes(pmcid=pmcid):
                raise FreshSamplingError("prior-pmcid")
            pmc_payload = client.get(_fetch_url("pmc", pmcid))
            parsed_pmc = parse_pmc_jats(pmc_payload, pmcid)
            license_evidence = extract_cc_by_license(pmc_payload, pmcid)
            pmid = parsed_pmc.pmid
            if pmid is None:
                raise PilotSourceError("primary article has no linked PMID")
            if ledger.excludes(pmid=pmid, pmcid=parsed_pmc.pmcid):
                raise FreshSamplingError("linked article group is in prior evidence")
            if pmid in used_pmids or pmcid in used_pmcids:
                raise FreshSamplingError("duplicate linked article group")
            pubmed_payload = client.get(_fetch_url("pubmed", pmid))
            parsed_pubmed = parse_pubmed_source(pubmed_payload, pmid)
            group = _group(parsed_pmc, parsed_pubmed, config, pmcid, pmid)
            if not group.pmc_prose:
                raise FreshSamplingError("no eligible source-derived PMC prose")
            if not group.pubmed_abstract:
                raise FreshSamplingError("no eligible source-derived abstract")
        except PilotLimitError as error:
            attempts.append(
                _attempt(cursor - 1, "representative", pmcid, "failed", str(error))
            )
            break
        except (OSError, PilotSourceError, FreshSamplingError, ValueError) as error:
            attempts.append(
                _attempt(cursor - 1, "representative", pmcid, "excluded", str(error))
            )
            _checkpoint(root, started, attempts, groups, (), budget)
            continue
        artifacts = [
            _write_raw(root / "raw" / f"{pmcid}.xml", pmc_payload),
            _write_raw(root / "raw" / f"PMID{pmid}.xml", pubmed_payload),
        ]
        groups.append(group)
        used_pmids.add(pmid)
        used_pmcids.add(pmcid)
        attempts.append(
            _attempt(cursor - 1, "representative", pmcid, "selected", "eligible", pmid)
        )
        sources.append(
            _source(
                "representative",
                group,
                license_evidence.model_dump(mode="json"),
                artifacts,
            )
        )
        _checkpoint(root, started, attempts, groups, (), budget)
    return cursor


def _acquire_structural(
    draws: tuple[int, ...],
    start: int,
    config: MilestoneCSampleConfig,
    client: CachedBoundedClient,
    budget: RequestBudget,
    ledger: ExclusionLedger,
    groups: list[FreshArticleGroup],
    attempts: list[dict[str, object]],
    sources: list[dict[str, object]],
    details: dict[str, dict[str, object]],
    used_pmids: set[str],
    used_pmcids: set[str],
    root: Path,
    started: str,
) -> None:
    representative_groups = (
        tuple(
            FreshArticleGroup.model_validate(value)
            for value in json.loads(
                (root / "acquisition-checkpoint.json").read_text(encoding="utf-8")
            ).get("representative", [])
        )
        if (root / "acquisition-checkpoint.json").is_file()
        else ()
    )
    for offset, uid in enumerate(draws[start:], start):
        if len(groups) >= config.structural_groups:
            break
        if offset - start >= config.maximum_attempts_per_stratum:
            budget.reached.append("maximum_attempts_structural")
            break
        pmcid = f"PMC{uid}"
        try:
            if ledger.excludes(pmcid=pmcid) or pmcid in used_pmcids:
                raise FreshSamplingError("excluded or already selected PMCID")
            pmc_payload = client.get(_fetch_url("pmc", pmcid))
            parsed_pmc = parse_pmc_jats(pmc_payload, pmcid)
            license_evidence = extract_cc_by_license(pmc_payload, pmcid)
            pmid = parsed_pmc.pmid
            if pmid is None:
                raise PilotSourceError("primary article has no linked PMID")
            if ledger.excludes(pmid=pmid, pmcid=parsed_pmc.pmcid):
                raise FreshSamplingError("linked article group is in prior evidence")
            if pmid in used_pmids:
                raise FreshSamplingError("already selected linked article group")
            group = _group(parsed_pmc, None, config, pmcid, pmid)
            if not group.structured:
                raise FreshSamplingError("no eligible source-declared structure")
        except PilotLimitError as error:
            attempts.append(
                _attempt(offset, "structural_challenge", pmcid, "failed", str(error))
            )
            break
        except (OSError, PilotSourceError, FreshSamplingError, ValueError) as error:
            attempts.append(
                _attempt(offset, "structural_challenge", pmcid, "excluded", str(error))
            )
            _checkpoint(root, started, attempts, representative_groups, groups, budget)
            continue
        raw = _write_raw(root / "raw" / f"{pmcid}.xml", pmc_payload)
        groups.append(group)
        used_pmids.add(pmid)
        used_pmcids.add(pmcid)
        selected = selected_passage(group, config, "structural")
        raw_xml = _element_xml(pmc_payload, selected.source_ref)
        details[group.group_id] = {
            "ordered_passages": [
                {
                    "position": index,
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "source_kind": section.source_kind,
                    "text": section.text,
                    "source_locator": section.source_locator,
                }
                for index, section in enumerate(parsed_pmc.sections)
            ],
            "selected_source_ref": selected.source_ref,
            "selected_source_element_xml": raw_xml,
            "raw_source": raw,
        }
        attempts.append(
            _attempt(
                offset, "structural_challenge", pmcid, "selected", "eligible", pmid
            )
        )
        sources.append(
            _source(
                "structural_challenge",
                group,
                license_evidence.model_dump(mode="json"),
                [raw],
            )
        )
        _checkpoint(root, started, attempts, representative_groups, groups, budget)


def _group(
    pmc: ParsedPilotArticle,
    pubmed: ParsedPilotArticle | None,
    config: MilestoneCSampleConfig,
    pmcid: str,
    pmid: str,
) -> FreshArticleGroup:
    prose = tuple(
        passage
        for section in pmc.sections
        if section.source_kind == "paragraph"
        for passage in segment_prose(
            section.text,
            source_ref=section.source_locator,
            heading=section.heading,
            source_kind="pmc_prose",
            minimum_chars=config.prose_minimum_chars,
            target_chars=config.prose_target_chars,
            maximum_chars=config.prose_maximum_chars,
        )
    )
    abstract = (
        tuple(
            passage
            for section in pubmed.sections
            if section.source_kind == "abstract"
            for passage in segment_prose(
                section.text,
                source_ref=section.source_locator,
                heading=section.heading,
                source_kind="pubmed_abstract",
                minimum_chars=config.prose_minimum_chars,
                target_chars=config.prose_target_chars,
                maximum_chars=config.prose_maximum_chars,
            )
        )
        if pubmed is not None
        else ()
    )
    return FreshArticleGroup(
        group_id=pmid,
        pmid=pmid,
        pmcid=pmcid,
        title=pmc.title,
        pmc_source_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        pubmed_source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        pmc_prose=prose,
        pubmed_abstract=abstract,
        structured=_structured_passages(pmc, config.structured_maximum_chars),
    )


def _structured_passages(
    parsed: ParsedPilotArticle, maximum_chars: int
) -> tuple[SourcePassage, ...]:
    result: list[SourcePassage] = []
    sections_by_id = {section.section_id: section for section in parsed.sections}
    for parent in parsed.structures:
        if parent.kind not in {"table", "definition-list"}:
            continue
        children = tuple(
            item for item in parsed.structures if item.parent_id == parent.structure_id
        )
        texts = [item.text.strip() for item in children if item.text.strip()]
        if not texts and parent.text.strip():
            texts = [parent.text.strip()]
        text = "\n".join(texts)
        if not text or len(text) > maximum_chars:
            continue
        source_section = next(
            (
                sections_by_id[item.section_id]
                for item in children
                if item.section_id in sections_by_id
            ),
            None,
        )
        result.append(
            SourcePassage(
                source_ref=parent.source_path,
                heading=(source_section.heading if source_section else "Table or list"),
                source_kind="table_or_list",
                text=text,
                structures=tuple(
                    ReviewStructure(
                        kind=item.kind, text=item.text, source_path=item.source_path
                    )
                    for item in (parent,) + children
                ),
            )
        )
    for section in parsed.sections:
        heading = " ".join(section.heading.split()).strip(" :")
        if not _ABBR_HEADING.fullmatch(heading):
            continue
        text = " ".join(section.text.split())
        if text and len(text) <= maximum_chars:
            result.append(
                SourcePassage(
                    source_ref=section.source_locator,
                    heading=section.heading,
                    source_kind="table_or_list",
                    text=text,
                    structures=(
                        ReviewStructure(
                            kind="source-declared-abbr-section",
                            text=text,
                            source_path=section.source_locator,
                        ),
                    ),
                )
            )
    return tuple(result)


def _build_structure_sidecar(
    packet: Any,
    groups: list[FreshArticleGroup],
    details: dict[str, dict[str, object]],
    config: MilestoneCSampleConfig,
    root: Path,
    delivery: Path,
) -> dict[str, object]:
    by_group = {group.group_id: group for group in groups}
    cases = []
    fragment_dir = delivery / "structure-xml"
    for case in packet.cases:
        if case.source_kind != "table_or_list":
            continue
        group = by_group[case.article_group_id]
        passage = selected_passage(group, config, "structural")
        detail = details[group.group_id]
        xml = str(detail["selected_source_element_xml"])
        fragment_path = fragment_dir / f"{group.pmcid}-{case.case_id}.xml"
        fragment_path.parent.mkdir(parents=True, exist_ok=True)
        fragment_path.write_text(xml, encoding="utf-8", newline="\n")
        cases.append(
            {
                "case_id": case.case_id,
                "article_group_id": group.group_id,
                "pmid": group.pmid,
                "pmcid": group.pmcid,
                "stratum": "structural_challenge",
                "selected_source_ref": passage.source_ref,
                "selected_text_sha256": _sha(passage.text.encode("utf-8")),
                "ordered_passages": detail["ordered_passages"],
                "structures": [
                    value.model_dump(mode="json") for value in passage.structures
                ],
                "raw_source": detail["raw_source"],
                "source_element_xml": {
                    **_artifact(fragment_path),
                    "serialization": (
                        "ElementTree UTF-8 serialization of the source element; "
                        "exact source bytes remain in raw_source"
                    ),
                },
                "canonical_mapping": _canonical_mapping(passage),
            }
        )
    return {
        "schema_version": "campaign-2026-10-milestone-c-structure-sidecar-v1",
        "protocol_sha256": config.protocol_sha256,
        "packet_id": packet.packet_id,
        "packet_content_sha256": packet.content_sha256,
        "cases": cases,
    }


def _canonical_mapping(passage: SourcePassage) -> list[dict[str, object]]:
    children = [item for item in passage.structures[1:] if item.text.strip()]
    if not children:
        children = list(passage.structures)
    if not children:
        return [
            {
                "position": 0,
                "source_index": 0,
                "source_path": passage.source_ref,
                "passage_type": passage.source_kind,
                "text": passage.text,
                "canonical_start": 0,
            }
        ]
    mapping: list[dict[str, object]] = []
    cursor = 0
    for position, child in enumerate(children):
        text = child.text.strip()
        start = passage.text.find(text, cursor)
        if start < 0:
            raise FreshSamplingError(
                "structure child is not grounded in selected passage: "
                f"{child.source_path}"
            )
        mapping.append(
            {
                "position": position,
                "source_index": position,
                "source_path": child.source_path,
                "passage_type": child.kind,
                "text": text,
                "canonical_start": start,
            }
        )
        cursor = start + len(text)
    return mapping


def _build_clp_request(
    packet: Any, sidecar: dict[str, object], config: MilestoneCSampleConfig
) -> dict[str, object]:
    cases = _mapping_by_case(sidecar["cases"])
    documents = []
    not_applicable = []
    for case in packet.cases:
        if case.source_kind != "table_or_list":
            continue
        source = cases[case.case_id]
        heading = " ".join(case.section_heading.split()).strip(" :")
        if not _ABBR_HEADING.fullmatch(heading):
            not_applicable.append(
                {
                    "document_id": case.case_id,
                    "reason": "source section is not declared ABBR",
                    "section_heading": case.section_heading,
                }
            )
            continue
        xml_info = _mapping(source["source_element_xml"], "source element XML")
        xml = Path(str(xml_info["path"])).read_text(encoding="utf-8")
        mappings = source["canonical_mapping"]
        if not isinstance(mappings, list):
            raise TypeError("canonical mapping must be an array")
        structures = source["structures"]
        if not isinstance(structures, list):
            raise TypeError("sidecar structures must be an array")
        passages: list[dict[str, object]] = [
            {
                "position": 0,
                "source_index": -1,
                "source_offset": 0,
                "canonical_start": 0,
                "section_type": "ABBR",
                "passage_type": "title",
                "text": case.section_heading,
                "xml": None,
            }
        ]
        is_table = any(
            isinstance(value, Mapping) and value.get("kind") == "table"
            for value in structures
        )
        if is_table:
            passages.append(
                {
                    "position": 1,
                    "source_index": 0,
                    "source_offset": 0,
                    "canonical_start": 0,
                    "section_type": "TABLE",
                    "passage_type": "table",
                    "text": case.text,
                    "xml": xml,
                }
            )
        else:
            for position, value in enumerate(mappings, 1):
                item = _mapping(value, "canonical mapping item")
                passages.append(
                    {
                        "position": position,
                        "source_index": item["source_index"],
                        "source_offset": 0,
                        "canonical_start": item["canonical_start"],
                        "section_type": "ABBR",
                        "passage_type": "paragraph",
                        "text": item["text"],
                        "xml": xml if position == 1 else None,
                    }
                )
        documents.append(
            {
                "document_id": case.case_id,
                "source_filename": f"{source['pmcid']}.xml",
                "start_position": 0,
                "passages": passages,
            }
        )
    request_identity = {
        "protocol_sha256": config.protocol_sha256,
        "packet_content_sha256": packet.content_sha256,
        "documents": documents,
    }
    return {
        "schema_version": "clp-abbr-worker-request-v2",
        "request_id": f"milestone-c-rules-{_sha(_canonical(request_identity))[:20]}",
        **request_identity,
        "not_applicable": not_applicable,
    }


def validate_existing_sample(manifest_path: Path) -> dict[str, object]:
    """Replay hashes, packet identity, emptiness, and raw source integrity."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete_source_only_sample_frozen":
        raise FreshSamplingError("existing Milestone C manifest is not complete")
    for key in ("packet", "empty_state", "structure_sidecar", "clp_rules_only_request"):
        artifact = _mapping(manifest.get(key), key)
        path = Path(str(artifact["path"]))
        if _file_sha(path) != artifact["sha256"]:
            raise FreshSamplingError(f"existing Milestone C {key} hash mismatch")
    packet_info = _mapping(manifest["packet"], "packet")
    packet = read_blind_packet(Path(str(packet_info["path"])))
    assert_prediction_free(packet)
    state_info = _mapping(manifest["empty_state"], "empty state")
    state = AnnotationState.model_validate_json(
        Path(str(state_info["path"])).read_text(encoding="utf-8")
    )
    validate_annotation_state(packet.annotation_packet(), state)
    if state.annotations:
        raise FreshSamplingError("existing Milestone C state is no longer empty")
    for source in manifest["sources"]:
        for artifact in source["artifacts"]:
            path = Path(artifact["path"])
            if _file_sha(path) != artifact["sha256"]:
                raise FreshSamplingError(f"raw source hash mismatch: {path}")
    return cast(dict[str, object], manifest)


def _element_xml(payload: bytes, source_path: str) -> str:
    root = ET.fromstring(payload)
    article: ET.Element | None = root if _local(root.tag) == "article" else None
    if article is None:
        article = next(
            (child for child in root if _local(child.tag) == "article"), None
        )
    if article is None:
        raise FreshSamplingError("raw JATS has no primary article")
    for path, node in _pilot_source_walk(article):
        if path == source_path:
            return ET.tostring(node, encoding="unicode")
    raise FreshSamplingError(
        f"selected source path is absent from raw JATS: {source_path}"
    )


def _pilot_source_walk(article: ET.Element) -> Any:
    """Yield the body paths used by ``parse_pmc_jats``."""

    yield "article", article
    body = next((child for child in article if _local(child.tag) == "body"), None)
    if body is not None:
        yield "article/body", body
        yield from _walk_body(body, "article/body")


def _walk_body(root: ET.Element, path: str) -> Any:
    counts: dict[str, int] = {}
    for child in root:
        tag = _local(child.tag)
        counts[tag] = counts.get(tag, 0) + 1
        child_path = f"{path}/{tag}[{counts[tag]}]"
        yield child_path, child
        yield from _walk_body(child, child_path)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _fetch_url(database: str, identifier: str) -> str:
    query = urllib.parse.urlencode({"db": database, "id": identifier, "retmode": "xml"})
    return f"{NCBI_EFETCH}?{query}"


def _attempt(
    draw_index: int,
    stratum: str,
    pmcid: str,
    outcome: str,
    reason: str,
    pmid: str | None = None,
) -> dict[str, object]:
    return {
        "draw_index": draw_index,
        "stratum": stratum,
        "pmcid": pmcid,
        "pmid": pmid,
        "outcome": outcome,
        "reason": reason,
        "observed_at": _now(),
    }


def _source(
    stratum: str,
    group: FreshArticleGroup,
    license_evidence: dict[str, object],
    artifacts: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "stratum": stratum,
        "article_group_id": group.group_id,
        "pmcid": group.pmcid,
        "pmid": group.pmid,
        "title": group.title,
        "license": license_evidence,
        "artifacts": artifacts,
    }


def _write_raw(path: Path, payload: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return _artifact(path)


def _checkpoint(
    root: Path,
    started: str,
    attempts: list[dict[str, object]],
    representative: Any,
    structural: Any,
    budget: RequestBudget,
) -> None:
    _write_json(
        root / "acquisition-checkpoint.json",
        {
            "started_at": started,
            "attempts": attempts,
            "representative": [
                group.model_dump(mode="json") for group in representative
            ],
            "structural": [group.model_dump(mode="json") for group in structural],
            "limits": _limits(budget, 0),
        },
    )


def _limits(budget: RequestBudget, cache_hits: int) -> dict[str, object]:
    return {
        "metadata_requests": budget.metadata_requests,
        "http_attempts": budget.http_attempts,
        "response_cache_hits": cache_hits,
        "total_bytes": budget.total_bytes,
        "elapsed_seconds": budget.elapsed(),
        "reached": budget.reached,
    }


def _incomplete(
    config: MilestoneCSampleConfig,
    frame: dict[str, object],
    ledger: ExclusionLedger,
    attempts: list[dict[str, object]],
    representative: list[FreshArticleGroup],
    structural: list[FreshArticleGroup],
    budget: RequestBudget,
    cache_hits: int,
) -> dict[str, object]:
    return {
        "schema_version": "campaign-2026-10-milestone-c-source-manifest-v1",
        "status": "incomplete",
        "protocol_sha256": config.protocol_sha256,
        "frame": frame,
        "exclusions": ledger.model_dump(mode="json"),
        "attempts": attempts,
        "counts": {
            "representative_groups": len(representative),
            "structural_groups": len(structural),
        },
        "limits": _limits(budget, cache_hits),
    }


def _artifact(path: Path) -> dict[str, object]:
    return {
        "path": path.as_posix(),
        "sha256": _file_sha(path),
        "bytes": path.stat().st_size,
    }


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _mapping_by_case(value: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list):
        raise TypeError("sidecar cases must be an array")
    return {str(item["case_id"]): _mapping(item, "sidecar case") for item in value}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["acquire_milestone_c_sample", "validate_existing_sample"]
