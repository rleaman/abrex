"""Shared pytest configuration for the repository test suite."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from _pytest import tmpdir as pytest_tmpdir

_ORIGINAL_MAKE_NUMBERED_DIR = cast(
    Callable[[Path, str, int], Path],
    pytest_tmpdir.make_numbered_dir,  # type: ignore[attr-defined]
)


def _windows_safe_make_numbered_dir(root: Path, prefix: str, mode: int = 0o700) -> Path:
    """Avoid Python 3.13's restrictive Windows ACL for mode 0o700."""

    del mode
    return _ORIGINAL_MAKE_NUMBERED_DIR(root, prefix, 0o777)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Any) -> None:
    """Keep pytest temporary paths usable under managed Windows tokens."""

    if os.name != "nt":
        return
    factory = config._tmp_path_factory
    requested = config.option.basetemp
    base = (
        Path(requested).absolute()
        if requested is not None
        else Path(tempfile.gettempdir())
        / f"abrex-pytest-{os.getpid()}-{uuid.uuid4().hex}"
    )
    if base.exists():
        base = base.with_name(f"{base.name}-{uuid.uuid4().hex}")
    base.mkdir(mode=0o777, parents=True, exist_ok=False)
    factory._basetemp = base.resolve()
    pytest_tmpdir.make_numbered_dir = (  # type: ignore[attr-defined]
        _windows_safe_make_numbered_dir
    )
