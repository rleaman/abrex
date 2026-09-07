"""Tests for the cross-platform quality-gate orchestration."""

from __future__ import annotations

import importlib.util
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
