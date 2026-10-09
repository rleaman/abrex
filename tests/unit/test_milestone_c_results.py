"""Milestone C returned Linux result receipt tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from abrex.corpora import read_canonical_dataset
from abrex.jobs import JobBundleManifest, JobResultManifest, PortableJob
from abrex.literature.milestone_c_results import (
    LINUX_JOBS,
    build_linux_execution_receipt,
)
from abrex.resolvers import (
    PredictionArtifact,
    PredictionRecord,
    ResolverMetadata,
    write_prediction_artifact,
)

ROOT = Path(__file__).parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_linux_receipt_validates_complete_prediction_artifacts(tmp_path: Path) -> None:
    corpus_path = ROOT / "docs/examples/experiment-corpus.jsonl"
    corpus_manifest_path = ROOT / "docs/examples/experiment-corpus.manifest.json"
    records, manifest = read_canonical_dataset(corpus_path, corpus_manifest_path)
    documents_fingerprint = "d" * 64
    bundle_id = "b" * 64
    jobs = tuple(
        PortableJob(
            job_id=job_id,
            resolver_key=resolver,
            config_path=f"configs/{job_id}.json",
            documents_path=f"documents/{job_id}.jsonl",
            dataset_fingerprint=manifest.fingerprint,
            documents_fingerprint=documents_fingerprint,
        )
        for job_id, resolver in LINUX_JOBS.items()
    )
    bundle = JobBundleManifest(
        bundle_id=bundle_id,
        created_utc="2026-10-07T00:00:00+00:00",
        source={},
        jobs=jobs,
        files={},
    )
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(bundle.model_dump_json(), encoding="utf-8")
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps({"bundle_id": bundle_id}), encoding="utf-8")

    imported = tmp_path / "imported"
    for job_id, resolver in LINUX_JOBS.items():
        result_root = imported / job_id
        result_root.mkdir(parents=True)
        predictions_path = result_root / "predictions.jsonl"
        artifact = PredictionArtifact(
            ResolverMetadata(resolver, "test-v1"),
            tuple(PredictionRecord(record.document.document_id) for record in records),
            dataset_fingerprint=manifest.fingerprint,
        )
        write_prediction_artifact(artifact, predictions_path)
        result = JobResultManifest(
            result_id=("a" if resolver == "ab3p" else "c") * 64,
            bundle_id=bundle_id,
            job_id=job_id,
            status="complete",
            started_utc="2026-10-07T00:00:00+00:00",
            completed_utc="2026-10-07T00:00:01+00:00",
            elapsed_seconds=1.0,
            dataset_fingerprint=manifest.fingerprint,
            documents_fingerprint=documents_fingerprint,
            resolver={"key": resolver, "version": "test-v1"},
            environment={},
            files={"predictions.jsonl": _sha(predictions_path)},
        )
        (result_root / "result.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

    returned = tmp_path / "returned.zip"
    with zipfile.ZipFile(returned, "w") as archive:
        archive.writestr(
            "doctor-report.json",
            json.dumps({"bundle_id": bundle_id, "complete": True}),
        )
    output = tmp_path / "receipt.json"

    receipt = build_linux_execution_receipt(
        bundle_release_path=release_path,
        bundle_manifest_path=bundle_path,
        returned_archive_path=returned,
        imported_root=imported,
        prediction_corpus_path=corpus_path,
        prediction_corpus_manifest_path=corpus_manifest_path,
        output_path=output,
        repository_root=ROOT,
    )

    assert receipt["status"] == "imported_and_validated"
    assert receipt["documents"] == len(records)
    jobs_receipt = cast(Mapping[str, object], receipt["jobs"])
    assert set(jobs_receipt) == set(LINUX_JOBS)
    assert json.loads(output.read_text())["bundle_id"] == bundle_id
