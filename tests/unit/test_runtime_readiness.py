from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from abrex.literature.pilot_models import (
    Ab3PRuntimeConfig,
    PilotConfig,
    PlodRuntimeConfig,
)
from abrex.literature.runtime_readiness import run_readiness, smoke_sections


def _config() -> PilotConfig:
    return PilotConfig(
        output_dir="unused",
        ab3p=Ab3PRuntimeConfig(
            interpreter="missing-python",
            installation_manifest="missing-manifest.json",
            installation_root="missing-root",
            cache_dir="missing-cache",
            timeout_seconds=1,
        ),
        plodv2=PlodRuntimeConfig(
            interpreter="missing-python",
            checkpoint_path="missing-model.pt",
            checkpoint_sha256="0" * 64,
            timeout_seconds=1,
        ),
    )


def test_smoke_input_is_fixed_unicode_repeated_and_empty() -> None:
    sections = smoke_sections()
    assert [section.heading for section in sections] == ["unicode", "repeated", "empty"]
    assert any(ord(char) > 0xFFFF for char in sections[0].canonical_text)
    assert sections[1].canonical_text.count("MRI") == 2
    assert len({section.canonical_text_sha256 for section in sections}) == 3


def test_readiness_preserves_failure_states_and_separates_plod_outputs(
    tmp_path: Path,
) -> None:
    report = run_readiness(_config(), tmp_path)
    methods = {item.method_id: item for item in report.methods}
    assert methods["schwartz_hearst"].status == "available"
    assert methods["ab3p"].status in {"failed", "unavailable"}
    assert methods["plodv2"].status in {"failed", "unavailable"}
    assert methods["plodv2_pairing"].status in {"failed", "unavailable"}
    assert methods["plodv2"].method_id != methods["plodv2_pairing"].method_id
    assert report.cache_identity_checks["changed_input_changes_identity"] is True


@pytest.mark.parametrize("require_all,expected_exit", [(False, 0), (True, 1)])
def test_readiness_cli_saves_diagnostics_and_enforces_required_methods(
    tmp_path: Path, require_all: bool, expected_exit: int
) -> None:
    root = Path(__file__).parents[2]
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump({"literature_pilot": _config().model_dump(mode="json")}),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(root / "scripts/run_t058_readiness.py"),
        str(config),
        "--output",
        str(output),
        "--runtime-dir",
        str(tmp_path / "workers"),
    ]
    if require_all:
        command.append("--require-all")
    result = subprocess.run(
        command,
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected_exit, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert any(item["status"] == "unavailable" for item in report["methods"])
