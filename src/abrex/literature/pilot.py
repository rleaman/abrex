"""Bounded, reproducible orchestration for the T051 literature pilot."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from abrex.literature.pilot_methods import generate_candidates, run_methods
from abrex.literature.pilot_models import (
    Arm,
    AttemptRecord,
    HeuristicEvidence,
    InventoryRecord,
    LimitReport,
    PilotConfig,
    PilotManifest,
    PilotRecord,
    PilotSection,
    SourceArtifact,
    SourceComparison,
    StructureRecord,
    config_fingerprint,
    stable_id,
)
from abrex.literature.pilot_sampling import (
    BoundedClient,
    PilotLimitError,
    RequestBudget,
    deterministic_uid_draws,
    discover_uid_frame,
)
from abrex.literature.pilot_sources import (
    PilotSourceError,
    extract_cc_by_license,
    parse_bioc_xml,
    parse_pmc_jats,
    parse_pubmed_source,
)
from abrex.literature.pilot_sources import (
    _is_exact_cc_by as _source_is_exact_cc_by,
)

PILOT_SCHEMA_VERSION = "random-literature-pilot-v2"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BIOC_PMCOA = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml"


class PilotError(RuntimeError):
    """Raised when a pilot cannot produce a valid manifest."""


def _is_exact_cc_by(url: str | None, text: str | None) -> bool:
    """Compatibility wrapper for the source license policy."""
    return _source_is_exact_cc_by(url, text)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _artifact(
    path: Path,
    kind: Literal["jats_xml", "pubmed_xml", "bioc_xml"],
    url: str,
    payload: bytes,
) -> SourceArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return SourceArtifact(
        kind=kind,
        path=str(path),
        sha256=_sha(payload),
        bytes=len(payload),
        source_url=url,
        retrieved_at=_now(),
    )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _abstract_bioc(parsed: Any) -> bytes:
    values = [
        '<?xml version="1.0" encoding="UTF-8"?><collection><source>abrex</source>'
        "<date></date><key>t051</key><document>",
        f"<id>{_escape(parsed.pmid or parsed.title)}</id>",
    ]
    for section in parsed.sections:
        values.append(
            f'<passage><infon key="section_type">{_escape(section.source_kind)}</infon>'
            f"<text>{_escape(section.text)}</text></passage>"
        )
    values.append("</document></collection>")
    return "".join(values).encode("utf-8")


def _section_models(parsed: Any, article_id: str) -> tuple[PilotSection, ...]:
    result = []
    for index, source in enumerate(parsed.sections):
        result.append(
            PilotSection(
                section_id=source.section_id,
                document_id=f"{article_id}/{source.section_id}",
                heading=source.heading,
                source_kind=source.source_kind,
                canonical_text=source.text,
                canonical_text_sha256=_sha(source.text.encode("utf-8")),
                source_locator=source.source_locator,
                previous_section_id=parsed.sections[index - 1].section_id
                if index
                else None,
                next_section_id=parsed.sections[index + 1].section_id
                if index + 1 < len(parsed.sections)
                else None,
            )
        )
    return tuple(result)


def _record(
    parsed: Any,
    article_id: str,
    group: str,
    arm: Arm,
    url: str,
    artifacts: tuple[SourceArtifact, ...],
    license: Any = None,
) -> PilotRecord:
    structures = tuple(
        StructureRecord(
            structure_id=s.structure_id,
            kind=s.kind,
            text=s.text,
            source_path=s.source_path,
            section_id=s.section_id,
            parent_id=s.parent_id,
        )
        for s in parsed.structures
    )
    return PilotRecord(
        article_id=article_id,
        article_group_id=group,
        arm=arm,
        title=parsed.title,
        pmid=parsed.pmid,
        pmcid=parsed.pmcid,
        source_url=url,
        license=license,
        source_artifacts=artifacts,
        sections=_section_models(parsed, article_id),
        structures=structures,
        diagnostics=parsed.diagnostics,
    )


def _fetch_url(db: str, identifier: str) -> str:
    params = {"db": db, "id": identifier, "retmode": "xml"}
    return f"{NCBI_EFETCH}?{urllib.parse.urlencode(params)}"


def _attempt(
    arm: Arm,
    index: int,
    identifier: str,
    outcome: Literal["selected", "excluded", "failed"],
    reason: str,
    *,
    response_sha256: str | None = None,
    response_bytes: int | None = None,
    article_group_id: str | None = None,
) -> AttemptRecord:
    return AttemptRecord(
        arm=arm,
        draw_index=index,
        identifier=identifier,
        outcome=outcome,
        reason=reason,
        observed_at=_now(),
        response_sha256=response_sha256,
        response_bytes=response_bytes,
        article_group_id=article_group_id,
    )


def _run_record(
    record: PilotRecord, config: PilotConfig, runtime: Path
) -> tuple[PilotRecord, tuple[InventoryRecord, ...]]:
    sections = list(record.sections)
    outputs = run_methods(sections, config, runtime)
    updated = []
    inventories = []
    names = ("schwartz_hearst", "ab3p", "plodv2_pairing")
    for section in sections:
        structural, lexical = generate_candidates(section, ())
        current = PilotSection.model_validate(
            section.model_copy(
                update={
                    "method_outputs": outputs[section.document_id],
                    "structural_candidates": structural,
                    "lexical_candidates": lexical,
                }
            ).model_dump()
        )
        updated.append(current)
        methods = current.method_outputs
        complete = all(
            methods[n].status == "completed" and methods[n].coverage == "complete"
            for n in names
        )
        keys = {
            n: {
                (
                    p.short_form.start,
                    p.short_form.end,
                    p.long_form.start,
                    p.long_form.end,
                )
                for p in methods[n].pairs
            }
            for n in names
        }
        if not complete:
            category: str = "method_failure"
        elif not any(keys.values()):
            category = "all_primary_zero"
        elif len(set(map(frozenset, keys.values()))) == 1:
            category = "exact_agreement"
        else:
            relation_keys = {
                n: {(p.short_form.text, p.long_form.text) for p in methods[n].pairs}
                for n in names
            }
            category = (
                "boundary_disagreement"
                if len(set(map(frozenset, relation_keys.values()))) == 1
                else "relation_disagreement"
            )
        tokens = tuple(
            sorted(
                {
                    w.strip(".,;:()")
                    for w in section.canonical_text.split()
                    if 2 <= len(w.strip(".,;:()")) <= 12
                    and (w.isupper() or any(c.isdigit() for c in w))
                }
            )
        )
        heuristic = (
            HeuristicEvidence(
                name=config.abbreviation_heuristic, tokens=tokens, enriched=bool(tokens)
            )
            if category == "all_primary_zero"
            else None
        )
        inventories.append(
            InventoryRecord(
                inventory_id=stable_id(
                    "inventory", record.article_id, section.section_id, category
                ),
                article_id=record.article_id,
                section_id=section.section_id,
                canonical_text_sha256=section.canonical_text_sha256,
                category=cast(Any, category),
                pair_ids=tuple(p.pair_id for n in methods for p in methods[n].pairs),
                span_ids=tuple(s.span_id for n in methods for s in methods[n].spans),
                methods=tuple(methods),
                eligible_for_review=complete,
                heuristic=heuristic,
            )
        )
    return record.model_copy(update={"sections": tuple(updated)}), tuple(inventories)


def _comparison(record: PilotRecord, payload: bytes) -> SourceComparison:
    passages = parse_bioc_xml(payload)
    jats = [s.canonical_text for s in record.sections]
    bioc = [p.text for p in passages]
    normalized = {" ".join(v.split()) for v in bioc}
    return SourceComparison(
        article_id=record.article_id,
        jats_sha256=record.source_artifacts[0].sha256,
        bioc_sha256=_sha(payload),
        jats_section_count=len(jats),
        bioc_passage_count=len(bioc),
        exact_text_matches=sum(v in bioc for v in jats),
        normalized_text_matches=sum(" ".join(v.split()) in normalized for v in jats),
        unmatched_jats_sections=tuple(
            str(i) for i, v in enumerate(jats) if v not in bioc
        ),
        unmatched_bioc_passages=tuple(
            p.passage_id for p in passages if p.text not in jats
        ),
        jats_structure_counts={},
        observations=("BioC and JATS offsets are retained independently.",),
    )


def _write_checkpoint(
    root: Path,
    started: str,
    attempts: list[AttemptRecord],
    exclusions: list[dict[str, object]],
) -> None:
    """Persist acquisition progress after every draw for deterministic resume/audit."""
    checkpoint = {
        "schema_version": PILOT_SCHEMA_VERSION,
        "started_at": started,
        "attempts": [item.model_dump(mode="json") for item in attempts],
        "exclusions": exclusions,
    }
    (root / "pilot-checkpoint.json").write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_pilot(config: PilotConfig) -> dict[str, object]:
    """Run bounded random UID sampling and all configured method comparisons."""
    started = _now()
    root = Path(config.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    budget = RequestBudget()
    client = BoundedClient(config, budget)
    try:
        frames = [
            discover_uid_frame(db, client, ceiling=config.uid_search_ceiling)
            for db in ("pmc", "pubmed")
        ]
    except (PilotLimitError, OSError, ValueError) as error:
        raise PilotError(f"unable to verify UID frame: {error}") from error
    attempts: list[AttemptRecord] = []
    exclusions: list[dict[str, object]] = []
    records: list[PilotRecord] = []
    inventories: list[InventoryRecord] = []
    comparisons: list[SourceComparison] = []
    for arm, frame, target, maximum in (
        ("pmc_cc_by", frames[0], config.pmc_target, config.pmc_max_attempts),
        (
            "pubmed_abstract",
            frames[1],
            config.pubmed_target,
            config.pubmed_max_attempts,
        ),
    ):
        arm = cast(Arm, arm)
        selected = {r.article_group_id for r in records}
        for index, uid in enumerate(
            deterministic_uid_draws(config.seed, arm, frame.upper_bound, maximum)
        ):
            if sum(r.arm == arm for r in records) >= target:
                break
            identifier = f"PMC{uid}" if arm == "pmc_cc_by" else str(uid)
            db = "pmc" if arm == "pmc_cc_by" else "pubmed"
            url = _fetch_url(db, identifier)
            rec = None
            try:
                payload = client.get(url)
                if arm == "pmc_cc_by":
                    parsed = parse_pmc_jats(payload, identifier)
                    evidence = extract_cc_by_license(payload, identifier)
                    group = parsed.pmid or parsed.pmcid or identifier
                    if group in selected:
                        raise PilotSourceError("counterpart already selected")
                    bioc_url = f"{BIOC_PMCOA}/{identifier}/unicode"
                    bioc = client.get(bioc_url)
                    if b"[Error]" in bioc[:100]:
                        raise PilotSourceError("BioC unavailable")
                    artifacts = (
                        _artifact(
                            root / "raw/pmc" / f"{identifier}.xml",
                            "jats_xml",
                            url,
                            payload,
                        ),
                        _artifact(
                            root / "raw/pmc" / f"{identifier}.bioc.xml",
                            "bioc_xml",
                            bioc_url,
                            bioc,
                        ),
                    )
                    rec = _record(
                        parsed,
                        parsed.pmcid or identifier,
                        group,
                        arm,
                        f"https://pmc.ncbi.nlm.nih.gov/articles/{identifier}/",
                        artifacts,
                        evidence,
                    )
                    comparisons.append(_comparison(rec, bioc))
                else:
                    parsed = parse_pubmed_source(payload, identifier)
                    group = parsed.pmid or identifier
                    if group in selected:
                        raise PilotSourceError("pmc counterpart already selected")
                    bioc = _abstract_bioc(parsed)
                    artifacts = (
                        _artifact(
                            root / "raw/pubmed" / f"{identifier}.xml",
                            "pubmed_xml",
                            url,
                            payload,
                        ),
                        _artifact(
                            root / "raw/pubmed" / f"{identifier}.bioc.xml",
                            "bioc_xml",
                            "generated:pubmed-sections",
                            bioc,
                        ),
                    )
                    rec = _record(
                        parsed,
                        parsed.pmid or identifier,
                        group,
                        arm,
                        f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/",
                        artifacts,
                    )
                rec, inv = _run_record(rec, config, root / "runtime" / rec.article_id)
                records.append(rec)
                inventories.extend(inv)
                selected.add(group)
                attempts.append(
                    _attempt(
                        arm,
                        index,
                        identifier,
                        "selected",
                        "eligible",
                        response_sha256=_sha(payload),
                        response_bytes=len(payload),
                        article_group_id=group,
                    )
                )
            except (PilotSourceError, PilotLimitError, OSError, ValueError) as error:
                if rec is not None and rec not in records:
                    # Keep the selected source and its diagnostic context when a
                    # resolver or comparison fails; processing failure is not
                    # an exclusion and must never become an empty prediction.
                    records.append(rec)
                outcome = cast(
                    Literal["selected", "excluded", "failed"],
                    (
                        "failed"
                        if isinstance(error, PilotLimitError | OSError)
                        else "excluded"
                    ),
                )
                attempts.append(_attempt(arm, index, identifier, outcome, str(error)))
                exclusions.append(
                    {"arm": arm, "identifier": identifier, "reason": str(error)}
                )
                _write_checkpoint(root, started, attempts, exclusions)
            else:
                _write_checkpoint(root, started, attempts, exclusions)
    limits = LimitReport(
        metadata_requests=budget.metadata_requests,
        pmc_attempts=sum(a.arm == "pmc_cc_by" for a in attempts),
        pubmed_attempts=sum(a.arm == "pubmed_abstract" for a in attempts),
        total_bytes=budget.total_bytes,
        elapsed_seconds=budget.elapsed(),
        reached=tuple(budget.reached),
    )
    manifest = PilotManifest(
        run_id=stable_id("run", config_fingerprint(config), started),
        started_at=started,
        finished_at=_now(),
        config_sha256=config_fingerprint(config),
        protocol=config.model_dump(mode="json"),
        frames=tuple(frames),
        limits=limits,
        counts={
            "pmc_selected": sum(r.arm == "pmc_cc_by" for r in records),
            "pubmed_selected": sum(r.arm == "pubmed_abstract" for r in records),
            "records": len(records),
            "attempts": len(attempts),
            "exclusions": len(exclusions),
            "inventories": len(inventories),
        },
        attempts=tuple(attempts),
        records=tuple(records),
        inventories=tuple(inventories),
        source_comparisons=tuple(comparisons),
        limitations=tuple([f"excluded:{item['reason']}" for item in exclusions]),
    )
    manifest_payload = manifest.model_dump(mode="json")
    (root / "pilot-manifest.json").write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return manifest_payload


__all__ = ["PILOT_SCHEMA_VERSION", "PilotConfig", "PilotError", "run_pilot"]
