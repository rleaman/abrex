"""Tests for the cross-platform quality-gate orchestration."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_gate_module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "quality_gate.py"
    spec = importlib.util.spec_from_file_location("quality_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_gate_creates_parent_and_stops_on_failure(tmp_path: Path) -> None:
    gate = _load_gate_module()
    marker = tmp_path / "should-not-exist"
    commands = [
        (sys.executable, "-c", "raise SystemExit(23)"),
        (sys.executable, "-c", f"from pathlib import Path; Path(r'{marker}').touch()"),
    ]

    status = gate.run_gate(commands, root=tmp_path, basetemp_name="test")

    assert status == 23
    assert (tmp_path / ".pytest-tmp").is_dir()
    assert not marker.exists()


def test_run_command_prefers_checkout_source_over_installed_package(
    tmp_path: Path,
) -> None:
    gate = _load_gate_module()
    root = Path(__file__).parents[2]
    output = tmp_path / "origin.txt"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "env313" / "Lib" / "site-packages")
    original = os.environ.get("PYTHONPATH")
    try:
        os.environ["PYTHONPATH"] = environment["PYTHONPATH"]
        status = gate.run_command(
            (
                sys.executable,
                "-c",
                "from pathlib import Path; import abrex; "
                f"Path(r'{output}').write_text(abrex.__file__, encoding='utf-8')",
            ),
            cwd=root,
        )
    finally:
        if original is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = original
    assert status == 0
    assert output.read_text(encoding="utf-8").startswith(str(root / "src"))


def test_development_python_prefers_requested_then_local_environment(
    tmp_path: Path,
) -> None:
    gate = _load_gate_module()
    requested = tmp_path / "requested-python"
    assert gate.development_python(tmp_path, requested) == requested.resolve()

    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    local = tmp_path / ".venv" / relative
    local.parent.mkdir(parents=True)
    local.touch()
    assert gate.development_python(tmp_path) == local.resolve()


def test_source_import_verifier_reports_checkout_origin() -> None:
    root = Path(__file__).parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    completed = subprocess.run(
        (
            sys.executable,
            str(root / "scripts" / "verify_source_import.py"),
            "--root",
            str(root),
        ),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert str((root / "src" / "abrex").resolve()) in completed.stdout


def test_gate_commands_verify_source_before_tools_and_use_selected_python(
    tmp_path: Path,
) -> None:
    gate = _load_gate_module()
    selected = tmp_path / "python"

    fast = gate._commands(
        root=tmp_path,
        python=selected,
        full=False,
        basetemp_name="fast",
    )
    full = gate._commands(
        root=tmp_path,
        python=selected,
        full=True,
        basetemp_name="full",
    )

    assert fast[0] == (
        str(selected),
        str(Path("scripts") / "verify_source_import.py"),
        "--root",
        str(tmp_path),
    )
    assert all(command[0] == str(selected) for command in fast)
    assert fast[-1][2:5] == ("pytest", "tests/unit", "tests/contract")
    assert full[-1][2:4] == ("pytest", "--cov")
