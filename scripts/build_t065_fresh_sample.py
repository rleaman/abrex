"""Acquire and package the frozen T065 prediction-blind source sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from abrex.config import load_config_layer
from abrex.literature.blind_review import write_blind_packet
from abrex.literature.fresh_sampling import (
    ExclusionLedger,
    FreshArticleGroup,
    FreshSamplingError,
    FrozenFreshConfig,
    SourcePassage,
    assert_prediction_free,
    build_fresh_packet,
    load_exclusion_ledger,
    segment_prose,
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
from abrex.literature.review_models import ReviewStructure, empty_annotation_state

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def main() -> int:
    """Run the source-only acquisition or validate an existing completed package."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/literature/T065-fresh-sample.yaml"),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    report = acquire_fresh_sample(config)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "complete" else 2


def acquire_fresh_sample(config: FrozenFreshConfig) -> dict[str, object]:
    """Retrieve eligible linked sources and publish the blind packet last."""

    root = Path(config.output_dir)
    delivery = Path(config.delivery_dir)
    manifest_path = delivery / "source-manifest-v1.json"
    if manifest_path.is_file():
        return _validate_existing(manifest_path)
    protocol_path = Path(config.protocol_path)
    protocol_bytes = protocol_path.read_bytes()
    if _sha(protocol_bytes) != config.protocol_sha256:
        raise FreshSamplingError("T063 protocol hash differs from frozen T065 config")
    protocol = json.loads(protocol_bytes)
    if protocol.get("status") != "approved_and_frozen":
        raise FreshSamplingError("T063 protocol is not approved and frozen")
    exclusion_paths = tuple(Path(value) for value in config.exclusion_paths)
    ledger = load_exclusion_ledger(exclusion_paths)

    started = _now()
    root.mkdir(parents=True, exist_ok=True)
    delivery.mkdir(parents=True, exist_ok=True)
    budget = RequestBudget()
    client = BoundedClient(cast(Any, config), budget)
    frame = discover_uid_frame("pmc", client, ceiling=config.uid_search_ceiling)
    attempts: list[dict[str, object]] = []
    groups: list[FreshArticleGroup] = []
    sources: list[dict[str, object]] = []
    draws = deterministic_uid_draws(
        config.seed,
        "t065-linked-pmc-groups",
        frame.upper_bound,
        config.maximum_attempts,
    )
    for draw_index, uid in enumerate(draws):
        if len(groups) >= config.article_groups:
            break
        pmcid = f"PMC{uid}"
        if ledger.excludes(pmcid=pmcid):
            attempts.append(_attempt(draw_index, pmcid, "excluded", "prior-pmcid"))
            continue
        pmc_url = _fetch_url("pmc", pmcid)
        try:
            pmc_payload = client.get(pmc_url)
            parsed_pmc = parse_pmc_jats(pmc_payload, pmcid)
            license_evidence = extract_cc_by_license(pmc_payload, pmcid)
            pmid = parsed_pmc.pmid
            if pmid is None:
                raise PilotSourceError("primary article has no linked PMID")
            if ledger.excludes(pmid=pmid, pmcid=parsed_pmc.pmcid):
                raise PilotSourceError("linked article group is in prior evidence")
            pubmed_url = _fetch_url("pubmed", pmid)
            pubmed_payload = client.get(pubmed_url)
            parsed_pubmed = parse_pubmed_source(pubmed_payload, pmid)
            group = _group_from_sources(
                parsed_pmc,
                parsed_pubmed,
                config,
                pmcid,
                pmid,
            )
            _check_group_capacity(group, len(groups), config)
        except PilotLimitError as error:
            attempts.append(_attempt(draw_index, pmcid, "failed", str(error)))
            budget.reached.append("acquisition_stopped")
            break
        except (OSError, PilotSourceError, FreshSamplingError, ValueError) as error:
            attempts.append(_attempt(draw_index, pmcid, "excluded", str(error)))
            _write_checkpoint(root, started, attempts, groups, budget)
            continue

        pmc_artifact = _write_raw(root / "raw" / f"{pmcid}.xml", pmc_payload)
        pubmed_artifact = _write_raw(root / "raw" / f"PMID{pmid}.xml", pubmed_payload)
        groups.append(group)
        attempts.append(
            _attempt(
                draw_index,
                pmcid,
                "selected",
                "eligible-source-structure",
                pmid=pmid,
                response_sha256=_sha(pmc_payload),
                response_bytes=len(pmc_payload) + len(pubmed_payload),
            )
        )
        sources.append(
            {
                "article_group_id": pmid,
                "pmcid": pmcid,
                "pmid": pmid,
                "title": parsed_pmc.title,
                "license": license_evidence.model_dump(mode="json"),
                "artifacts": [pmc_artifact, pubmed_artifact],
            }
        )
        _write_checkpoint(root, started, attempts, groups, budget)

    status = "complete" if len(groups) == config.article_groups else "incomplete"
    if status != "complete":
        report = _incomplete_report(config, frame, ledger, attempts, groups, budget)
        _write_json(delivery / "incomplete-source-manifest.json", report)
        return report

    packet = build_fresh_packet(tuple(groups), config)
    assert_prediction_free(packet)
    packet_path = delivery / "review-packet-blind-v1.json"
    state_path = delivery / "review-packet-blind-v1.annotations.json"
    write_blind_packet(packet, packet_path)
    state = empty_annotation_state(packet.annotation_packet())
    _write_json(state_path, state.model_dump(mode="json"))
    manifest = {
        "schema_version": "t065-source-manifest-v1",
        "status": status,
        "started_at": started,
        "finished_at": _now(),
        "protocol": {
            "path": config.protocol_path,
            "sha256": config.protocol_sha256,
            "approval_response": protocol["approval"]["response"],
        },
        "config": config.model_dump(mode="json"),
        "config_sha256": _sha(
            json.dumps(
                config.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ),
        "frame": frame.model_dump(mode="json"),
        "exclusions": ledger.model_dump(mode="json"),
        "attempts": attempts,
        "sources": sources,
        "limits": {
            "metadata_requests": budget.metadata_requests,
            "total_bytes": budget.total_bytes,
            "elapsed_seconds": budget.elapsed(),
            "reached": budget.reached,
        },
        "counts": {
            "attempts": len(attempts),
            "excluded": sum(item["outcome"] == "excluded" for item in attempts),
            "failed": sum(item["outcome"] == "failed" for item in attempts),
            "article_groups": len(groups),
            "cases": len(packet.cases),
            "pmc_prose": sum(case.source_kind == "pmc_prose" for case in packet.cases),
            "pubmed_abstract": sum(
                case.source_kind == "pubmed_abstract" for case in packet.cases
            ),
            "table_or_list": sum(
                case.source_kind == "table_or_list" for case in packet.cases
            ),
        },
        "sampling": {
            "denominator_article_draws": len(attempts),
            "targets": {
                "article_groups": config.article_groups,
                "pmc_prose": config.pmc_prose_passages,
                "pubmed_abstract": config.pubmed_abstract_passages,
                "table_or_list": config.table_or_list_sections,
            },
            "selected": {
                "article_groups": len(groups),
                "pmc_prose": config.pmc_prose_passages,
                "pubmed_abstract": config.pubmed_abstract_passages,
                "table_or_list": config.table_or_list_sections,
            },
            "shortages": {
                "article_groups": 0,
                "pmc_prose": 0,
                "pubmed_abstract": 0,
                "table_or_list": 0,
            },
            "replacement_rule": protocol["prefilled_recommendation"]["sample"][
                "acquisition_limits"
            ]["replacement_rule"],
            "selection_inputs": [
                "seeded numeric PMC UID order",
                "exact CC BY license evidence",
                "linked PMID/PMCID identity",
                "source type and structural table/list presence",
                "frozen source-length passage segmentation",
            ],
        },
        "packet": {
            "path": packet_path.as_posix(),
            "packet_id": packet.packet_id,
            "content_sha256": packet.content_sha256,
            "file_sha256": _file_sha(packet_path),
        },
        "empty_state": {
            "path": state_path.as_posix(),
            "file_sha256": _file_sha(state_path),
            "annotation_count": 0,
        },
        "blindness": {
            "evaluated_methods_run": False,
            "candidate_generators_run": False,
            "token_enrichment_used": False,
            "predictions_exposed": False,
            "incidental_exposure": [],
        },
    }
    _write_json(manifest_path, manifest)
    return manifest


def _load_config(path: Path) -> FrozenFreshConfig:
    raw = load_config_layer(path)
    section = raw.get("fresh_sample")
    if not isinstance(section, Mapping):
        raise FreshSamplingError("T065 config requires a fresh_sample mapping")
    return FrozenFreshConfig.model_validate(section)


def _group_from_sources(
    pmc: ParsedPilotArticle,
    pubmed: ParsedPilotArticle,
    config: FrozenFreshConfig,
    pmcid: str,
    pmid: str,
) -> FreshArticleGroup:
    pmc_prose = tuple(
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
    abstract = tuple(
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
    structured = _structured_passages(pmc, config.structured_maximum_chars)
    return FreshArticleGroup(
        group_id=pmid,
        pmid=pmid,
        pmcid=pmcid,
        title=pmc.title,
        pmc_source_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        pubmed_source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        pmc_prose=pmc_prose,
        pubmed_abstract=abstract,
        structured=structured,
    )


def _structured_passages(
    parsed: ParsedPilotArticle, maximum_chars: int
) -> tuple[SourcePassage, ...]:
    result: list[SourcePassage] = []
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
        structures = (parent,) + children
        result.append(
            SourcePassage(
                source_ref=parent.source_path,
                heading="Table or list",
                source_kind="table_or_list",
                text=text,
                structures=tuple(
                    ReviewStructure(
                        kind=item.kind,
                        text=item.text,
                        source_path=item.source_path,
                    )
                    for item in structures
                ),
            )
        )
    return tuple(result)


def _check_group_capacity(
    group: FreshArticleGroup, group_index: int, config: FrozenFreshConfig
) -> None:
    pmc_needed = 2 if group_index < config.article_groups // 2 else 1
    abstract_needed = config.maximum_items_per_group - pmc_needed - 1
    if len(group.pmc_prose) < pmc_needed:
        raise FreshSamplingError("insufficient source-derived PMC prose passages")
    if len(group.pubmed_abstract) < abstract_needed:
        raise FreshSamplingError("insufficient source-derived abstract passages")
    if not group.structured:
        raise FreshSamplingError("no eligible table/list structure")


def _fetch_url(database: str, identifier: str) -> str:
    query = urllib.parse.urlencode({"db": database, "id": identifier, "retmode": "xml"})
    return f"{NCBI_EFETCH}?{query}"


def _attempt(
    draw_index: int,
    pmcid: str,
    outcome: str,
    reason: str,
    *,
    pmid: str | None = None,
    response_sha256: str | None = None,
    response_bytes: int | None = None,
) -> dict[str, object]:
    return {
        "draw_index": draw_index,
        "pmcid": pmcid,
        "pmid": pmid,
        "outcome": outcome,
        "reason": reason,
        "response_sha256": response_sha256,
        "response_bytes": response_bytes,
        "observed_at": _now(),
    }


def _write_raw(path: Path, payload: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": path.as_posix(), "sha256": _sha(payload), "bytes": len(payload)}


def _write_checkpoint(
    root: Path,
    started: str,
    attempts: list[dict[str, object]],
    groups: list[FreshArticleGroup],
    budget: RequestBudget,
) -> None:
    _write_json(
        root / "acquisition-checkpoint.json",
        {
            "started_at": started,
            "attempts": attempts,
            "groups": [group.model_dump(mode="json") for group in groups],
            "limits": {
                "metadata_requests": budget.metadata_requests,
                "total_bytes": budget.total_bytes,
                "elapsed_seconds": budget.elapsed(),
                "reached": budget.reached,
            },
        },
    )


def _incomplete_report(
    config: FrozenFreshConfig,
    frame: Any,
    ledger: ExclusionLedger,
    attempts: list[dict[str, object]],
    groups: list[FreshArticleGroup],
    budget: RequestBudget,
) -> dict[str, object]:
    return {
        "schema_version": "t065-source-manifest-v1",
        "status": "incomplete",
        "protocol_sha256": config.protocol_sha256,
        "frame": frame.model_dump(mode="json"),
        "exclusions": ledger.model_dump(mode="json"),
        "attempts": attempts,
        "counts": {"article_groups": len(groups), "attempts": len(attempts)},
        "limits": {
            "metadata_requests": budget.metadata_requests,
            "total_bytes": budget.total_bytes,
            "elapsed_seconds": budget.elapsed(),
            "reached": budget.reached,
        },
    }


def _validate_existing(path: Path) -> dict[str, object]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    from abrex.literature.blind_review import read_blind_packet
    from abrex.literature.review_models import (
        AnnotationState,
        validate_annotation_state,
    )

    for key in ("packet", "empty_state"):
        artifact = manifest[key]
        artifact_path = Path(artifact["path"])
        if _file_sha(artifact_path) != artifact["file_sha256"]:
            raise FreshSamplingError(f"existing T065 {key} hash mismatch")
    packet = read_blind_packet(Path(manifest["packet"]["path"]))
    assert_prediction_free(packet)
    state = AnnotationState.model_validate_json(
        Path(manifest["empty_state"]["path"]).read_text(encoding="utf-8")
    )
    validate_annotation_state(packet.annotation_packet(), state)
    if state.annotations:
        raise FreshSamplingError("existing T065 state is no longer empty")
    for source in manifest["sources"]:
        for artifact in source["artifacts"]:
            artifact_path = Path(artifact["path"])
            if _file_sha(artifact_path) != artifact["sha256"]:
                raise FreshSamplingError(
                    f"existing T065 raw source hash mismatch: {artifact_path}"
                )
    return cast(dict[str, object], manifest)


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


if __name__ == "__main__":
    raise SystemExit(main())
