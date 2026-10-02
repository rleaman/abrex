"""Cross-platform temporary working directories for subprocess adapters."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def temporary_working_directory(prefix: str) -> Iterator[Path]:
    """Yield a private-enough temporary directory usable by the current token.

    Python 3.13 gives ``mode=0o700`` special ACL behavior on Windows. Managed
    process tokens can lose access to directories created through
    ``TemporaryDirectory`` as a result, so Windows uses an unpredictable name
    with the normal inherited ACL. POSIX retains ``TemporaryDirectory``.
    """

    if os.name != "nt":
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary_name:
            yield Path(temporary_name)
        return

    root = Path(tempfile.gettempdir())
    path = root / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir(mode=0o755)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


__all__ = ["temporary_working_directory"]
