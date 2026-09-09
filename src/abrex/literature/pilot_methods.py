"""Configured resolver and candidate execution for section-local pilot text."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.candidates import (
    LexicalResourceCandidateGenerator,
    ParentheticalCandidateGenerator,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    Document,
    PredictionMetadata,
    TextSpan,
)
from abrex.literature.pilot_models import (
    CandidateProposal,
    CanonicalSpan,
    MethodOutput,
    PilotConfig,
    PilotSection,
    PredictionPair,
    PredictionSpan,
    config_fingerprint,
    stable_id,
)
from abrex.resolvers import SchwartzHearstResolver, TransparentHybridResolver


class PilotMethodError(RuntimeError):
    """Raised when an isolated worker result violates the pilot contract."""


def run_methods(
    sections: Sequence[PilotSection], config: PilotConfig, runtime_dir: Path
) -> dict[str, dict[str, MethodOutput]]:
    """Run all primary methods once and derive the configured transparent hybrid."""

    outputs: dict[str, dict[str, MethodOutput]] = {
        section.document_id: {} for section in sections
    }
    for section in sections:
        outputs[section.document_id]["schwartz_hearst"] = _schwartz(section)

    ab3p_params: dict[str, object] = {
        "backend": "cache_then_subprocess",
        "output_format": "offset_jsonl",
        "timeout_seconds": config.ab3p.timeout_seconds,
        "installation": {
            "manifest": config.ab3p.installation_manifest,
            "root": config.ab3p.installation_root,
            "executable": "identify_abbr_offsets",
            "resource_directory": "WordData",
        },
        "cache": {"path": config.ab3p.cache_dir, "read": True, "write": True},
    }
    ab3p = _run_worker(
        "ab3p",
        sections,
        ab3p_params,
        config.ab3p.interpreter,
        config.ab3p.timeout_seconds * max(1, len(sections)),
        runtime_dir,
        enabled=config.ab3p.enabled,
    )
    _merge_worker_outputs(outputs, sections, ab3p, "ab3p", ab3p_params)

    plod_params: dict[str, object] = {
        "checkpoint_path": config.plodv2.checkpoint_path,
        "checkpoint_sha256": config.plodv2.checkpoint_sha256,
        "device": config.plodv2.device,
        "max_chars_per_window": config.plodv2.max_chars_per_window,
        "window_overlap": config.plodv2.window_overlap,
        "duplicate_policy": "deduplicate",
        "runtime_version": "flair-0.15.1-torch-2.14.0+cpu",
    }
    plod = _run_worker(
        "plodv2",
        sections,
        plod_params,
        config.plodv2.interpreter,
        config.plodv2.timeout_seconds,
        runtime_dir,
        enabled=config.plodv2.enabled,
    )
    _merge_worker_outputs(outputs, sections, plod, "plodv2_pairing", plod_params)
    for section in sections:
        paired = outputs[section.document_id]["plodv2_pairing"]
        outputs[section.document_id]["plodv2"] = paired.model_copy(
            update={"method_id": "plodv2", "pairs": ()}
        )
        outputs[section.document_id]["transparent_hybrid"] = _hybrid(
            section, outputs[section.document_id]
        )
    return outputs


def generate_candidates(
    section: PilotSection, resource_paths: Sequence[str]
) -> tuple[tuple[CandidateProposal, ...], tuple[CandidateProposal, ...]]:
    """Run separately labeled structural and optional lexical proposal paths."""

    document = Document(section.document_id, section.canonical_text)
    structural = _candidate_proposals(
        section,
        ParentheticalCandidateGenerator().generate(document).candidates,
        "parenthetical",
    )
    lexical: tuple[CandidateProposal, ...] = ()
    if resource_paths:
        lexical = _candidate_proposals(
            section,
            LexicalResourceCandidateGenerator(
                resource_paths=tuple(Path(path) for path in resource_paths)
            )
            .generate(document)
            .candidates,
            "lexical_resource",
        )
    return structural, lexical


def _schwartz(section: PilotSection) -> MethodOutput:
    started = time.monotonic()
    resolver = SchwartzHearstResolver()
    predictions = tuple(
        resolver.resolve(Document(section.document_id, section.canonical_text))
    )
    params = resolver.config.model_dump(mode="json")
    return MethodOutput(
        method_id="schwartz_hearst",
        identity=resolver.identity,
        version=resolver.version,
        config_sha256=config_fingerprint(params),
        runtime={"python": "in_process"},
        status="completed",
        coverage="complete",
        elapsed_seconds=time.monotonic() - started,
        pairs=tuple(
            _prediction_pair(section, "schwartz_hearst", item) for item in predictions
        ),
    )


def _run_worker(
    method: str,
    sections: Sequence[PilotSection],
    params: Mapping[str, object],
    interpreter: str,
    timeout: float,
    runtime_dir: Path,
    *,
    enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return {
            "status": "not_run",
            "identity": method,
            "version": "disabled",
            "diagnostics": ["disabled_by_resolved_configuration"],
            "records": [],
        }
    runtime_dir.mkdir(parents=True, exist_ok=True)
    input_path = runtime_dir / f"{method}-input.json"
    params_path = runtime_dir / f"{method}-params.json"
    output_path = runtime_dir / f"{method}-output.json"
    input_path.write_text(
        json.dumps(
            [
                {"document_id": section.document_id, "text": section.canonical_text}
                for section in sections
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    params_path.write_text(
        json.dumps(params, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    output_path.unlink(missing_ok=True)
    command = _worker_command(interpreter, method, input_path, output_path, params_path)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "status": "unavailable" if isinstance(error, OSError) else "failed",
            "identity": method,
            "version": "worker-failed",
            "diagnostics": [f"worker_launch_failed:{type(error).__name__}:{error}"],
            "records": [],
        }
    if completed.returncode != 0 or not output_path.is_file():
        return {
            "status": "failed",
            "identity": method,
            "version": "worker-failed",
            "diagnostics": [
                f"worker_exit:{completed.returncode}",
                f"worker_stderr:{completed.stderr[-2000:]}",
            ],
            "records": [],
        }
    try:
        result = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PilotMethodError(f"invalid {method} worker output: {error}") from error
    if not isinstance(result, dict):
        raise PilotMethodError(f"invalid {method} worker output root")
    return result


def _worker_command(
    interpreter: str,
    method: str,
    input_path: Path,
    output_path: Path,
    params_path: Path,
) -> list[str]:
    worker_args = [
        interpreter,
        "-m",
        "abrex.literature.pilot_worker",
        "--method",
        method,
        "--input",
        _runtime_path(input_path),
        "--output",
        _runtime_path(output_path),
        "--params",
        _runtime_path(params_path),
    ]
    if os.name == "nt" and interpreter.startswith("/"):
        repo_src = Path(__file__).resolve().parents[2]
        return [
            "wsl.exe",
            "-d",
            "Ubuntu",
            "--",
            "env",
            f"PYTHONPATH={_runtime_path(repo_src, wsl=True)}",
            *worker_args,
        ]
    return worker_args


def _runtime_path(path: Path, *, wsl: bool = True) -> str:
    resolved = path.resolve()
    if os.name != "nt" or not wsl:
        return str(resolved)
    drive = resolved.drive.rstrip(":").lower()
    suffix = resolved.as_posix().split(":", 1)[-1]
    return f"/mnt/{drive}{suffix}"


def _merge_worker_outputs(
    outputs: dict[str, dict[str, MethodOutput]],
    sections: Sequence[PilotSection],
    worker: Mapping[str, object],
    method_id: str,
    params: Mapping[str, object],
) -> None:
    raw_records = worker.get("records", [])
    records: dict[str, Mapping[str, object]] = {}
    if isinstance(raw_records, list):
        for item in raw_records:
            if not isinstance(item, Mapping) or not isinstance(
                item.get("document_id"), str
            ):
                raise PilotMethodError("worker records must have string document IDs")
            document_id = str(item["document_id"])
            if document_id in records:
                raise PilotMethodError(f"duplicate worker document ID: {document_id}")
            records[document_id] = item
    overall_status = str(worker.get("status", "failed"))
    for section in sections:
        raw = records.get(section.document_id)
        if raw is None:
            status = (
                overall_status
                if overall_status in {"unavailable", "not_run"}
                else "failed"
            )
            outputs[section.document_id][method_id] = MethodOutput(
                method_id=method_id,
                identity=str(worker.get("identity", method_id)),
                version=str(worker.get("version", "unknown")),
                config_sha256=config_fingerprint(dict(params)),
                runtime=_runtime_identity(worker),
                status=status,  # type: ignore[arg-type]
                coverage="none",
                diagnostics=_string_tuple(worker.get("diagnostics", [])),
            )
            continue
        outputs[section.document_id][method_id] = _worker_method_output(
            section, method_id, params, worker, raw
        )


def _worker_method_output(
    section: PilotSection,
    method_id: str,
    params: Mapping[str, object],
    worker: Mapping[str, object],
    raw: Mapping[str, object],
) -> MethodOutput:
    pairs = tuple(
        _raw_pair(section, method_id, item) for item in _objects(raw.get("pairs", []))
    )
    spans = tuple(
        _raw_span(section, method_id, item) for item in _objects(raw.get("spans", []))
    )
    return MethodOutput(
        method_id=method_id,
        identity=str(worker.get("identity", method_id)),
        version=str(worker.get("version", "unknown")),
        config_sha256=config_fingerprint(dict(params)),
        runtime=_runtime_identity(worker),
        status=cast(Any, str(raw.get("status", "failed"))),
        coverage=cast(Any, str(raw.get("coverage", "none"))),
        elapsed_seconds=float(str(raw.get("elapsed_seconds", 0.0))),
        pairs=pairs,
        spans=spans,
        diagnostics=_string_tuple(raw.get("diagnostics", [])),
    )


def _runtime_identity(worker: Mapping[str, object]) -> dict[str, object]:
    value = worker.get("runtime_identity", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise PilotMethodError("worker pair/span arrays must contain objects")
    return tuple(cast(Mapping[str, object], item) for item in value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _raw_pair(
    section: PilotSection, method: str, raw: Mapping[str, object]
) -> PredictionPair:
    short = _raw_canonical_span(raw.get("short_form"))
    long = _raw_canonical_span(raw.get("long_form"))
    raw_provenance = raw.get("provenance", {})
    return PredictionPair(
        pair_id=stable_id(
            "pair",
            section.document_id,
            method,
            short.start,
            short.end,
            long.start,
            long.end,
        ),
        short_form=short,
        long_form=long,
        score=float(str(raw["score"]))
        if isinstance(raw.get("score"), int | float)
        else None,
        provenance=dict(raw_provenance) if isinstance(raw_provenance, Mapping) else {},
    )


def _raw_span(
    section: PilotSection, method: str, raw: Mapping[str, object]
) -> PredictionSpan:
    label = raw.get("label")
    if label not in {"SF", "LF"}:
        raise PilotMethodError(f"invalid worker span label: {label}")
    return PredictionSpan(
        span_id=stable_id(
            "span", section.document_id, method, label, raw.get("start"), raw.get("end")
        ),
        label=cast(Any, label),
        start=int(str(raw["start"])),
        end=int(str(raw["end"])),
        text=str(raw["text"]),
        score=float(str(raw["score"]))
        if isinstance(raw.get("score"), int | float)
        else None,
        provenance={"source_window_start": raw.get("source_window_start")},
    )


def _raw_canonical_span(value: object) -> CanonicalSpan:
    if not isinstance(value, Mapping):
        raise PilotMethodError("worker pair form must be an object")
    return CanonicalSpan(
        start=int(str(value["start"])),
        end=int(str(value["end"])),
        text=str(value["text"]),
    )


def _prediction_pair(
    section: PilotSection, method: str, item: AbbreviationDefinition
) -> PredictionPair:
    if item.short_form is None or item.long_form is None:
        raise PilotMethodError(f"{method} returned an incomplete pair")
    return PredictionPair(
        pair_id=stable_id(
            "pair",
            section.document_id,
            method,
            item.short_form.start,
            item.short_form.end,
            item.long_form.start,
            item.long_form.end,
        ),
        short_form=CanonicalSpan(
            start=item.short_form.start,
            end=item.short_form.end,
            text=item.short_form_text
            or section.canonical_text[item.short_form.start : item.short_form.end],
        ),
        long_form=CanonicalSpan(
            start=item.long_form.start,
            end=item.long_form.end,
            text=item.long_form_text
            or section.canonical_text[item.long_form.start : item.long_form.end],
        ),
        score=item.prediction.score if item.prediction is not None else None,
        provenance={
            "adapter_identity": item.provenance.adapter_identity
            if item.provenance is not None
            else None,
            "transformation_notes": list(item.provenance.transformation_notes)
            if item.provenance is not None
            else [],
        },
    )


class _ReplayResolver:
    def __init__(
        self, identity: str, predictions: tuple[AbbreviationDefinition, ...]
    ) -> None:
        self.identity = identity
        self.version = "pilot-replay-v1"
        self._predictions = predictions

    def resolve(self, document: Document) -> Iterable[AbbreviationDefinition]:
        for prediction in self._predictions:
            if prediction.document_id != document.document_id:
                raise ValueError("replay prediction document mismatch")
        return self._predictions


def _hybrid(section: PilotSection, outputs: Mapping[str, MethodOutput]) -> MethodOutput:
    child_names = ("schwartz_hearst", "ab3p", "plodv2_pairing")
    children: list[_ReplayResolver] = []
    for name in child_names:
        output = outputs[name]
        if output.status != "completed" or output.coverage != "complete":
            return MethodOutput(
                method_id="transparent_hybrid",
                identity="transparent_hybrid",
                version="transparent-hybrid-v1",
                config_sha256=config_fingerprint(
                    {
                        "strategy": "exact_union",
                        "conflict_policy": "retain_all",
                        "children": child_names,
                    }
                ),
                status="failed",
                coverage="none",
                diagnostics=(
                    f"primary_method_incomplete:{name}:{output.status}:{output.coverage}",
                ),
            )
        predictions = tuple(
            _domain_prediction(section, pair, name) for pair in output.pairs
        )
        children.append(_ReplayResolver(name, predictions))
    started = time.monotonic()
    resolver = TransparentHybridResolver(
        children=children,
        child_names=child_names,
        strategy="exact_union",
        conflict_policy="retain_all",
        child_failure_policy="raise",
    )
    result = resolver.resolve_with_evidence(
        Document(section.document_id, section.canonical_text)
    )
    return MethodOutput(
        method_id="transparent_hybrid",
        identity=resolver.identity,
        version=resolver.version,
        config_sha256=config_fingerprint(resolver.cache_identity),
        runtime=resolver.cache_identity,
        status="completed",
        coverage="complete",
        elapsed_seconds=time.monotonic() - started,
        pairs=tuple(
            _prediction_pair(section, "transparent_hybrid", item)
            for item in result.predictions
        ),
        diagnostics=tuple(
            f"{decision.child}:{decision.rule}:{decision.accepted}"
            for decision in result.decisions
        ),
    )


def _domain_prediction(
    section: PilotSection, pair: PredictionPair, method: str
) -> AbbreviationDefinition:
    return AbbreviationDefinition(
        section.document_id,
        short_form=TextSpan(pair.short_form.start, pair.short_form.end),
        long_form=TextSpan(pair.long_form.start, pair.long_form.end),
        short_form_text=pair.short_form.text,
        long_form_text=pair.long_form.text,
        provenance=AnnotationProvenance(
            adapter_identity=method, adapter_version="pilot-v2"
        ),
        prediction=PredictionMetadata(score=pair.score, component=method),
    )


def _candidate_proposals(
    section: PilotSection, candidates: Sequence[Any], generator: str
) -> tuple[CandidateProposal, ...]:
    return tuple(
        CandidateProposal(
            candidate_id=stable_id(
                "candidate",
                section.document_id,
                generator,
                item.short_form.start,
                item.short_form.end,
                item.long_form.start,
                item.long_form.end,
            ),
            generator=generator,
            short_form=CanonicalSpan(
                start=item.short_form.start,
                end=item.short_form.end,
                text=section.canonical_text[
                    item.short_form.start : item.short_form.end
                ],
            ),
            long_form=CanonicalSpan(
                start=item.long_form.start,
                end=item.long_form.end,
                text=section.canonical_text[item.long_form.start : item.long_form.end],
            ),
            provenance={"construction": item.construction},
        )
        for item in candidates
    )


__all__ = ["PilotMethodError", "generate_candidates", "run_methods"]
