"""Subprocess and portable-cache mechanics for the Ab3P adapter."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from abrex.domain import Document
from abrex.resolvers.adapters.ab3p import (
    AB3P_ADAPTER_VERSION,
    Ab3PResolverConfig,
    build_ab3p_input,
)

CACHE_SCHEMA_VERSION = "ab3p-cache-v1"

logger = logging.getLogger(__name__)


class Ab3PExecutionError(RuntimeError):
    """A live Ab3P invocation failed."""


class Ab3PCacheMiss(LookupError):
    """No compatible cached execution exists."""


@dataclass(frozen=True, slots=True)
class Ab3PRawResult:
    """Raw execution evidence used identically by live and cached paths."""

    stdout: str
    stderr: str
    exit_status: int
    timed_out: bool = False
    executable_sha256: str | None = None


def cache_key(document: Document, config: Ab3PResolverConfig) -> str:
    """Return a path-independent key for document and semantic invocation data."""

    payload = {
        "adapter": AB3P_ADAPTER_VERSION,
        "document_id": document.document_id,
        "document_sha256": _sha256(document.text.encode("utf-8")),
        "input_sha256": _sha256(build_ab3p_input(document).encode("utf-8")),
        "installation_label": config.installation_label,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


class Ab3PCache:
    """JSON cache whose entries contain raw input, output, and provenance."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self, document: Document, config: Ab3PResolverConfig) -> Ab3PRawResult:
        key = cache_key(document, config)
        logger.debug("Reading Ab3P cache key=%s document=%s", key, document.document_id)
        try:
            data = json.loads((self.path / f"{key}.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise Ab3PCacheMiss(
                f"No compatible Ab3P cache entry for {document.document_id!r}"
            ) from error
        expected_input = build_ab3p_input(document)
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != CACHE_SCHEMA_VERSION
            or data.get("cache_key") != key
            or data.get("document_id") != document.document_id
            or data.get("input_text") != expected_input
            or data.get("input_sha256") != _sha256(expected_input.encode("utf-8"))
        ):
            raise Ab3PCacheMiss(
                f"Incompatible Ab3P cache entry for {document.document_id!r}"
            )
        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            raise Ab3PCacheMiss(
                f"Incompatible Ab3P cache entry for {document.document_id!r}"
            )
        digest = provenance.get("executable_sha256")
        return Ab3PRawResult(
            str(data["stdout"]),
            str(data["stderr"]),
            int(data["exit_status"]),
            bool(data["timed_out"]),
            str(digest) if digest else None,
        )

    def write(
        self, document: Document, config: Ab3PResolverConfig, result: Ab3PRawResult
    ) -> Path:
        key = cache_key(document, config)
        logger.debug("Writing Ab3P cache key=%s document=%s", key, document.document_id)
        input_text = build_ab3p_input(document)
        data = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": key,
            "document_id": document.document_id,
            "document_sha256": _sha256(document.text.encode("utf-8")),
            "input_text": input_text,
            "input_sha256": _sha256(input_text.encode("utf-8")),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_status": result.exit_status,
            "timed_out": result.timed_out,
            "provenance": {
                "configured_executable": config.executable,
                "invocation_arguments": [
                    "<configured executable>",
                    "<temporary input file>",
                ],
                "executable_sha256": result.executable_sha256,
                "installation_label": config.installation_label,
                "platform": platform.platform(),
                "created_at": datetime.now(UTC).isoformat(),
            },
        }
        self.path.mkdir(parents=True, exist_ok=True)
        target = self.path / f"{key}.json"
        target.write_text(
            json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target


def run_ab3p(document: Document, config: Ab3PResolverConfig) -> Ab3PRawResult:
    """Run a configured executable without shell interpolation."""

    if not config.executable:
        raise Ab3PExecutionError("Ab3P subprocess backend requires executable")
    input_text = build_ab3p_input(document)
    logger.info("Starting Ab3P resolver for %s", document.document_id)
    try:
        with tempfile.TemporaryDirectory(prefix="abrex-ab3p-") as directory:
            input_path = Path(directory) / "input.txt"
            input_path.write_bytes(input_text.encode("utf-8"))
            try:
                argv = [config.executable, os.fspath(input_path)]
                logger.debug("Ab3P executable=%s argv=%s", config.executable, argv)
                completed = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="strict",
                    timeout=config.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise Ab3PExecutionError(
                    f"Ab3P timed out for {document.document_id!r}"
                ) from error
            except (OSError, UnicodeError) as error:
                raise Ab3PExecutionError(
                    f"Unable to execute Ab3P for {document.document_id!r}: {error}"
                ) from error
    except OSError as error:
        raise Ab3PExecutionError(
            f"Unable to prepare Ab3P input for {document.document_id!r}: {error}"
        ) from error
    executable_digest: str | None = None
    with suppress(OSError):
        executable_digest = _sha256(Path(config.executable).read_bytes())
    result = Ab3PRawResult(
        completed.stdout,
        completed.stderr,
        completed.returncode,
        executable_sha256=executable_digest,
    )
    if completed.returncode != 0:
        logger.error(
            "Ab3P exited with status %d for %s",
            completed.returncode,
            document.document_id,
        )
        stderr = completed.stderr.strip()
        if len(stderr) > 500:
            stderr = stderr[:500] + "..."
        raise Ab3PExecutionError(
            f"Ab3P exited with status {completed.returncode} for "
            f"{document.document_id!r}: {stderr}"
        )
    logger.info("Ab3P completed for %s", document.document_id)
    if result.stderr:
        logger.debug("Ab3P stderr for %s: %.500s", document.document_id, result.stderr)
    return result


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "Ab3PCache",
    "Ab3PCacheMiss",
    "Ab3PExecutionError",
    "Ab3PRawResult",
    "CACHE_SCHEMA_VERSION",
    "cache_key",
    "run_ab3p",
]
