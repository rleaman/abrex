"""Prepare, execute, inspect, and import portable resolver jobs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from abrex.config import ResolvedConfig, load_resolved_config
from abrex.corpora import fingerprint_records, read_canonical_jsonl
from abrex.domain import Document
from abrex.jobs.models import JobBundleManifest, JobResultManifest, PortableJob
from abrex.resolvers import (
    create_resolver_executor,
    resolver_config_from_resolved,
    write_prediction_artifact,
)

BUNDLE_MANIFEST = "bundle.json"
RESULT_MANIFEST = "result.json"
DOCUMENT_SCHEMA_VERSION = "documents-v1"


class JobBundleError(ValueError):
    """Raised when a portable job bundle is invalid or unsafe."""


def prepare_bundle(
    experiment_paths: Sequence[Path],
    output: Path,
    *,
    backend: str = "both",
) -> JobBundleManifest:
    """Create a prediction-only portable bundle from experiment configs."""

    if not experiment_paths:
        raise JobBundleError("at least one experiment configuration is required")
    if backend not in {"shell", "slurm", "both"}:
        raise JobBundleError("backend must be shell, slurm, or both")
    if output.exists() and any(output.iterdir()):
        raise JobBundleError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    embedded_source = _embed_source(output)
    jobs: list[PortableJob] = []
    used_ids: set[str] = set()
    for index, path in enumerate(experiment_paths, start=1):
        resolved = load_resolved_config(
            (path,), environment=_portable_config_environment(path)
        )
        resolver = resolved.component("resolver")
        records = _records_from_config(resolved)
        job_id = _unique_job_id(
            _slug(
                (resolved.project.name if resolved.project else None) or resolver.type
            ),
            used_ids,
            index,
        )
        used_ids.add(job_id)
        config_path = PurePosixPath("configs") / f"{job_id}.json"
        documents_path = PurePosixPath("documents") / f"{job_id}.jsonl"
        documents_text = _serialize_documents(record.document for record in records)
        _write_text(
            output / Path(config_path.as_posix()), _resolver_config_text(resolved)
        )
        _write_text(output / Path(documents_path.as_posix()), documents_text)
        jobs.append(
            PortableJob(
                job_id=job_id,
                resolver_key=resolver.type,
                config_path=config_path.as_posix(),
                documents_path=documents_path.as_posix(),
                dataset_fingerprint=fingerprint_records(records),
                documents_fingerprint=_sha256(documents_text.encode("utf-8")),
                required_capabilities=_required_capabilities(resolver.type),
                python_executable=_job_python(resolved),
                python_environment=_job_python_environment(job_id),
            )
        )
    _write_launchers(output, tuple(jobs), backend=backend)
    _write_bundle_guide(output, tuple(jobs))
    files = _bundle_file_hashes(output)
    source = {**_source_identity(), **embedded_source}
    bundle_id = _sha256_json(
        {
            "schema_version": "job-bundle-v1",
            "source": source,
            "jobs": [job.model_dump(mode="json") for job in jobs],
            "files": files,
        }
    )
    manifest = JobBundleManifest(
        bundle_id=bundle_id,
        created_utc=_now(),
        source=source,
        jobs=tuple(jobs),
        files=files,
    )
    _write_json(output / BUNDLE_MANIFEST, manifest.model_dump(mode="json"))
    return manifest


def inspect_bundle(root: Path) -> JobBundleManifest:
    """Load a bundle and verify its identity and every declared file."""

    manifest = JobBundleManifest.model_validate(_read_json(root / BUNDLE_MANIFEST))
    expected_id = _sha256_json(
        {
            "schema_version": manifest.schema_version,
            "source": manifest.source,
            "jobs": [job.model_dump(mode="json") for job in manifest.jobs],
            "files": manifest.files,
        }
    )
    if manifest.bundle_id != expected_id:
        raise JobBundleError("bundle identity does not match its manifest")
    for relative, expected in manifest.files.items():
        path = _safe_child(root, relative)
        if not path.is_file():
            raise JobBundleError(f"bundle file is missing: {relative}")
        actual = _sha256_file(path)
        if actual != expected:
            raise JobBundleError(f"bundle checksum mismatch: {relative}")
    return manifest


def doctor_bundle(root: Path) -> dict[str, object]:
    """Report runtime prerequisites without installing or modifying them."""

    manifest = inspect_bundle(root)
    checks: list[dict[str, object]] = []
    checks.append(
        {
            "name": "python",
            "status": "available" if sys.version_info >= (3, 13) else "unavailable",
            "detail": sys.version.split()[0],
        }
    )
    embedded = manifest.source.get("embedded_package")
    expected_commit = manifest.source.get("git_commit")
    current_commit = _git_value(("git", "rev-parse", "HEAD"))
    source_available = isinstance(embedded, str) and (root / embedded).is_dir()
    checks.append(
        {
            "name": "source_commit",
            "status": (
                "available"
                if source_available
                or not expected_commit
                or current_commit == expected_commit
                else "unavailable"
            ),
            "detail": (
                f"embedded source snapshot ({expected_commit or 'uncommitted'})"
                if source_available
                else current_commit or "not a git checkout"
            ),
        }
    )
    capabilities = sorted(
        {item for job in manifest.jobs for item in job.required_capabilities}
    )
    for capability in capabilities:
        if capability == "typesafe":
            available = bool(os.environ.get("TYPESAFE_API_KEY"))
            detail = (
                "TYPESAFE_API_KEY is set" if available else "TYPESAFE_API_KEY is absent"
            )
        else:
            available, detail = _probe_resolvers(root, manifest, capability)
        checks.append(
            {
                "name": capability,
                "status": "available" if available else "unavailable",
                "detail": detail,
            }
        )
    return {
        "schema_version": "job-doctor-v1",
        "bundle_id": manifest.bundle_id,
        "complete": all(check["status"] == "available" for check in checks),
        "checks": checks,
    }


def execute_job(root: Path, job_id: str) -> JobResultManifest:
    """Execute one checksummed bundle job and publish a resumable result."""

    manifest = inspect_bundle(root)
    job = _job_by_id(manifest, job_id)
    result_root = root / "results" / job.job_id
    result_path = result_root / RESULT_MANIFEST
    if result_path.is_file():
        existing = _read_result(result_path)
        if (
            existing.status == "complete"
            and existing.bundle_id == manifest.bundle_id
            and existing.job_id == job.job_id
        ):
            _verify_result_files(result_root, existing)
            return existing
    result_root.mkdir(parents=True, exist_ok=True)
    started_at = _now()
    started = time.perf_counter()
    events: list[dict[str, object]] = [
        {"timestamp_utc": started_at, "event": "started", "job_id": job.job_id}
    ]
    status = "complete"
    error_data: dict[str, str] | None = None
    resolver_identity = {"key": job.resolver_key, "version": "unknown"}
    try:
        documents_path = _safe_child(root, job.documents_path)
        if _sha256_file(documents_path) != job.documents_fingerprint:
            raise JobBundleError(
                "document input checksum changed after bundle validation"
            )
        documents = _read_documents(documents_path)
        config = ResolvedConfig.model_validate(
            _expand_environment(_read_json(_safe_child(root, job.config_path)))
        )
        executor = create_resolver_executor(resolver_config_from_resolved(config))
        resolver_identity = {
            "key": executor.metadata.key,
            "version": executor.metadata.version,
        }
        result = executor.resolve_documents(documents)
        predictions_path = result_root / "predictions.jsonl"
        write_prediction_artifact(
            result,
            predictions_path,
            dataset_fingerprint=job.dataset_fingerprint,
        )
        events.append(
            {
                "timestamp_utc": _now(),
                "event": "predictions_written",
                "records": len(result.records),
                "errors": len(result.execution_errors),
            }
        )
    except Exception as error:  # boundary: preserve exact worker failure
        status = "failed"
        error_data = {"type": type(error).__name__, "message": str(error)}
        events.append(
            {
                "timestamp_utc": _now(),
                "event": "failed",
                "error_type": type(error).__name__,
                "message": str(error),
            }
        )
    completed_at = _now()
    events.append(
        {"timestamp_utc": completed_at, "event": "completed", "status": status}
    )
    _write_jsonl(result_root / "execution.jsonl", events)
    files = {
        path.name: _sha256_file(path)
        for path in sorted(result_root.iterdir())
        if path.is_file() and path.name != RESULT_MANIFEST
    }
    payload: dict[str, object] = {
        "schema_version": "job-result-v1",
        "bundle_id": manifest.bundle_id,
        "job_id": job.job_id,
        "status": status,
        "started_utc": started_at,
        "completed_utc": completed_at,
        "elapsed_seconds": time.perf_counter() - started,
        "dataset_fingerprint": job.dataset_fingerprint,
        "documents_fingerprint": job.documents_fingerprint,
        "resolver": resolver_identity,
        "environment": _environment(),
        "files": files,
        "error": error_data,
    }
    result_manifest = JobResultManifest(
        result_id=_sha256_json(payload),
        **payload,  # type: ignore[arg-type]
    )
    _write_json(result_path, result_manifest.model_dump(mode="json"))
    return result_manifest


def bundle_status(root: Path) -> dict[str, object]:
    """Return verified completion state for every job in a bundle."""

    manifest = inspect_bundle(root)
    states: list[dict[str, str]] = []
    for job in manifest.jobs:
        result_path = root / "results" / job.job_id / RESULT_MANIFEST
        if not result_path.is_file():
            states.append({"job_id": job.job_id, "status": "pending"})
            continue
        try:
            result = _read_result(result_path)
            _validate_result_for_job(
                root / "results" / job.job_id, result, manifest, job
            )
        except (OSError, ValueError) as error:
            states.append(
                {"job_id": job.job_id, "status": "invalid", "detail": str(error)}
            )
        else:
            states.append({"job_id": job.job_id, "status": result.status})
    return {
        "schema_version": "job-status-v1",
        "bundle_id": manifest.bundle_id,
        "jobs": states,
    }


def import_results(
    bundle_root: Path, source: Path, destination: Path
) -> dict[str, object]:
    """Verify copied-back results and import only declared files."""

    bundle = inspect_bundle(bundle_root)
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        extracted = destination.parent / f".abrex-job-import-{uuid.uuid4().hex}"
        extracted.mkdir(mode=0o777)
        try:
            _safe_extract_zip(source, extracted)
            return _import_result_tree(bundle, extracted, destination)
        finally:
            shutil.rmtree(extracted, ignore_errors=True)
    return _import_result_tree(bundle, source, destination)


def _import_result_tree(
    bundle: JobBundleManifest, source: Path, destination: Path
) -> dict[str, object]:
    manifests = sorted(source.rglob(RESULT_MANIFEST))
    if not manifests:
        raise JobBundleError(f"no {RESULT_MANIFEST} files found under {source}")
    imported: list[str] = []
    reused: list[str] = []
    seen: set[str] = set()
    for path in manifests:
        result = _read_result(path)
        if result.job_id in seen:
            raise JobBundleError(f"duplicate result for job {result.job_id!r}")
        seen.add(result.job_id)
        job = _job_by_id(bundle, result.job_id)
        result_root = path.parent
        _validate_result_for_job(result_root, result, bundle, job)
        target = destination / result.job_id
        target_manifest = target / RESULT_MANIFEST
        if target_manifest.is_file():
            existing = _read_result(target_manifest)
            if existing.result_id == result.result_id:
                reused.append(result.job_id)
                continue
            raise JobBundleError(
                f"conflicting result already imported for {result.job_id}"
            )
        partial = destination / f".{result.job_id}.part"
        if partial.exists():
            shutil.rmtree(partial)
        partial.mkdir(parents=True, exist_ok=False)
        for name in result.files:
            shutil.copy2(_safe_child(result_root, name), partial / name)
        shutil.copy2(path, partial / RESULT_MANIFEST)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial.replace(target)
        imported.append(result.job_id)
    return {
        "schema_version": "job-import-v1",
        "bundle_id": bundle.bundle_id,
        "imported": imported,
        "reused": reused,
    }


def _records_from_config(config: ResolvedConfig) -> tuple[Any, ...]:
    corpus = config.component("corpus")
    if corpus.type != "canonical_jsonl":
        raise JobBundleError(
            "portable jobs currently require corpus.type=canonical_jsonl"
        )
    raw_path = corpus.params.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise JobBundleError("canonical corpus configuration requires params.path")
    return read_canonical_jsonl(Path(raw_path))


def _resolver_config_text(config: ResolvedConfig) -> str:
    resolver = config.component("resolver")
    payload: dict[str, object] = {
        "resolver": resolver.model_dump(mode="json"),
    }
    if config.runtime is not None:
        payload["runtime"] = config.runtime.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _serialize_documents(documents: Iterable[Document]) -> str:
    ordered = sorted(documents, key=lambda item: item.document_id)
    if len({item.document_id for item in ordered}) != len(ordered):
        raise JobBundleError("portable jobs require unique document IDs")
    return "".join(
        json.dumps(
            {
                "schema_version": DOCUMENT_SCHEMA_VERSION,
                "document_id": document.document_id,
                "text": document.text,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for document in ordered
    )


def _read_documents(path: Path) -> tuple[Document, ...]:
    documents: list[Document] = []
    with path.open("r", encoding="utf-8", newline=None) as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise TypeError("object required")
                if row.get("schema_version") != DOCUMENT_SCHEMA_VERSION:
                    raise ValueError("unsupported schema version")
                document = Document(str(row["document_id"]), str(row["text"]))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise JobBundleError(
                    f"invalid document input at line {line_number}: {error}"
                ) from error
            documents.append(document)
    if len({item.document_id for item in documents}) != len(documents):
        raise JobBundleError("document input contains duplicate IDs")
    return tuple(documents)


def _write_launchers(
    root: Path, jobs: tuple[PortableJob, ...], *, backend: str
) -> None:
    ids = " ".join(job.job_id for job in jobs)
    control_python = jobs[0]
    _write_text(
        root / "doctor.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'export PYTHONPATH="$ROOT/source${PYTHONPATH:+:$PYTHONPATH}"\n'
        f'PYTHON_BIN="${{ABREX_JOB_DOCTOR_PYTHON:-{control_python.python_executable}}}"\n'
        '"$PYTHON_BIN" -m abrex jobs doctor "$ROOT" | '
        'tee "$ROOT/doctor-report.json"\n',
    )
    _write_text(
        root / "run-job.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'export PYTHONPATH="$ROOT/source${PYTHONPATH:+:$PYTHONPATH}"\n'
        'if [[ $# -ne 1 ]]; then echo "usage: $0 JOB_ID" >&2; exit 2; fi\n'
        'case "$1" in\n'
        + "".join(
            f'  "{job.job_id}") PYTHON_BIN="${{{job.python_environment}:-'
            f'{job.python_executable}}}" ;;\n'
            for job in jobs
        )
        + '  *) echo "unknown job: $1" >&2; exit 2 ;;\n'
        + "esac\n"
        + '"$PYTHON_BIN" -m abrex jobs execute "$ROOT" "$1"\n',
    )
    _write_text(
        root / "run-all.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        f'for job in {ids}; do "$ROOT/run-job.sh" "$job"; done\n'
        '"$ROOT/collect-results.sh"\n',
    )
    _write_text(
        root / "collect-results.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        f'PYTHON_BIN="${{ABREX_JOB_DOCTOR_PYTHON:-{control_python.python_executable}}}"\n'
        'BUNDLE_ID="$("$PYTHON_BIN" -c \'import json,sys; '
        'print(json.load(open(sys.argv[1], encoding="utf-8"))["bundle_id"])\' '
        '"$ROOT/bundle.json")"\n'
        '"$PYTHON_BIN" -c \'from pathlib import Path; import sys,zipfile; '
        "root=Path(sys.argv[1]); out=Path(sys.argv[2]); "
        'files=([p for p in (root/"results").rglob("*") if p.is_file()] '
        '+ ([root/"doctor-report.json"] if '
        '(root/"doctor-report.json").is_file() else []) '
        '+ list(root.glob("slurm-*.out"))); '
        'z=zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED); '
        "[z.write(p,p.relative_to(root)) for p in files]; z.close()' "
        '"$ROOT" "$ROOT/abrex-results-${BUNDLE_ID}.zip"\n'
        'echo "Wrote $ROOT/abrex-results-${BUNDLE_ID}.zip"\n',
    )
    if backend in {"slurm", "both"}:
        quoted = " ".join(f'"{job.job_id}"' for job in jobs)
        _write_text(
            root / "submit.slurm",
            "#!/usr/bin/env bash\n"
            f"#SBATCH --array=0-{len(jobs) - 1}\n"
            "#SBATCH --job-name=abrex\n"
            "#SBATCH --output=slurm-%A_%a.out\n"
            "set -euo pipefail\n"
            'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            f"JOBS=({quoted})\n"
            '"$ROOT/run-job.sh" "${JOBS[$SLURM_ARRAY_TASK_ID]}"\n',
        )


def _required_capabilities(resolver_key: str) -> tuple[str, ...]:
    if resolver_key == "ab3p":
        return ("ab3p",)
    if resolver_key in {"plodv2", "plodv2_pairing"}:
        return ("plodv2",)
    if resolver_key == "jev_candidate_judge":
        return ("typesafe",)
    return ()


def _job_python(config: ResolvedConfig) -> str:
    raw = (config.model_extra or {}).get("job")
    if raw is None:
        return "python"
    if not isinstance(raw, dict):
        raise JobBundleError("job configuration must be a mapping")
    value = raw.get("python_executable", "python")
    if not isinstance(value, str) or not value.strip():
        raise JobBundleError("job.python_executable must be a non-empty string")
    return value


def _job_python_environment(job_id: str) -> str:
    return "ABREX_JOB_PYTHON_" + "".join(
        character if character.isalnum() else "_" for character in job_id.upper()
    )


def _probe_resolvers(
    root: Path, manifest: JobBundleManifest, capability: str
) -> tuple[bool, str]:
    relevant = [job for job in manifest.jobs if capability in job.required_capabilities]
    for job in relevant:
        executable = os.environ.get(job.python_environment, job.python_executable)
        script = (
            "import json,os,sys; from pathlib import Path; "
            "from abrex.config import ResolvedConfig; "
            "from abrex.resolvers import create_resolver_executor, "
            "resolver_config_from_resolved; "
            "p=Path(sys.argv[1]); value=json.loads(p.read_text(encoding='utf-8')); "
            "pattern=__import__('re').compile(r'^\\$\\{([A-Z][A-Z0-9_]*)\\}$'); "
            "expand=lambda x: os.environ[pattern.fullmatch(x).group(1)] "
            "if isinstance(x,str) and pattern.fullmatch(x) else "
            "({k:expand(v) for k,v in x.items()} if isinstance(x,dict) else "
            "([expand(v) for v in x] if isinstance(x,list) else x)); "
            "create_resolver_executor(resolver_config_from_resolved("
            "ResolvedConfig.model_validate(expand(value))))"
        )
        environment = dict(os.environ)
        source = root / "source"
        environment["PYTHONPATH"] = (
            str(source) + os.pathsep + environment.get("PYTHONPATH", "")
        )
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-c",
                    script,
                    str(_safe_child(root, job.config_path)),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                env=environment,
            )
            if completed.returncode:
                detail = (completed.stderr or completed.stdout).strip().splitlines()
                return False, (
                    f"{job.job_id} via {executable}: "
                    f"{detail[-1] if detail else 'probe failed'}"
                )
        except (OSError, subprocess.SubprocessError) as error:
            return False, f"{job.job_id}: {type(error).__name__}: {error}"
    return True, f"{len(relevant)} configured job(s) initialized"


_ENVIRONMENT_REFERENCE = re.compile(r"^\$\{(?P<name>[A-Z][A-Z0-9_]*)\}$")
_PORTABLE_RUNTIME_PREFIXES = ("ABREX_AB3P_", "ABREX_PLODV2_")


def _portable_config_environment(path: Path) -> dict[str, str]:
    """Preserve declared server-runtime placeholders while resolving other values."""

    environment = dict(os.environ)
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"\$\{([A-Z][A-Z0-9_]*)\}", text):
        name = match.group(1)
        if name.startswith(_PORTABLE_RUNTIME_PREFIXES):
            environment[name] = f"${{{name}}}"
    return environment


def _expand_environment(value: object) -> object:
    if isinstance(value, str):
        match = _ENVIRONMENT_REFERENCE.fullmatch(value)
        if match is None:
            return value
        name = match.group("name")
        resolved = os.environ.get(name)
        if not resolved:
            raise JobBundleError(
                f"required server environment variable is absent: {name}"
            )
        return resolved
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _expand_environment(item) for key, item in value.items()}
    return value


def _write_bundle_guide(root: Path, jobs: tuple[PortableJob, ...]) -> None:
    variables = "\n".join(
        f"export {job.python_environment}={job.python_executable}" for job in jobs
    )
    _write_text(
        root / "README.md",
        "# ABREX portable job bundle\n\n"
        "This directory contains immutable prediction-only inputs. It contains "
        "no gold annotations or credentials.\n\n"
        "On the Linux server, set the runtime paths required by the job configs "
        "and, if needed, override each Python interpreter:\n\n"
        "```bash\n"
        f"export ABREX_JOB_DOCTOR_PYTHON={jobs[0].python_executable}\n"
        f"{variables}\n"
        "export ABREX_AB3P_MANIFEST=/absolute/path/to/live-installation-manifest.json\n"
        "export ABREX_AB3P_ROOT=/absolute/path/to/Ab3P\n"
        "export ABREX_PLODV2_CHECKPOINT=/absolute/path/to/pytorch_model.bin\n"
        "chmod +x doctor.sh run-job.sh run-all.sh collect-results.sh\n"
        "./doctor.sh\n"
        "```\n\n"
        "Run synchronously with `./run-all.sh`, or submit `sbatch submit.slurm`. "
        "After a Slurm array finishes, run `./collect-results.sh`. Copy the "
        "result ZIP (which also includes the doctor report and Slurm logs) back "
        "to the machine that prepared this bundle and import it "
        "with `abrex jobs import BUNDLE RESULT.zip --into DESTINATION`.\n",
    )


def _bundle_file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != BUNDLE_MANIFEST
    }


def _embed_source(root: Path) -> dict[str, object]:
    """Copy the current ABREX package so a bundle executes the prepared code."""

    package_root = Path(__file__).resolve().parents[1]
    destination = root / "source" / "abrex"
    hashes: dict[str, str] = {}
    for source in sorted(package_root.rglob("*.py")):
        relative = source.relative_to(package_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[relative.as_posix()] = _sha256_file(target)
    return {
        "embedded_package": "source/abrex",
        "embedded_source_schema": "abrex-source-snapshot-v1",
        "embedded_source_sha256": _sha256_json(hashes),
        "embedded_source_files": len(hashes),
    }


def _validate_result_for_job(
    root: Path,
    result: JobResultManifest,
    bundle: JobBundleManifest,
    job: PortableJob,
) -> None:
    if result.bundle_id != bundle.bundle_id:
        raise JobBundleError("result belongs to a different bundle")
    if result.dataset_fingerprint != job.dataset_fingerprint:
        raise JobBundleError("result dataset identity does not match the job")
    if result.documents_fingerprint != job.documents_fingerprint:
        raise JobBundleError("result document identity does not match the job")
    expected = _sha256_json(result.model_dump(mode="json", exclude={"result_id"}))
    if expected != result.result_id:
        raise JobBundleError("result identity does not match its manifest")
    _verify_result_files(root, result)


def _verify_result_files(root: Path, result: JobResultManifest) -> None:
    for name, expected in result.files.items():
        path = _safe_child(root, name)
        if not path.is_file() or _sha256_file(path) != expected:
            raise JobBundleError(f"result checksum mismatch: {name}")


def _safe_extract_zip(source: Path, destination: Path) -> None:
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as error:
        raise JobBundleError(f"invalid result archive: {error}") from error
    with archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename.replace("\\", "/"))
            mode = info.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
                raise JobBundleError(f"unsafe result archive member: {info.filename}")
        archive.extractall(destination)


def _safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise JobBundleError(f"unsafe relative path: {relative!r}")
    candidate = root.joinpath(*pure.parts).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise JobBundleError(f"path escapes bundle root: {relative!r}")
    return candidate


def _job_by_id(manifest: JobBundleManifest, job_id: str) -> PortableJob:
    for job in manifest.jobs:
        if job.job_id == job_id:
            return job
    raise JobBundleError(f"unknown job {job_id!r}")


def _read_result(path: Path) -> JobResultManifest:
    return JobResultManifest.model_validate(_read_json(path))


def _environment() -> dict[str, object]:
    packages: dict[str, str] = {}
    for name in ("abrex", "pydantic", "PyYAML", "typesafe-sdk"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "unavailable"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
    }


def _source_identity() -> dict[str, object]:
    dirty = _git_value(("git", "status", "--porcelain"))
    return {
        "git_commit": _git_value(("git", "rev-parse", "HEAD")),
        "git_dirty": bool(dirty),
        "python_requires": ">=3.13",
        "package": "abrex",
        "package_version": _package_version(),
    }


def _git_value(command: tuple[str, ...]) -> str | None:
    try:
        value = subprocess.run(
            command, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return value or None


def _package_version() -> str:
    try:
        return importlib.metadata.version("abrex")
    except importlib.metadata.PackageNotFoundError:
        return "source-checkout"


def _unique_job_id(base: str, used: set[str], index: int) -> str:
    candidate = base
    if candidate not in used:
        return candidate
    return f"{candidate}-{index}"


def _slug(value: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in value
    )
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed[:80] or "job"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise JobBundleError(f"unable to read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise JobBundleError(f"JSON object required: {path}")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    _write_text(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, object]]) -> None:
    _write_text(
        path,
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for value in values
        ),
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


__all__ = [
    "JobBundleError",
    "bundle_status",
    "doctor_bundle",
    "execute_job",
    "import_results",
    "inspect_bundle",
    "prepare_bundle",
]
