"""Bounded readiness checks for the existing literature baselines.

This module deliberately reports operational state only.  It does not turn a
failed worker into an empty prediction or make any accuracy claim.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import Document
from abrex.infrastructure.ab3p import (
    Ab3PCacheMiss,
    Ab3PInstallationError,
    cache_key,
)
from abrex.literature.pilot_methods import _worker_command, run_methods
from abrex.literature.pilot_models import (
    MethodOutput,
    PilotConfig,
    PilotSection,
    config_fingerprint,
)
from abrex.resolvers import (
    Ab3PCacheConfig,
    Ab3PInstallationConfig,
    Ab3PResolverConfig,
)

ReadinessStatus = Literal["available", "failed", "unavailable"]


class ReadinessMethod(BaseModel):
    """One method's observed smoke result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method_id: str
    status: ReadinessStatus
    version: str
    identity: str
    resource_hashes: dict[str, str] = Field(default_factory=dict)
    runtime: dict[str, object] = Field(default_factory=dict)
    worker_command: tuple[str, ...] = ()
    text_coverage: str
    truncated: bool
    elapsed_seconds: float = Field(ge=0)
    diagnostics: tuple[str, ...] = ()
    section_count: int = Field(ge=0)
    pair_count: int = Field(ge=0)
    span_count: int = Field(ge=0)


