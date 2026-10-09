"""Validation receipts for returned Milestone C Linux executions."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.jobs import JobBundleManifest, JobResultManifest
from abrex.resolvers import read_prediction_artifact

LINUX_JOBS = {
    "campaign-2026-10-milestone-c-ab3p-linux": "ab3p",
    "campaign-2026-10-milestone-c-plodv2-pairing-linux": "plodv2_pairing",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_linux_execution_receipt(
    *,
    bundle_release_path: Path,
    bundle_manifest_path: Path,
    returned_archive_path: Path,
    imported_root: Path,
    prediction_corpus_path: Path,
    prediction_corpus_manifest_path: Path,
    output_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    """Validate a returned v2 archive and bind every imported result file."""

    release = _read_object(bundle_release_path)
    bundle = JobBundleManifest.model_validate(_read_object(bundle_manifest_path))
    if release.get("bundle_id") != bundle.bundle_id:
        raise ValueError("bundle release and bundle manifest identities differ")
    if set(job.job_id for job in bundle.jobs) != set(LINUX_JOBS):
        raise ValueError("bundle does not contain the two frozen Linux jobs")

    corpus_records, corpus_manifest = read_canonical_dataset(
        prediction_corpus_path, prediction_corpus_manifest_path
    )
    dataset_fingerprint = fingerprint_records(corpus_records)
    if dataset_fingerprint != corpus_manifest.fingerprint:
        raise ValueError("prediction corpus identity changed")
    documents = {
        record.document.document_id: record.document for record in corpus_records
    }

    with zipfile.ZipFile(returned_archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"returned archive has a corrupt member: {bad_member}")
        names = set(archive.namelist())
        forbidden = sorted(
            name
            for name in names
            if PurePosixPath(name).name.casefold().startswith("strict-gold")
            or ".annotations." in PurePosixPath(name).name.casefold()
        )
        if forbidden:
            raise ValueError(
                f"returned archive contains review/gold files: {forbidden}"
            )
        doctor = json.loads(archive.read("doctor-report.json"))
        if not isinstance(doctor, dict):
            raise TypeError("doctor-report.json must contain an object")
        if (
            doctor.get("bundle_id") != bundle.bundle_id
            or doctor.get("complete") is not True
        ):
            raise ValueError(
                "returned doctor report is incomplete or for another bundle"
            )

    job_receipts: dict[str, object] = {}
    for job_id, resolver_key in sorted(LINUX_JOBS.items()):
        result_root = imported_root / job_id
        result_path = result_root / "result.json"
        result = JobResultManifest.model_validate(_read_object(result_path))
        if result.bundle_id != bundle.bundle_id or result.job_id != job_id:
            raise ValueError(f"result identity mismatch for {job_id}")
        if result.status != "complete" or result.error is not None:
            raise ValueError(f"job did not complete cleanly: {job_id}")
        if result.dataset_fingerprint != dataset_fingerprint:
            raise ValueError(f"dataset identity mismatch for {job_id}")
        if result.resolver.get("key") != resolver_key:
            raise ValueError(f"resolver identity mismatch for {job_id}")
        for name, expected_hash in result.files.items():
            path = result_root / name
            if not path.is_file() or _sha256(path) != expected_hash:
                raise ValueError(f"result file identity mismatch: {job_id}/{name}")

        predictions_path = result_root / "predictions.jsonl"
        artifact = read_prediction_artifact(
            predictions_path,
            documents=documents,
            expected_dataset_fingerprint=dataset_fingerprint,
        )
        if artifact.resolver.key != resolver_key:
            raise ValueError(f"prediction resolver mismatch for {job_id}")
        diagnostics = Counter(
            diagnostic.code
            for record in artifact.records
            for diagnostic in record.diagnostics
        )
        failed_documents = sorted(
            record.document_id
            for record in artifact.records
            if any(
                diagnostic.code == "RESOLVER_EXECUTION_FAILED"
                for diagnostic in record.diagnostics
            )
        )
        job_receipts[job_id] = {
            "result_id": result.result_id,
            "status": result.status,
            "resolver": dict(result.resolver),
            "started_utc": result.started_utc,
            "completed_utc": result.completed_utc,
            "elapsed_seconds": result.elapsed_seconds,
            "environment": result.environment,
            "result_path": _relative(result_path, repository_root),
            "result_sha256": _sha256(result_path),
            "predictions": {
                "path": _relative(predictions_path, repository_root),
                "sha256": _sha256(predictions_path),
                "records": len(artifact.records),
                "predictions": sum(
                    len(record.predictions) for record in artifact.records
                ),
                "nonempty_records": sum(
                    bool(record.predictions) for record in artifact.records
                ),
                "diagnostics": dict(sorted(diagnostics.items())),
                "failed_documents": failed_documents,
            },
        }

    receipt: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-linux-execution-v1",
        "status": "imported_and_validated",
        "prediction_scoring_status": (
            "withheld_pending_second_review_and_adjudication"
        ),
        "bundle_id": bundle.bundle_id,
        "bundle_release_path": _relative(bundle_release_path, repository_root),
        "bundle_release_sha256": _sha256(bundle_release_path),
        "returned_archive": {
            "path": _relative(returned_archive_path, repository_root),
            "sha256": _sha256(returned_archive_path),
            "members": len(names),
            "gold_or_review_files": 0,
        },
        "doctor": doctor,
        "dataset_fingerprint": dataset_fingerprint,
        "documents": len(documents),
        "jobs": job_receipts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


__all__ = ["LINUX_JOBS", "build_linux_execution_receipt"]
