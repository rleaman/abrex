"""Deterministic T052 packet selection from T051 section inventories."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

from abrex.literature.review_models import (
    PRIMARY_METHODS,
    ReviewCase,
    ReviewError,
    ReviewPacket,
    ReviewSelection,
    ReviewSpan,
    ReviewStructure,
    ReviewSuggestion,
    fingerprint,
    packet_identity_payload,
    validate_packet_identity,
    validate_span,
)

TARGETS = {"disagreement": 30, "agreement": 10, "enriched_zero": 15, "uniform_zero": 5}
DIAGNOSTIC_BUDGET = 60


def _sections(
    manifest: Mapping[str, object],
) -> tuple[
    dict[tuple[str, str], Mapping[str, object]], dict[str, Mapping[str, object]]
]:
    section_index: dict[tuple[str, str], Mapping[str, object]] = {}
    records: dict[str, Mapping[str, object]] = {}
    raw_records = manifest.get("records")
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, str | bytes):
        raise ReviewError("pilot manifest records must be an array")
    for record in raw_records:
        if not isinstance(record, Mapping):
            raise ReviewError("pilot records must be objects")
        article_id = str(record.get("article_id", ""))
        if not article_id:
            raise ReviewError("pilot record is missing article_id")
        if article_id in records:
            raise ReviewError(f"duplicate article identity {article_id}")
        records[article_id] = record
        raw_sections = record.get("sections")
        if not isinstance(raw_sections, Sequence) or isinstance(
            raw_sections, str | bytes
        ):
            raise ReviewError(f"record {article_id} sections must be an array")
        for section in raw_sections:
            if not isinstance(section, Mapping):
                raise ReviewError(f"record {article_id} contains an invalid section")
            section_id = str(section.get("section_id", ""))
            text, digest = (
                section.get("canonical_text"),
                section.get("canonical_text_sha256"),
            )
            if (
                not section_id
                or not isinstance(text, str)
                or not isinstance(digest, str)
            ):
                raise ReviewError(f"record {article_id} has an incomplete section")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
                raise ReviewError(
                    f"canonical text hash mismatch for {article_id}/{section_id}"
                )
            key = (article_id, section_id)
            if key in section_index:
                raise ReviewError(
                    f"duplicate section identity {article_id}/{section_id}"
                )
            section_index[key] = section
    return section_index, records


def _inventory_rows(manifest: Mapping[str, object]) -> list[Mapping[str, object]]:
    inventories = manifest.get("inventories")
    if isinstance(inventories, Mapping):
        rows: list[Mapping[str, object]] = []
        for value in inventories.values():
            if isinstance(value, Sequence) and not isinstance(value, str | bytes):
                rows.extend(item for item in value if isinstance(item, Mapping))
        return rows
    if isinstance(inventories, Sequence) and not isinstance(inventories, str | bytes):
        return [item for item in inventories if isinstance(item, Mapping)]
    raise ReviewError(
        "pilot manifest inventories must be an array or mapping of arrays"
    )


def _outputs(section: Mapping[str, object]) -> Mapping[str, object]:
    value = section.get("method_outputs")
    if not isinstance(value, Mapping):
        raise ReviewError("section method_outputs must be an object")
    return value


def _valid_zero(section: Mapping[str, object]) -> bool:
    outputs = _outputs(section)
    for method in PRIMARY_METHODS:
        value = outputs.get(method)
        if (
            not isinstance(value, Mapping)
            or value.get("status") != "completed"
            or value.get("coverage") != "complete"
        ):
            return False
        pairs = value.get("pairs")
        if not isinstance(pairs, Sequence) or isinstance(pairs, str | bytes) or pairs:
            return False
    return True


def _enriched(inventory: Mapping[str, object]) -> bool:
    value = inventory.get("heuristic")
    if not isinstance(value, Mapping):
        return False
    for key in ("matched", "abbreviation_like", "eligible", "has_candidate"):
        if isinstance(value.get(key), bool):
            return bool(value[key])
    for key in ("matches", "tokens", "candidates"):
        entries = value.get(key)
        if isinstance(entries, Sequence) and not isinstance(entries, str | bytes):
            return bool(entries)
    return False


def _stratum(
    inventory: Mapping[str, object], section: Mapping[str, object]
) -> str | None:
    if inventory.get("category") == "method_failure":
        return "diagnostic"
    if inventory.get("eligible_for_review") is not True:
        return None
    category = str(inventory.get("category", ""))
    if category == "exact_agreement":
        return "agreement"
    if category in {"relation_disagreement", "boundary_disagreement", "unpaired_span"}:
        return "disagreement"
    if category == "all_primary_zero" and _valid_zero(section):
        return "enriched_zero" if _enriched(inventory) else "zero_pool"
    return None


def _rank(seed: int, inventory_id: str) -> str:
    return hashlib.sha256(f"{seed}:{inventory_id}".encode()).hexdigest()


def _select(
    pool: Sequence[Mapping[str, object]],
    target: int,
    seed: int,
    article_counts: dict[str, int],
    cap: int,
    *,
    prefer_predictions: bool = False,
) -> list[Mapping[str, object]]:
    arms: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for item in pool:
        arms[str(item["_arm"])].append(item)
    for values in arms.values():
        values.sort(
            key=lambda item: (
                not item.get("pair_ids") and not item.get("span_ids")
                if prefer_predictions
                else False,
                _rank(seed, str(item["inventory_id"])),
            )
        )
    picked: list[Mapping[str, object]] = []
    arm_counts: Counter[str] = Counter()
    while len(picked) < target:
        available = [
            arm
            for arm, values in arms.items()
            if any(
                article_counts.get(
                    str(item.get("article_group_id", item["article_id"])), 0
                )
                < cap
                for item in values
            )
        ]
        if not available:
            break
        arm = min(available, key=lambda value: (arm_counts[value], value))
        index = next(
            i
            for i, item in enumerate(arms[arm])
            if article_counts.get(
                str(item.get("article_group_id", item["article_id"])), 0
            )
            < cap
        )
        item = arms[arm].pop(index)
        article_id = str(item.get("article_group_id", item["article_id"]))
        article_counts[article_id] = article_counts.get(article_id, 0) + 1
        arm_counts[arm] += 1
        picked.append(item)
    return picked


def _raw_span(value: object, text: str, label: str) -> ReviewSpan | None:
    if not isinstance(value, Mapping):
        return None
    try:
        span = ReviewSpan.model_validate(
            {key: value[key] for key in ("start", "end", "text") if key in value}
        )
        validate_span(span, text, label)
    except ValueError as error:
        raise ReviewError(f"invalid {label}: {error}") from error
    return span


def _predictions(
    section: Mapping[str, object], inventory: Mapping[str, object]
) -> tuple[
    list[tuple[str, Mapping[str, object], Mapping[str, object]]],
    list[tuple[str, Mapping[str, object], Mapping[str, object]]],
]:
    pair_ids = {
        str(value) for value in cast(Sequence[object], inventory.get("pair_ids", []))
    }
    span_ids = {
        str(value) for value in cast(Sequence[object], inventory.get("span_ids", []))
    }
    pairs: list[tuple[str, Mapping[str, object], Mapping[str, object]]] = []
    spans: list[tuple[str, Mapping[str, object], Mapping[str, object]]] = []
    for key, output in _outputs(section).items():
        if not isinstance(output, Mapping):
            continue
        method_id = str(output.get("method_id", key))
        for raw in cast(Sequence[object], output.get("pairs", [])):
            if isinstance(raw, Mapping) and str(raw.get("pair_id")) in pair_ids:
                pairs.append((method_id, output, raw))
        for raw in cast(Sequence[object], output.get("spans", [])):
            if isinstance(raw, Mapping) and str(raw.get("span_id")) in span_ids:
                spans.append((method_id, output, raw))
    found = {str(raw.get("pair_id")) for _, _, raw in pairs} | {
        str(raw.get("span_id")) for _, _, raw in spans
    }
    missing = sorted((pair_ids | span_ids) - found)
    if missing:
        raise ReviewError(
            f"inventory {inventory.get('inventory_id')} references missing "
            f"predictions: {missing}"
        )
    return pairs, spans


def _bounds(
    text: str, spans: Sequence[ReviewSpan], inventory_id: str, max_chars: int = 3200
) -> tuple[int, int]:
    if len(text) <= max_chars:
        return 0, len(text)
    if spans:
        center = (
            min(span.start for span in spans) + max(span.end for span in spans)
        ) // 2
    else:
        center = (
            int(_rank(0, inventory_id)[:12], 16) % (len(text) - max_chars + 1)
            + max_chars // 2
        )
    start = max(0, min(len(text) - max_chars, center - max_chars // 2))
    end = min(len(text), start + max_chars)
    left = text.rfind("\n\n", max(0, start - 240), start + 1)
    right = text.find("\n\n", end, min(len(text), end + 240))
    return (left + 2 if left >= 0 else start, right if right >= 0 else end)


def _case(
    inventory: Mapping[str, object],
    section: Mapping[str, object],
    record: Mapping[str, object],
    category: str,
    manifest: Mapping[str, object],
) -> ReviewCase:
    section_text = str(section["canonical_text"])
    pairs, independent = _predictions(section, inventory)
    all_spans = [
        span
        for _, _, raw in pairs
        for role in ("short_form", "long_form")
        if (span := _raw_span(raw.get(role), section_text, role))
    ]
    all_spans += [
        span
        for _, _, raw in independent
        if (span := _raw_span(raw, section_text, "independent span"))
    ]
    start, end = _bounds(section_text, all_spans, str(inventory["inventory_id"]))
    passage = section_text[start:end]
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    raw_items: list[
        tuple[str, Mapping[str, object], ReviewSpan | None, ReviewSpan | None, str, str]
    ] = []
    for method, output, raw in pairs:
        raw_items.append(
            (
                method,
                output,
                _raw_span(raw.get("short_form"), section_text, "short form"),
                _raw_span(raw.get("long_form"), section_text, "long form"),
                str(raw["pair_id"]),
                "pair",
            )
        )
    for method, output, raw in independent:
        span = _raw_span(raw, section_text, "independent span")
        raw_items.append(
            (
                method,
                output,
                span if raw.get("label") == "SF" else None,
                span if raw.get("label") == "LF" else None,
                str(raw["span_id"]),
                "span",
            )
        )
    for method, output, sf, lf, source_id, source_type in raw_items:
        key = (
            sf.start if sf else None,
            sf.end if sf else None,
            sf.text if sf else None,
            lf.start if lf else None,
            lf.end if lf else None,
            lf.text if lf else None,
        )
        entry = grouped.setdefault(
            key,
            {
                "sf": sf,
                "lf": lf,
                "pair_ids": [],
                "span_ids": [],
                "methods": [],
                "provenance": [],
            },
        )
        cast(
            list[str], entry["pair_ids" if source_type == "pair" else "span_ids"]
        ).append(source_id)
        cast(list[str], entry["methods"]).append(method)
        cast(list[dict[str, object]], entry["provenance"]).append(
            {
                "method_id": method,
                "identity": output.get("identity"),
                "version": output.get("version"),
            }
        )
    suggestions: list[ReviewSuggestion] = []
    for entry in grouped.values():
        sf0, lf0 = (
            cast(ReviewSpan | None, entry["sf"]),
            cast(ReviewSpan | None, entry["lf"]),
        )
        if any(
            span and not (start <= span.start and span.end <= end)
            for span in (sf0, lf0)
        ):
            raise ReviewError("selected prediction falls outside its bounded passage")
        sf = (
            ReviewSpan(start=sf0.start - start, end=sf0.end - start, text=sf0.text)
            if sf0
            else None
        )
        lf = (
            ReviewSpan(start=lf0.start - start, end=lf0.end - start, text=lf0.text)
            if lf0
            else None
        )
        suggestion_id = (
            "suggestion-"
            + fingerprint(
                {
                    "sf": sf.model_dump() if sf else None,
                    "lf": lf.model_dump() if lf else None,
                }
            )[:16]
        )
        suggestions.append(
            ReviewSuggestion(
                suggestion_id=suggestion_id,
                proposal_kind="definition"
                if sf is not None and lf is not None
                else "span",
                short_form=sf,
                long_form=lf,
                source_pair_ids=tuple(sorted(set(cast(list[str], entry["pair_ids"])))),
                source_span_ids=tuple(sorted(set(cast(list[str], entry["span_ids"])))),
                method_ids=tuple(sorted(set(cast(list[str], entry["methods"])))),
                provenance=tuple(cast(list[dict[str, object]], entry["provenance"])),
            )
        )
    structures: list[ReviewStructure] = []
    raw_structures = list(
        cast(Sequence[object], section.get("structural_candidates", []))
    )
    raw_structures += [
        raw
        for raw in cast(Sequence[object], record.get("structures", []))
        if isinstance(raw, Mapping)
        and raw.get("section_id") == section.get("section_id")
    ]
    for raw_obj in raw_structures:
        if isinstance(raw_obj, Mapping):
            structures.append(
                ReviewStructure(
                    kind=str(raw_obj.get("kind", "source-structure")),
                    text=str(raw_obj.get("text", "")),
                    source_path=str(raw_obj["source_path"])
                    if raw_obj.get("source_path")
                    else None,
                )
            )
    comparisons = tuple(
        cast(dict[str, object], item)
        for item in cast(Sequence[object], manifest.get("source_comparisons", []))
        if isinstance(item, dict)
        and item.get("article_id") == record.get("article_id")
        and item.get("section_id") in {None, section.get("section_id")}
    )
    diagnostics = tuple(
        {
            "method_id": str(key),
            "status": value.get("status"),
            "coverage": value.get("coverage"),
            "diagnostics": value.get("diagnostics", []),
        }
        for key, value in _outputs(section).items()
        if isinstance(value, Mapping)
    )
    article_id, section_id, inventory_id = (
        str(record["article_id"]),
        str(section["section_id"]),
        str(inventory["inventory_id"]),
    )
    case_id = (
        "case-"
        + fingerprint(
            {
                "article_id": article_id,
                "section_id": section_id,
                "canonical_text_sha256": section["canonical_text_sha256"],
                "inventory_id": inventory_id,
                "start": start,
                "end": end,
                "category": category,
            }
        )[:20]
    )
    return ReviewCase(
        case_id=case_id,
        inventory_id=inventory_id,
        article_id=article_id,
        article_group_id=str(record.get("article_group_id", article_id)),
        title=str(record.get("title") or article_id),
        arm=cast(Literal["pmc_cc_by", "pubmed_abstract"], record.get("arm")),
        source_url=str(record.get("source_url") or "https://www.ncbi.nlm.nih.gov/"),
        source_kind=str(section.get("source_kind") or "article section"),
        section_id=section_id,
        section_heading=str(section.get("heading") or "Untitled section"),
        category=cast(
            Literal[
                "disagreement",
                "agreement",
                "enriched_zero",
                "uniform_zero",
                "diagnostic",
            ],
            category,
        ),
        inventory_category=str(inventory["category"]),
        canonical_text_sha256=str(section["canonical_text_sha256"]),
        passage_start=start,
        passage_end=end,
        text=passage,
        context_before=section_text[max(0, start - 900) : start],
        context_after=section_text[end : min(len(section_text), end + 900)],
        suggestions=tuple(suggestions),
        structures=tuple(structures),
        source_comparisons=comparisons,
        method_diagnostics=diagnostics,
        selection_reason=(
            "Uniformly ranked valid all-primary-zero control."
            if category == "uniform_zero"
            else (
                "Method-availability diagnostic; not a comparison or "
                "no-definition case."
                if category == "diagnostic"
                else f"Selected from the {category.replace('_', ' ')} stratum."
            )
        ),
    )


def _finish_packet(
    *,
    source_manifest_sha256: str,
    source_run_id: str,
    seed: int,
    cases: tuple[ReviewCase, ...],
    selection: ReviewSelection,
) -> ReviewPacket:
    provisional = ReviewPacket(
        packet_id="pending",
        content_sha256="0" * 64,
        source_manifest_sha256=source_manifest_sha256,
        source_run_id=source_run_id,
        seed=seed,
        cases=cases,
        selection=selection,
    )
    digest = fingerprint(packet_identity_payload(provisional))
    packet = provisional.model_copy(
        update={"packet_id": f"t052-{digest[:20]}", "content_sha256": digest}
    )
    validate_packet_identity(packet)
    return packet


def _write(packet: ReviewPacket, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        packet.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def build_review_packet(
    manifest_path: Path,
    output_path: Path,
    *,
    seed: int = 20260908,
    per_article_cap: int = 4,
) -> ReviewPacket:
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReviewError(f"unable to read pilot manifest: {error}") from error
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema_version") != "random-literature-pilot-v2"
    ):
        raise ReviewError("review packets require random-literature-pilot-v2")
    sections, records = _sections(manifest)
    classified: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    seen: set[str] = set()
    for raw in _inventory_rows(manifest):
        inventory_id, article_id, section_id = (
            str(raw.get("inventory_id", "")),
            str(raw.get("article_id", "")),
            str(raw.get("section_id", "")),
        )
        if not inventory_id or inventory_id in seen:
            raise ReviewError("inventory IDs must be present and unique")
        seen.add(inventory_id)
        section, record = (
            sections.get((article_id, section_id)),
            records.get(article_id),
        )
        if section is None or record is None:
            raise ReviewError(f"inventory {inventory_id} references an unknown section")
        if raw.get("canonical_text_sha256") != section.get("canonical_text_sha256"):
            raise ReviewError(
                f"inventory {inventory_id} has changed canonical text identity"
            )
        stratum = _stratum(raw, section)
        if stratum:
            item = dict(raw)
            item["_arm"] = record.get("arm")
            item["article_group_id"] = record.get("article_group_id", article_id)
            classified[stratum].append(item)
    denominators = {
        "disagreement": len(classified["disagreement"]),
        "agreement": len(classified["agreement"]),
        "enriched_zero": len(classified["enriched_zero"]),
        "uniform_zero": len(classified["enriched_zero"]) + len(classified["zero_pool"]),
        "diagnostic": len(classified["diagnostic"]),
    }
    article_counts: dict[str, int] = {}
    chosen: list[tuple[str, Mapping[str, object]]] = []
    for category in ("disagreement", "agreement", "enriched_zero"):
        chosen.extend(
            (category, item)
            for item in _select(
                classified[category],
                TARGETS[category],
                seed,
                article_counts,
                per_article_cap,
            )
        )
    used_zeros = {
        str(item["inventory_id"])
        for category, item in chosen
        if category == "enriched_zero"
    }
    zero_pool = [
        item
        for item in classified["enriched_zero"] + classified["zero_pool"]
        if str(item["inventory_id"]) not in used_zeros
    ]
    chosen.extend(
        ("uniform_zero", item)
        for item in _select(
            zero_pool,
            TARGETS["uniform_zero"],
            seed + 1,
            article_counts,
            per_article_cap,
        )
    )
    remaining_budget = max(0, DIAGNOSTIC_BUDGET - len(chosen))
    chosen.extend(
        ("diagnostic", item)
        for item in _select(
            classified["diagnostic"],
            remaining_budget,
            seed + 2,
            article_counts,
            per_article_cap,
            prefer_predictions=True,
        )
    )
    cases = tuple(
        _case(
            inventory,
            sections[(str(inventory["article_id"]), str(inventory["section_id"]))],
            records[str(inventory["article_id"])],
            category,
            manifest,
        )
        for category, inventory in chosen
    )
    counts: Counter[str] = Counter(case.category for case in cases)
    selected = {key: counts[key] for key in TARGETS}
    selected["diagnostic"] = counts["diagnostic"]
    shortages = {key: TARGETS[key] - selected[key] for key in TARGETS}
    shortages["diagnostic"] = max(0, remaining_budget - selected["diagnostic"])
    targets = dict(TARGETS)
    targets["diagnostic"] = DIAGNOSTIC_BUDGET
    selection = ReviewSelection(
        targets=targets,
        denominators=denominators,
        selected=selected,
        shortages=shortages,
        arm_counts=dict(sorted(Counter(case.arm for case in cases).items())),
        per_article_cap=per_article_cap,
    )
    packet = _finish_packet(
        source_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        source_run_id=str(manifest.get("run_id", "unknown-run")),
        seed=seed,
        cases=cases,
        selection=selection,
    )
    _write(packet, output_path)
    return packet


def read_review_packet(path: Path) -> ReviewPacket:
    try:
        packet = ReviewPacket.model_validate_json(path.read_text(encoding="utf-8"))
        validate_packet_identity(packet)
        return packet
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, ReviewError):
            raise
        raise ReviewError(f"invalid review packet: {error}") from error


def build_review_fixture(path: Path) -> ReviewPacket:
    text = (
        "A 🧬 marker and <img src=x onerror=alert('unsafe')> remain plain text.\n\n"
        "Tumor necrosis factor (TNF) and total nuclear factor (TNF) were measured; "
        "TNF appeared again."
    )

    def span(needle: str, start_at: int = 0) -> ReviewSpan:
        start = text.index(needle, start_at)
        return ReviewSpan(start=start, end=start + len(needle), text=needle)

    lf1, sf1 = span("Tumor necrosis factor"), span("TNF)")
    sf1 = sf1.model_copy(update={"end": sf1.end - 1, "text": "TNF"})
    lf2, sf2 = span("total nuclear factor"), span("TNF)", sf1.end)
    sf2 = sf2.model_copy(update={"end": sf2.end - 1, "text": "TNF"})
    suggestions = (
        ReviewSuggestion(
            suggestion_id="suggestion-a",
            short_form=sf1,
            long_form=lf1,
            source_pair_ids=("pair-a",),
            method_ids=("schwartz_hearst",),
        ),
        ReviewSuggestion(
            suggestion_id="suggestion-b",
            short_form=sf2,
            long_form=lf2,
            source_pair_ids=("pair-b",),
            method_ids=("ab3p",),
        ),
        ReviewSuggestion(
            suggestion_id="suggestion-overlap",
            short_form=sf1,
            long_form=ReviewSpan(
                start=lf1.start, end=lf1.end + 5, text=text[lf1.start : lf1.end + 5]
            ),
            source_pair_ids=("pair-c",),
            method_ids=("plodv2_pairing",),
        ),
    )
    case1 = ReviewCase(
        case_id="case-adversarial",
        inventory_id="inventory-adversarial",
        article_id="PMC-FIXTURE",
        article_group_id="fixture-group",
        title="Reviewer safety and multiple-definition fixture",
        arm="pmc_cc_by",
        source_url="https://www.ncbi.nlm.nih.gov/pmc/",
        source_kind="full_text",
        section_id="body-1",
        section_heading="Results",
        category="disagreement",
        inventory_category="boundary_disagreement",
        canonical_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        passage_start=0,
        passage_end=len(text),
        text=text,
        context_before="Earlier full-text paragraph.",
        context_after="Later full-text paragraph.",
        suggestions=suggestions,
        structures=(
            ReviewStructure(
                kind="table",
                text="TNF | total nuclear factor",
                source_path="article/body/sec/table",
            ),
        ),
        source_comparisons=(
            {"format": "JATS/BioC", "finding": "fixture mapping retained"},
        ),
        method_diagnostics=(
            {
                "method_id": "plodv2_pairing",
                "status": "failed",
                "coverage": "partial",
                "diagnostics": ["fixture failure"],
            },
        ),
        selection_reason="Adversarial rendered-interaction fixture.",
    )
    zero_text = "No abbreviation definition appears in this abstract."
    case2 = ReviewCase(
        case_id="case-no-suggestions",
        inventory_id="inventory-zero",
        article_id="PMID-FIXTURE",
        article_group_id="fixture-abstract",
        title="No-suggestion passage fixture",
        arm="pubmed_abstract",
        source_url="https://pubmed.ncbi.nlm.nih.gov/",
        source_kind="abstract",
        section_id="abstract",
        section_heading="Abstract",
        category="uniform_zero",
        inventory_category="all_primary_zero",
        canonical_text_sha256=hashlib.sha256(zero_text.encode("utf-8")).hexdigest(),
        passage_start=0,
        passage_end=len(zero_text),
        text=zero_text,
        method_diagnostics=tuple(
            {
                "method_id": method,
                "status": "completed",
                "coverage": "complete",
                "diagnostics": [],
            }
            for method in PRIMARY_METHODS
        ),
        selection_reason="Uniform valid all-primary-zero fixture.",
    )
    selection = ReviewSelection(
        targets={
            "disagreement": 1,
            "agreement": 0,
            "enriched_zero": 0,
            "uniform_zero": 1,
        },
        denominators={
            "disagreement": 1,
            "agreement": 0,
            "enriched_zero": 0,
            "uniform_zero": 1,
        },
        selected={
            "disagreement": 1,
            "agreement": 0,
            "enriched_zero": 0,
            "uniform_zero": 1,
        },
        shortages={
            "disagreement": 0,
            "agreement": 0,
            "enriched_zero": 0,
            "uniform_zero": 0,
        },
        arm_counts={"pmc_cc_by": 1, "pubmed_abstract": 1},
        per_article_cap=4,
    )
    packet = _finish_packet(
        source_manifest_sha256="f" * 64,
        source_run_id="t052-ui-fixture",
        seed=20260908,
        cases=(case1, case2),
        selection=selection,
    )
    _write(packet, path)
    return packet
