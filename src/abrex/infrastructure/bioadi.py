"""Subprocess boundary and identity checks for the optional BioADI runtime."""

from __future__ import annotations

import hashlib
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from abrex.domain import Document

if TYPE_CHECKING:
    from abrex.resolvers.adapters.bioadi import BioADIResolverConfig


class BioADIExecutionError(RuntimeError):
    """BioADI could not be invoked or its process timed out."""


@dataclass(frozen=True, slots=True)
class BioADIRawResult:
    stdout: str
    stderr: str
    exit_status: int
    timed_out: bool = False


def _wsl_path(path: Path | str) -> str:
    value = str(path)
    if len(value) >= 2 and value[1] == ":":
        return "/mnt/" + value[0].lower() + value[2:].replace("\\", "/")
    return value


def _input_text(document: Document) -> str:
    return f"{document.document_id}\n{document.text}\n"


def run_bioadi(document: Document, config: BioADIResolverConfig) -> BioADIRawResult:
    """Run the pinned Java entry point through WSL with bounded resources."""

    if not isinstance(document, Document):
        raise TypeError("document must be a Document")
    jar_path = Path(config.jar_path)
    if not jar_path.is_file():
        raise BioADIExecutionError(f"BioADI JAR does not exist: {jar_path}")
    with tempfile.TemporaryDirectory(prefix="abrex-bioadi-") as directory:
        input_path = Path(directory) / "input.txt"
        input_path.write_text(_input_text(document), encoding="utf-8", newline="\n")
        java = shlex.quote(_wsl_path(config.java_path))
        jar = shlex.quote(_wsl_path(jar_path.resolve()))
        input_file = shlex.quote(_wsl_path(input_path.resolve()))
        command = (
            f"timeout {config.timeout_seconds}s {java} -Xmx{config.heap_mb}m "
            f"-Dfile.encoding=UTF-8 -cp {jar} aiiaadi.util.Executor {input_file}"
        )
        try:
            completed = subprocess.run(
                ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=config.timeout_seconds + 5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise BioADIExecutionError(f"Unable to execute BioADI: {error}") from error
    return BioADIRawResult(
        completed.stdout,
        completed.stderr,
        completed.returncode,
        completed.returncode == 124,
    )


def bioadi_identity(config: BioADIResolverConfig) -> dict[str, str]:
    """Verify the supplied JAR digest and return path-independent cache identity."""

    jar_path = Path(config.jar_path)
    if not jar_path.is_file():
        raise BioADIExecutionError(f"BioADI JAR does not exist: {jar_path}")
    digest = hashlib.sha256(jar_path.read_bytes()).hexdigest()
    if digest.lower() != config.jar_sha256.lower():
        raise BioADIExecutionError(
            f"BioADI JAR digest mismatch: expected {config.jar_sha256}, got {digest}"
        )
    return {
        "adapter_version": "1",
        "jar_sha256": digest,
        "java_path": config.java_path,
        "java_sha256": config.java_sha256 or "unverified",
        "mapping_policy": config.mapping_policy,
        "entry_point": "aiiaadi.util.Executor",
    }


__all__ = [
    "BioADIExecutionError",
    "BioADIRawResult",
    "bioadi_identity",
    "run_bioadi",
]
