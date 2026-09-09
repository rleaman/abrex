"""Durable JSON state and BioC entity/relation interchange for T052."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from abrex.literature.review_models import (
    AnnotationState,
    AnnotationSubmission,
    CaseSubmission,
    DecisionOrigin,
    DecisionSnapshot,
    MissedStatus,
    PairDecision,
    PairStatus,
    ReviewError,
    ReviewPacket,
    ReviewSpan,
    apply_submission,
    empty_annotation_state,
    fingerprint,
    validate_annotation_state,
    validate_snapshot,
    validate_span,
)


def read_annotation_state(packet: ReviewPacket, path: Path) -> AnnotationState:
    if not path.exists():
        return empty_annotation_state(packet)
    try:
        state = AnnotationState.model_validate_json(path.read_text(encoding="utf-8"))
        validate_annotation_state(packet, state)
        return state
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, ReviewError):
            raise
        raise ReviewError(f"invalid annotation state: {error}") from error


def write_annotation_state(state: AnnotationState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        state.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def _infon(parent: ET.Element, key: str, value: object) -> None:
    ET.SubElement(parent, "infon", {"key": key}).text = str(value)


def _infons(parent: ET.Element) -> dict[str, str]:
    return {
        str(node.get("key")): node.text or ""
        for node in parent.findall("infon")
        if node.get("key")
    }


def _semantics(state: AnnotationState) -> dict[str, object]:
    return {
        case_id: annotation.current.model_dump(mode="json")
        for case_id, annotation in sorted(state.annotations.items())
    }


def write_bioc_xml(
    packet: ReviewPacket, path: Path, state: AnnotationState | None = None
) -> None:
    """Write BioC XML with endpoints, relations, statuses, provenance, and history."""
    resolved = state or empty_annotation_state(packet)
    validate_annotation_state(packet, resolved)
    root = ET.Element("collection")
    ET.SubElement(root, "source").text = "ABREX T052 local reviewer"
    ET.SubElement(root, "date").text = datetime.now(UTC).date().isoformat()
    ET.SubElement(root, "key").text = packet.packet_id
    _infon(root, "abrex_schema_version", resolved.schema_version)
    _infon(root, "abrex_packet_id", packet.packet_id)
    _infon(root, "abrex_packet_content_sha256", packet.content_sha256)
    _infon(root, "abrex_semantic_sha256", fingerprint(_semantics(resolved)))
    _infon(
        root,
        "abrex_annotation_state",
        json.dumps(
            resolved.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        ),
    )
    for case in packet.cases:
        document = ET.SubElement(root, "document")
        ET.SubElement(document, "id").text = case.case_id
        for key, value in (
            ("article_id", case.article_id),
            ("section_id", case.section_id),
            ("canonical_text_sha256", case.canonical_text_sha256),
        ):
            _infon(document, key, value)
        passage = ET.SubElement(document, "passage")
        annotation = resolved.annotations.get(case.case_id)
        snapshot = annotation.current if annotation is not None else DecisionSnapshot()
        _infon(passage, "type", "review_passage")
        _infon(passage, "case_id", case.case_id)
        _infon(passage, "missed_definition", snapshot.missed_definition)
        _infon(passage, "notes", snapshot.notes)
        ET.SubElement(passage, "offset").text = str(case.passage_start)
        ET.SubElement(passage, "text").text = case.text
        for pair in snapshot.pairs:
            endpoint_ids: list[tuple[str, str]] = []
            for role, span in (
                ("short_form", pair.short_form),
                ("long_form", pair.long_form),
            ):
                if span is None:
                    continue
                endpoint_id = f"{pair.decision_id}-{role}"
                annotation_node = ET.SubElement(
                    passage, "annotation", {"id": endpoint_id}
                )
                _infon(annotation_node, "type", role)
                _infon(annotation_node, "decision_id", pair.decision_id)
                ET.SubElement(
                    annotation_node,
                    "location",
                    {
                        "offset": str(case.passage_start + span.start),
                        "length": str(span.end - span.start),
                    },
                )
                ET.SubElement(annotation_node, "text").text = span.text
                endpoint_ids.append((role, endpoint_id))
            relation = ET.SubElement(passage, "relation", {"id": pair.decision_id})
            _infon(
                relation,
                "type",
                "abbreviation_definition"
                if pair.proposal_kind == "definition"
                else "span_judgment",
            )
            _infon(relation, "proposal_kind", pair.proposal_kind)
            _infon(relation, "status", pair.status)
            _infon(relation, "origin", pair.origin)
            _infon(relation, "suggestion_id", pair.suggestion_id or "")
            _infon(relation, "notes", pair.notes)
            for role, endpoint_id in endpoint_ids:
                ET.SubElement(relation, "node", {"refid": endpoint_id, "role": role})
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _parse_semantics(
    packet: ReviewPacket, root: ET.Element
) -> dict[str, DecisionSnapshot]:
    case_map = {case.case_id: case for case in packet.cases}
    decisions: dict[str, DecisionSnapshot] = {}
    for document in root.findall("document"):
        case_id = document.findtext("id") or ""
        if case_id in decisions:
            raise ReviewError(f"BioC contains duplicate case ID {case_id}")
        case = case_map.get(case_id)
        if case is None:
            raise ReviewError(f"BioC contains unknown case ID {case_id}")
        passages = document.findall("passage")
        if len(passages) != 1:
            raise ReviewError(f"BioC case {case_id} must contain exactly one passage")
        passage = passages[0]
        if (
            int(passage.findtext("offset") or "0") != case.passage_start
            or passage.findtext("text") != case.text
        ):
            raise ReviewError(f"BioC passage identity mismatch for {case_id}")
        annotations: dict[str, tuple[str, ReviewSpan]] = {}
        for node in passage.findall("annotation"):
            annotation_id, info, location = (
                node.get("id") or "",
                _infons(node),
                node.find("location"),
            )
            if not annotation_id or annotation_id in annotations:
                raise ReviewError(
                    f"BioC contains duplicate or empty annotation ID {annotation_id}"
                )
            if location is None:
                raise ReviewError(f"BioC annotation {annotation_id} has no location")
            start = int(location.get("offset", "-1")) - case.passage_start
            length = int(location.get("length", "-1"))
            span = ReviewSpan(
                start=start, end=start + length, text=node.findtext("text") or ""
            )
            validate_span(span, case.text, f"BioC annotation {annotation_id}")
            annotations[annotation_id] = (info.get("type", ""), span)
        pairs: list[PairDecision] = []
        relation_ids: set[str] = set()
        referenced_annotations: set[str] = set()
        for relation in passage.findall("relation"):
            relation_id = relation.get("id") or ""
            if not relation_id or relation_id in relation_ids:
                raise ReviewError(
                    f"BioC contains duplicate or empty relation ID {relation_id}"
                )
            relation_ids.add(relation_id)
            info, endpoints = _infons(relation), {}
            for node in relation.findall("node"):
                refid, role = node.get("refid") or "", node.get("role") or ""
                if role in endpoints:
                    raise ReviewError(f"BioC relation has duplicate {role} endpoint")
                endpoint = annotations.get(refid)
                if endpoint is None or endpoint[0] != role:
                    raise ReviewError(
                        f"BioC relation has invalid {role} endpoint {refid}"
                    )
                endpoints[role] = endpoint[1]
                referenced_annotations.add(refid)
            pairs.append(
                PairDecision(
                    decision_id=relation_id,
                    suggestion_id=info.get("suggestion_id") or None,
                    proposal_kind=cast(
                        Literal["definition", "span"],
                        info.get("proposal_kind", "definition"),
                    ),
                    status=cast(PairStatus, info.get("status", "unreviewed")),
                    short_form=endpoints.get("short_form"),
                    long_form=endpoints.get("long_form"),
                    origin=cast(DecisionOrigin, info.get("origin", "added")),
                    notes=info.get("notes", ""),
                )
            )
        if referenced_annotations != set(annotations):
            raise ReviewError("BioC contains an unreferenced annotation")
        info = _infons(passage)
        snapshot = DecisionSnapshot(
            pairs=tuple(pairs),
            missed_definition=cast(
                MissedStatus, info.get("missed_definition", "unreviewed")
            ),
            notes=info.get("notes", ""),
        )
        validate_snapshot(case, snapshot)
        if snapshot != DecisionSnapshot():
            decisions[case_id] = snapshot
    return decisions


def import_bioc_xml(
    packet: ReviewPacket, payload: bytes, existing: AnnotationState | None = None
) -> AnnotationState:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise ReviewError(f"invalid BioC XML: {error}") from error
    info = _infons(root)
    if (
        info.get("abrex_packet_id") != packet.packet_id
        or info.get("abrex_packet_content_sha256") != packet.content_sha256
    ):
        raise ReviewError("BioC packet/content identity mismatch")
    parsed = _parse_semantics(packet, root)
    embedded_raw = info.get("abrex_annotation_state")
    if embedded_raw:
        try:
            embedded = AnnotationState.model_validate_json(embedded_raw)
            validate_annotation_state(packet, embedded)
        except ValueError as error:
            raise ReviewError(
                f"invalid embedded annotation sidecar: {error}"
            ) from error
        embedded_semantics = {
            case_id: item.current for case_id, item in embedded.annotations.items()
        }
        parsed_json = {
            case_id: snapshot.model_dump(mode="json")
            for case_id, snapshot in parsed.items()
        }
        if parsed == embedded_semantics and fingerprint(parsed_json) == info.get(
            "abrex_semantic_sha256"
        ):
            return embedded
    state = existing or empty_annotation_state(packet)
    submissions = {
        case_id: CaseSubmission(
            expected_revision=state.annotations[case_id].revision
            if case_id in state.annotations
            else 0,
            decision=snapshot,
        )
        for case_id, snapshot in parsed.items()
    }
    return apply_submission(
        packet,
        state,
        AnnotationSubmission(
            packet_id=packet.packet_id,
            packet_content_sha256=packet.content_sha256,
            current_case_id=state.current_case_id,
            annotations=submissions,
        ),
        source="bioc_import",
    )
