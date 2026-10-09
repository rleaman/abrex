"""Tests for portable prediction-only execution bundles."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from abrex.jobs import (
    JobBundleError,
    bundle_status,
    doctor_bundle,
    execute_job,
    import_results,
    inspect_bundle,
    prepare_bundle,
)
from abrex.jobs import service as job_service

EXPERIMENT = Path("docs/examples/experiment-toy.yaml")


def test_bundle_is_gold_free_content_addressed_and_has_launchers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"

    manifest = prepare_bundle((EXPERIMENT,), root)
    verified = inspect_bundle(root)

    assert verified.bundle_id == manifest.bundle_id
    assert verified.schema_version == "job-bundle-v1"
    assert len(verified.jobs) == 1
    document_text = (root / verified.jobs[0].documents_path).read_text("utf-8")
    assert '"schema_version":"documents-v1"' in document_text
    assert "gold_annotations" not in document_text
    assert (root / "doctor.sh").read_bytes().find(b"\r\n") == -1
    assert (root / "run-job.sh").is_file()
    assert (root / "run-all.sh").is_file()
    assert (root / "collect-results.sh").is_file()
    assert (root / "submit.slurm").is_file()
    assert (root / "README.md").is_file()
    assert (root / "source/abrex/__init__.py").is_file()
    assert verified.source["embedded_package"] == "source/abrex"
    assert verified.source["embedded_source_schema"] == "abrex-source-snapshot-v1"
    assert b"PYTHONPATH" in (root / "doctor.sh").read_bytes()
    assert b"ABREX_JOB_DOCTOR_PYTHON" in (root / "doctor.sh").read_bytes()
    assert b"ABREX_JOB_DOCTOR_PYTHON" in (root / "collect-results.sh").read_bytes()
    run_all = (root / "run-all.sh").read_text(encoding="utf-8")
    assert 'if ! "$ROOT/run-job.sh" "$job"; then status=1; fi' in run_all
    assert run_all.index('"$ROOT/collect-results.sh"') < run_all.index('exit "$status"')
    assert manifest.jobs[0].python_executable == "python"
    assert manifest.jobs[0].python_environment.startswith("ABREX_JOB_PYTHON_")
    assert not (root / "setup-runtime.sh").exists()


def test_bundle_preserves_resolver_execution_policy(tmp_path: Path) -> None:
    experiment = tmp_path / "collect.yaml"
    experiment.write_text(
        EXPERIMENT.read_text(encoding="utf-8").replace(
            "resolver:\n  type: toy",
            "resolver:\n  type: toy\n  error_policy: collect",
        ),
        encoding="utf-8",
    )
    root = tmp_path / "bundle"

    bundle = prepare_bundle((experiment,), root)

    config = json.loads((root / bundle.jobs[0].config_path).read_text("utf-8"))
    assert config["resolver"]["error_policy"] == "collect"
    assert config["resolver"]["validation_mode"] == "strict"


def test_job_round_trip_is_resumable_and_import_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    bundle = prepare_bundle((EXPERIMENT,), root)
    job = bundle.jobs[0]

    first = execute_job(root, job.job_id)
    second = execute_job(root, job.job_id)
    status = bundle_status(root)
    imported = import_results(root, root / "results", tmp_path / "imported")
    reused = import_results(root, root / "results", tmp_path / "imported")

    assert first.status == "complete"
    assert second.result_id == first.result_id
    assert status["jobs"] == [{"job_id": job.job_id, "status": "complete"}]
    assert imported["imported"] == [job.job_id]
    assert reused["reused"] == [job.job_id]
    result = json.loads(
        (tmp_path / "imported" / job.job_id / "result.json").read_text("utf-8")
    )
    assert result["schema_version"] == "job-result-v1"
    assert result["dataset_fingerprint"] == job.dataset_fingerprint


def test_result_tampering_and_bundle_tampering_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    bundle = prepare_bundle((EXPERIMENT,), root)
    job = bundle.jobs[0]
    execute_job(root, job.job_id)
    predictions = root / "results" / job.job_id / "predictions.jsonl"
    predictions.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(JobBundleError, match="checksum mismatch"):
        import_results(root, root / "results", tmp_path / "imported")

    config = root / job.config_path
    config.write_text("{}\n", encoding="utf-8")
    with pytest.raises(JobBundleError, match="bundle checksum mismatch"):
        inspect_bundle(root)


def test_import_rejects_archive_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    prepare_bundle((EXPERIMENT,), root)
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", "unsafe")

    with pytest.raises(JobBundleError, match="unsafe result archive member"):
        import_results(root, archive, tmp_path / "imported")

    assert not (tmp_path / "outside.txt").exists()


def test_doctor_reports_current_checkout_without_installing(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    prepare_bundle((EXPERIMENT,), root, backend="shell")

    report = doctor_bundle(root)

    assert report["schema_version"] == "job-doctor-v1"
    assert report["complete"] is True
    checks = report["checks"]
    assert isinstance(checks, list)
    assert {item["name"] for item in checks if isinstance(item, dict)} == {
        "python",
        "source_commit",
    }
    assert not (root / "submit.slurm").exists()


def test_portable_runtime_placeholders_survive_local_config_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "experiment.yaml"
    path.write_text(
        "resolver:\n  params:\n    root: ${ABREX_AB3P_ROOT}\n"
        "corpus:\n  path: ${LOCAL_CORPUS}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ABREX_AB3P_ROOT", "local-should-not-be-baked-in")
    monkeypatch.setenv("LOCAL_CORPUS", "local-corpus.jsonl")

    environment = job_service._portable_config_environment(path)

    assert environment["ABREX_AB3P_ROOT"] == "${ABREX_AB3P_ROOT}"
    assert environment["LOCAL_CORPUS"] == "local-corpus.jsonl"


def test_external_runtime_bundle_contains_fresh_server_setup(tmp_path: Path) -> None:
    root = tmp_path / "bundle"

    manifest = prepare_bundle(
        (
            Path("configs/experiments/T060-ab3p-linux.yaml"),
            Path("configs/experiments/T060-plodv2-linux.yaml"),
        ),
        root,
    )

    setup = (root / "setup-runtime.sh").read_text(encoding="utf-8")
    guide = (root / "README.md").read_text(encoding="utf-8")
    assert "python3.13" in setup
    assert "-m venv" in setup
    assert "uv_tool" not in setup
    assert "41130cddfcba1449ba612905d4a51274f8f565a8" in setup
    assert "3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277" in setup
    assert "ABREX_JOB_PYTHON_T060_AB3P_LINUX" in setup
    assert "ABREX_JOB_PYTHON_T060_PLODV2_PAIRING_LINUX" in setup
    assert (root / "runtime-setup/build_ab3p.py").is_file()
    assert (root / "runtime-setup/ab3p_offset_frontend.C").is_file()
    assert (root / "runtime-setup/requirements-core.lock").is_file()
    assert (root / "runtime-setup/plod-runtime-requirements.txt").is_file()
    assert "./setup-runtime.sh --all" in guide
    assert "copy that bundle's `runtime.env`" in guide
    assert "/home/rleaman" not in guide
    assert "setup-runtime.sh" in manifest.files
    assert b'source "$ROOT/runtime.env"' in (root / "doctor.sh").read_bytes()


def test_job_execution_expands_required_server_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = {
        "root": "${ABREX_AB3P_ROOT}",
        "nested": ["literal", "${ABREX_PLODV2_CHECKPOINT}"],
    }
    monkeypatch.setenv("ABREX_AB3P_ROOT", "/opt/ab3p")
    monkeypatch.setenv("ABREX_PLODV2_CHECKPOINT", "/models/plod.bin")

    assert job_service._expand_environment(value) == {
        "root": "/opt/ab3p",
        "nested": ["literal", "/models/plod.bin"],
    }


def test_job_execution_reports_missing_server_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABREX_AB3P_ROOT", raising=False)

    with pytest.raises(JobBundleError, match="ABREX_AB3P_ROOT"):
        job_service._expand_environment("${ABREX_AB3P_ROOT}")
