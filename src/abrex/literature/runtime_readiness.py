"""Bounded readiness checks for the existing literature baselines.

This module deliberately reports operational state only.  It does not turn a
failed worker into an empty prediction or make any accuracy claim.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abrex.literature.pilot_methods import _worker_command, run_methods
from abrex.literature.pilot_models import (
    MethodOutput,
    PilotConfig,
    PilotSection,
    config_fingerprint,
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

    input_hashes = {
        section.document_id: section.canonical_text_sha256 for section in sections
    }
    cache_checks = {
        "input_hashes_are_unique": len(set(input_hashes.values())) == len(input_hashes),
        "changed_input_changes_identity": _changed_input_changes_identity(sections[0]),
        "check_scope": "input fingerprint only; not a prediction-cache replay test",
        "worker_inputs": {
            method: _worker_input_hash(runtime_dir, method)
            for method in ("ab3p", "plodv2")
            if (runtime_dir / f"{method}-input.json").is_file()
        },
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
        cache_identity_checks=cache_checks,
        limitations=(
            "Smoke evidence establishes operational readiness only; it is not "
            "an accuracy evaluation.",
            "PLOD independent spans and paired relations are reported separately.",
        ),
    )


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