class ReadinessReport(BaseModel):
    """Serializable bounded readiness evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["runtime-readiness-v1"] = "runtime-readiness-v1"
    repair_budget: dict[str, object]
    smoke_documents: tuple[dict[str, object], ...]
    canonical_text_hashes: dict[str, str]
    methods: tuple[ReadinessMethod, ...]
    offset_evidence: dict[str, object]
    cache_identity_checks: dict[str, object]
    limitations: tuple[str, ...] = ()


def smoke_sections() -> tuple[PilotSection, ...]:
    """Return the fixed Unicode/repeated/empty-result smoke input."""

    texts = (
        ("unicode", "🧬 β-blocker (BB) is repeated: β-blocker (BB)."),
        ("repeated", "Magnetic resonance imaging (MRI); MRI appears again."),
        ("empty", "A control passage contains no parenthetical definition."),
    )
    return tuple(
        PilotSection(
            section_id=f"t058-{name}",
            document_id=f"t058-{name}",
            heading=name,
            source_kind="fixed-smoke",
            canonical_text=text,
            canonical_text_sha256=_sha256_text(text),
            source_locator=f"t058-smoke:{name}",
        )
        for name, text in texts
    )


def run_readiness(
    config: PilotConfig,
    runtime_dir: Path,
    *,
    repair_budget_hours: float = 2.0,
) -> ReadinessReport:
    """Run the fixed smoke and return explicit method readiness evidence."""

    sections = smoke_sections()
    started = time.monotonic()
    outputs = run_methods(sections, config, runtime_dir)
    methods: list[ReadinessMethod] = []
    for method_id in (
        "schwartz_hearst",
        "ab3p",
        "plodv2",
        "plodv2_pairing",
    ):
        observed = tuple(
            outputs[section.document_id][method_id] for section in sections
        )
        command: tuple[str, ...] = ()
        if method_id in {"ab3p", "plodv2", "plodv2_pairing"}:
            worker_method = "ab3p" if method_id == "ab3p" else "plodv2"
            command = tuple(
                _worker_command(
                    config.ab3p.interpreter
                    if worker_method == "ab3p"
                    else config.plodv2.interpreter,
                    worker_method,
                    runtime_dir / f"{worker_method}-input.json",
                    runtime_dir / f"{worker_method}-output.json",
                    runtime_dir / f"{worker_method}-params.json",
                )
            )
        methods.append(_method_evidence(method_id, observed, command))

    offset_evidence = _offset_evidence(outputs, sections)

    input_hashes = {
        section.document_id: section.canonical_text_sha256 for section in sections
    }
    cache_checks = {
        "input_hashes_are_unique": len(set(input_hashes.values())) == len(input_hashes),
        "changed_input_changes_identity": _changed_input_changes_identity(sections[0]),
        "check_scope": "live prediction-cache probe plus input/config identity checks",
        "worker_inputs": {
            method: _worker_input_hash(runtime_dir, method)
            for method in ("ab3p", "plodv2")
            if (runtime_dir / f"{method}-input.json").is_file()
        },
        "prediction_cache": _verify_ab3p_prediction_cache(config, runtime_dir),
    }
    return ReadinessReport(
        repair_budget={
            "ceiling_hours": repair_budget_hours,
            "optional_method_repairs_per_method": 1,
            "bulk_downloads_permitted": False,
            "system_installation_permitted": False,
            "elapsed_seconds": time.monotonic() - started,
        },
        smoke_documents=tuple(
            {
                "document_id": section.document_id,
                "text_sha256": section.canonical_text_sha256,
                "characters": len(section.canonical_text),
                "contains_unicode": any(
                    ord(char) > 127 for char in section.canonical_text
                ),
                "contains_supplementary_unicode": any(
                    ord(char) > 0xFFFF for char in section.canonical_text
                ),
                "expected_empty_result": section.heading == "empty",
            }
            for section in sections
        ),
        canonical_text_hashes=input_hashes,
        methods=tuple(methods),
        offset_evidence=offset_evidence,
        cache_identity_checks=cache_checks,
        limitations=(
            "Smoke evidence establishes operational readiness only; it is not "
            "an accuracy evaluation.",
            "PLOD independent spans and paired relations are reported separately.",
        ),
    )


def _offset_evidence(
    outputs: dict[str, dict[str, MethodOutput]], sections: tuple[PilotSection, ...]
) -> dict[str, object]:
    evidence: dict[str, object] = {}
    for method_id in ("schwartz_hearst", "ab3p", "plodv2", "plodv2_pairing"):
        method_outputs = [
            outputs[section.document_id][method_id] for section in sections
        ]
        pair_total = sum(len(output.pairs) for output in method_outputs)
        pair_text_matches = sum(
            1
            for output, section in zip(method_outputs, sections, strict=True)
            for pair in output.pairs
            if section.canonical_text[pair.short_form.start : pair.short_form.end]
            == pair.short_form.text
            and section.canonical_text[pair.long_form.start : pair.long_form.end]
            == pair.long_form.text
        )
        span_total = sum(len(output.spans) for output in method_outputs)
        span_text_matches = sum(
            1
            for output, section in zip(method_outputs, sections, strict=True)
            for span in output.spans
            if section.canonical_text[span.start : span.end] == span.text
        )
        empty = outputs["t058-empty"][method_id]
        evidence[method_id] = {
            "pair_offsets_checked": pair_total,
            "pair_text_matches": pair_text_matches,
            "span_offsets_checked": span_total,
            "span_text_matches": span_text_matches,
            "empty_control_pairs": len(empty.pairs),
            "empty_control_spans": len(empty.spans),
        }
    return evidence


def _verify_ab3p_prediction_cache(
    config: PilotConfig, runtime_dir: Path
) -> dict[str, object]:
    """Exercise the existing Ab3P cache through cold and warm resolver paths."""

    from abrex.resolvers import Ab3PResolver

    cache_dir = runtime_dir.parent / "cache-probe"
    document = Document(
        "t058-cache",
        "Tumor necrosis factor (TNF) is measured in 🧬 tissue.",
    )
    live_config = Ab3PResolverConfig(
        backend="cache_then_subprocess",
        output_format="offset_jsonl",
        timeout_seconds=config.ab3p.timeout_seconds,
        installation=Ab3PInstallationConfig(
            manifest=config.ab3p.installation_manifest,
            root=config.ab3p.installation_root,
            executable="identify_abbr_offsets",
            resource_directory="WordData",
        ),
        cache=Ab3PCacheConfig(path=str(cache_dir), read=True, write=True),
    )
    try:
        key = cache_key(document, live_config)
    except (Ab3PInstallationError, OSError, ValueError) as error:
        return {
            "status": "unavailable",
            "diagnostic": f"cache_probe_prerequisite:{type(error).__name__}:{error}",
        }
    cache_path = cache_dir / f"{key}.json"
    cache_path.unlink(missing_ok=True)
    cold_absent = not cache_path.exists()
    cold_predictions = tuple(Ab3PResolver(**live_config.model_dump()).resolve(document))
    cold_written = cache_path.is_file()

    warm_resolver = Ab3PResolver(**live_config.model_dump())
    with patch(
        "abrex.infrastructure.ab3p.run_ab3p",
        side_effect=AssertionError("warm cache unexpectedly invoked live Ab3P"),
    ):
        warm_predictions = tuple(warm_resolver.resolve(document))

    cache_only = live_config.model_copy(
        update={
            "backend": "cache_only",
            "cache": Ab3PCacheConfig(path=str(cache_dir), read=True, write=False),
        }
    )
    changed_text_missed = _cache_misses(
        Ab3PResolver(**cache_only.model_dump()),
        Document(document.document_id, document.text + " changed"),
    )
    changed_config = live_config.model_copy(update={"output_format": "text"})
    changed_config = changed_config.model_copy(
        update={
            "backend": "cache_only",
            "cache": Ab3PCacheConfig(path=str(cache_dir), read=True, write=False),
        }
    )
    changed_config_missed = _cache_misses(
        Ab3PResolver(**changed_config.model_dump()), document
    )
    return {
        "cache_layer": "Ab3PCache via Ab3PResolver",
        "cache_key": key,
        "cold_cache_entry_absent_before_run": cold_absent,
        "cold_live_predictions": len(cold_predictions),
        "cold_cache_entry_written": cold_written,
        "warm_replay_predictions": len(warm_predictions),
        "warm_replay_matches_cold": _prediction_dump(cold_predictions)
        == _prediction_dump(warm_predictions),
        "warm_live_invocation_blocked": True,
        "changed_text_cache_miss": changed_text_missed,
        "changed_config_cache_miss": changed_config_missed,
        "cache_entry": str(cache_path),
    }


def _cache_misses(resolver: object, document: Document) -> bool:
    try:
        resolver.resolve(document)  # type: ignore[attr-defined]
    except Ab3PCacheMiss:
        return True
    return False


def _prediction_dump(predictions: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(repr(prediction) for prediction in predictions)


def _method_evidence(
    method_id: str, outputs: tuple[MethodOutput, ...], command: tuple[str, ...]
) -> ReadinessMethod:
    statuses = {output.status for output in outputs}
    status: ReadinessStatus = (
        "available"
        if statuses == {"completed"}
        and all(output.coverage == "complete" for output in outputs)
        else "unavailable"
        if statuses <= {"unavailable", "not_run"}
        else "failed"
    )
    first = outputs[0]
    hashes = {
        key: value
        for key, value in first.runtime.items()
        if key.endswith("sha256") and isinstance(value, str)
    }
    return ReadinessMethod(
        method_id=method_id,
        status=status,
        version=first.version,
        identity=first.identity,
        resource_hashes=hashes,
        runtime=first.runtime,
        worker_command=command,
        text_coverage=(
            "complete"
            if all(item.coverage == "complete" for item in outputs)
            else "none"
        ),
        truncated=any(
            "truncat" in diagnostic.casefold()
            for output in outputs
            for diagnostic in output.diagnostics
        ),
        elapsed_seconds=sum(item.elapsed_seconds for item in outputs),
        diagnostics=tuple(
            sorted(
                {diagnostic for output in outputs for diagnostic in output.diagnostics}
            )
        ),
        section_count=len(outputs),
        pair_count=sum(len(item.pairs) for item in outputs),
        span_count=sum(len(item.spans) for item in outputs),
    )


def _changed_input_changes_identity(section: PilotSection) -> bool:
    original = config_fingerprint(
        {"document_id": section.document_id, "text": section.canonical_text}
    )
    changed = config_fingerprint(
        {"document_id": section.document_id, "text": section.canonical_text + "x"}
    )
    return original != changed


def _worker_input_hash(runtime_dir: Path, method: str) -> str:
    return _sha256_bytes((runtime_dir / f"{method}-input.json").read_bytes())


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = ["ReadinessMethod", "ReadinessReport", "run_readiness", "smoke_sections"]
