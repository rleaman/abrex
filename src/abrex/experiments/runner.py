"""Application service for reproducible, YAML-composed experiments."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from abrex.config import ResolvedConfig, load_resolved_config, serialize_resolved_config
from abrex.corpora import (
    CanonicalSerializationError,
    DatasetManifest,
    fingerprint_records,
    read_canonical_dataset,
)
from abrex.domain import CorpusRecord, Document
from abrex.evaluation import create_evaluator
from abrex.reporting import ReportContext, create_reporters
from abrex.resolvers import (
    ExecutionErrorPolicy,
    PredictionArtifact,
    create_resolver_executor,
    fingerprint_prediction_artifact,
    read_prediction_artifact,
    resolver_config_from_resolved,
    write_prediction_artifact,
)
from abrex.resolvers.execution import ResolverExecutor


class ExperimentError(ValueError):
    """Raised when an experiment cannot be composed or published."""


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """Stable paths and identities produced by one experiment run."""

    run_directory: Path
    manifest_path: Path
    prediction_path: Path
    report_paths: tuple[Path, ...]
    corpus_fingerprint: str
    prediction_fingerprint: str
    evaluation_fingerprint: str
    reused_predictions: bool


def run_experiment(
    config_paths: tuple[Path, ...],
    *,
    output_root: Path | None = None,
    reuse_cached_predictions: bool | None = None,
) -> ExperimentResult:
    """Run a configured corpus/resolver/evaluation/reporting pipeline.

    Prediction cache paths are content addressed by the corpus fingerprint and
    the complete resolved resolver configuration.  A present file is never
    considered a valid cache without passing artifact and span validation.
    """

    config = load_resolved_config(config_paths)
    records, manifest = _load_corpus(config)
    corpus_fingerprint = fingerprint_records(records)
    resolver_config = resolver_config_from_resolved(config)
    resolver_executor = create_resolver_executor(resolver_config)
    resolver_config_json = _component_json(resolver_config)
    cache_key = _sha256(
        json.dumps(
            {
                "corpus_fingerprint": corpus_fingerprint,
                "resolver": resolver_config_json,
                "resolver_version": resolver_executor.metadata.version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    root = output_root or _output_root(config)
    run_directory = root / cache_key
    run_directory.mkdir(parents=True, exist_ok=True)
    prediction_path = run_directory / "predictions.jsonl"
    reuse = (
        _reuse_setting(config)
        if reuse_cached_predictions is None
        else reuse_cached_predictions
    )
    documents = {record.document.document_id: record.document for record in records}
    artifact: PredictionArtifact
    reused = False
    if reuse and prediction_path.exists():
        try:
            candidate = read_prediction_artifact(
                prediction_path,
                documents=documents,
                expected_dataset_fingerprint=corpus_fingerprint,
            )
        except (OSError, ValueError):
            candidate = None
        if candidate is not None and candidate.resolver == resolver_executor.metadata:
            artifact = candidate
            reused = True
        else:
            artifact = _run_resolver(
                resolver_executor,
                documents,
                resolver_config.error_policy,
                prediction_path,
                corpus_fingerprint,
            )
    else:
        artifact = _run_resolver(
            resolver_executor,
            documents,
            resolver_config.error_policy,
            prediction_path,
            corpus_fingerprint,
        )
    if not reused:
        artifact = read_prediction_artifact(
            prediction_path,
            documents=documents,
            expected_dataset_fingerprint=corpus_fingerprint,
        )
    prediction_fingerprint = fingerprint_prediction_artifact(artifact)
    evaluation = create_evaluator(config).evaluate(
        records, artifact, expected_dataset_fingerprint=corpus_fingerprint
    )
    context = ReportContext(
        evaluation=evaluation,
        documents=tuple(documents.values()),
        metadata=(
            ("corpus_fingerprint", corpus_fingerprint),
            ("prediction_fingerprint", prediction_fingerprint),
        ),
        configuration=(
            ("resolver_key", resolver_executor.metadata.key),
            ("resolver_version", resolver_executor.metadata.version),
        ),
    )
    report_paths = _write_reports(config, context, run_directory)
    evaluation_text = _evaluation_text(context)
    evaluation_path = run_directory / "evaluation.json"
    _write_text(evaluation_path, evaluation_text)
    evaluation_fingerprint = _sha256(evaluation_text.encode("utf-8"))
    manifest_path = run_directory / "run-manifest.json"
    run_manifest = _run_manifest(
        config,
        config_paths,
        manifest,
        corpus_fingerprint,
        resolver_executor.metadata.key,
        resolver_executor.metadata.version,
        resolver_config_json,
        prediction_path,
        prediction_fingerprint,
        evaluation_path,
        evaluation_fingerprint,
        config_fingerprint=_sha256(
            serialize_resolved_config(config, format="json").encode()
        ),
        reused=reused,
    )
    _write_text(
        manifest_path,
        json.dumps(run_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return ExperimentResult(
        run_directory,
        manifest_path,
        prediction_path,
        report_paths,
        corpus_fingerprint,
        prediction_fingerprint,
        evaluation_fingerprint,
        reused,
    )


def _load_corpus(
    config: ResolvedConfig,
) -> tuple[tuple[CorpusRecord, ...], DatasetManifest]:
    raw = (config.model_extra or {}).get("corpus")
    if not isinstance(raw, dict):
        raise ExperimentError("Experiment configuration requires a corpus section")
    params = raw.get("params", {})
    if not isinstance(params, dict) or not isinstance(params.get("path"), str):
        raise ExperimentError("corpus.params.path must name a canonical JSONL artifact")
    try:
        manifest_path = params.get("manifest_path", params.get("manifest"))
        if manifest_path is not None and not isinstance(manifest_path, str):
            raise ExperimentError("corpus.params.manifest_path must be a path string")
        return read_canonical_dataset(
            Path(params["path"]),
            Path(manifest_path) if manifest_path is not None else None,
        )
    except (OSError, CanonicalSerializationError, ValueError) as error:
        raise ExperimentError(f"Unable to load canonical corpus: {error}") from error


def _output_root(config: ResolvedConfig) -> Path:
    output = config.output
    if output is None or output.root is None:
        raise ExperimentError("output.root is required for an experiment")
    return Path(output.root)


def _run_resolver(
    resolver_executor: ResolverExecutor,
    documents: dict[str, Document],
    error_policy: ExecutionErrorPolicy,
    prediction_path: Path,
    corpus_fingerprint: str,
) -> PredictionArtifact:
    """Execute and persist predictions through the resolver boundary."""

    run_result = resolver_executor.resolve_documents(
        tuple(documents.values()), error_policy=error_policy
    )
    write_prediction_artifact(
        run_result, prediction_path, dataset_fingerprint=corpus_fingerprint
    )
    return PredictionArtifact.from_run(
        run_result, dataset_fingerprint=corpus_fingerprint
    )


def _reuse_setting(config: ResolvedConfig) -> bool:
    output = config.output
    extras = output.model_extra if output is not None else None
    return bool((extras or {}).get("reuse_cached_predictions", False))


def _component_json(component: object) -> str:
    if hasattr(component, "model_dump"):
        return json.dumps(
            component.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
    return json.dumps(component, sort_keys=True, separators=(",", ":"))


def _write_reports(
    config: ResolvedConfig, context: ReportContext, directory: Path
) -> tuple[Path, ...]:
    paths: list[Path] = []
    for index, reporter in enumerate(create_reporters(config)):
        suffix = (
            "html"
            if reporter.identity == "html_error_report"
            else ("json" if reporter.identity == "json" else "tsv")
        )
        path = directory / f"report-{index:02d}-{reporter.identity}.{suffix}"
        reporter.write(context, path)
        paths.append(path)
    return tuple(paths)


def _evaluation_text(context: ReportContext) -> str:
    from abrex.reporting.reporters import JSONReporter

    return JSONReporter().render(context)


def _run_manifest(
    config: ResolvedConfig,
    config_paths: tuple[Path, ...],
    corpus_manifest: DatasetManifest,
    corpus_fingerprint: str,
    resolver_key: str,
    resolver_version: str,
    resolver_config: str,
    prediction_path: Path,
    prediction_fingerprint: str,
    evaluation_path: Path,
    evaluation_fingerprint: str,
    *,
    config_fingerprint: str,
    reused: bool,
) -> dict[str, object]:
    return {
        "schema_version": "run-manifest-v1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git": _git_metadata(),
        "config_paths": [str(path) for path in config_paths],
        "config_fingerprint": config_fingerprint,
        "resolved_config": config.model_dump(mode="json", exclude_none=True),
        "seed": config.project.seed if config.project else None,
        "corpus": {
            "fingerprint": corpus_fingerprint,
            "dataset_id": corpus_manifest.dataset_id,
        },
        "resolver": {
            "key": resolver_key,
            "version": resolver_version,
            "config": json.loads(resolver_config),
        },
        "environment": _environment_snapshot(),
        "predictions": {
            "path": str(prediction_path),
            "fingerprint": prediction_fingerprint,
            "reused": reused,
        },
        "evaluation": {
            "path": str(evaluation_path),
            "fingerprint": evaluation_fingerprint,
        },
    }


def _environment_snapshot() -> dict[str, object]:
    packages: dict[str, str] = {}
    for name in ("abrex", "pydantic", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "unavailable"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
    }


def _git_metadata() -> dict[str, object]:
    try:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"), capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = (
            subprocess.run(
                ("git", "status", "--porcelain"),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            != ""
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = ["ExperimentError", "ExperimentResult", "run_experiment"]
