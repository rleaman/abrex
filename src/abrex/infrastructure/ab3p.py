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
    AB3P_OFFSET_SCHEMA_VERSION,
    AB3P_WRAPPER_VERSION,
    Ab3PResolverConfig,
    build_ab3p_input,
)

CACHE_SCHEMA_VERSION = "ab3p-cache-v3"
INSTALLATION_MANIFEST_SCHEMA_VERSION = "ab3p-installation-v1"

logger = logging.getLogger(__name__)


class Ab3PExecutionError(RuntimeError):
    """A live Ab3P invocation failed."""


class Ab3PCacheMiss(LookupError):
    """No compatible cached execution exists."""


class Ab3PInstallationError(RuntimeError):
    """The configured Ab3P installation manifest or runtime is invalid."""


@dataclass(frozen=True, slots=True)
class Ab3PRawResult:
    """Raw execution evidence used identically by live and cached paths."""

    stdout: str
    stderr: str
    exit_status: int
    timed_out: bool = False
    executable_sha256: str | None = None
    cache_identity: dict[str, str] | None = None


def installation_identity(
    config: Ab3PResolverConfig, *, require_runtime: bool
) -> dict[str, str]:
    """Resolve and verify the configured installation without changing cwd."""

    installation = config.installation
    if installation is None:
        if not config.executable_sha256:
            raise Ab3PInstallationError(
                "Ab3P installation identity requires the T018 manifest and root"
            )
        return {
            "schema_version": "ab3p-identity-v1",
            "adapter_version": AB3P_ADAPTER_VERSION,
            "wrapper_version": AB3P_WRAPPER_VERSION,
            "output_format": config.output_format,
            "offset_schema_version": (
                AB3P_OFFSET_SCHEMA_VERSION
                if config.output_format == "offset_jsonl"
                else "none"
            ),
            "executable_sha256": config.executable_sha256.lower(),
            "resource_sha256": "unverified",
        }
    manifest_path = Path(installation.manifest)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Ab3PInstallationError(
            f"Unable to read Ab3P installation manifest {manifest_path}: {error}"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != INSTALLATION_MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest.get("artifacts"), list)
    ):
        raise Ab3PInstallationError(
            f"Incompatible Ab3P installation manifest {manifest_path}"
        )
    artifacts = manifest["artifacts"]
    executable_digest: str | None = None
    resource_digests: list[tuple[str, str]] = []
    resource_root = Path(installation.resource_directory)
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise Ab3PInstallationError("Ab3P installation artifact must be an object")
        relative_path = artifact.get("path")
        digest = artifact.get("sha256")
        role = artifact.get("role")
        if not isinstance(relative_path, str) or not isinstance(digest, str):
            raise Ab3PInstallationError("Ab3P installation artifact is incomplete")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise Ab3PInstallationError(
                f"Ab3P installation artifact path escapes its root: {relative_path!r}"
            )
        if role == "executable" and relative_path == installation.executable:
            executable_digest = digest.lower()
        if role == "semantic-resource":
            if relative.parts[: len(resource_root.parts)] != resource_root.parts:
                raise Ab3PInstallationError(
                    f"Ab3P resource is outside resource_directory: {relative_path!r}"
                )
            resource_digests.append((relative_path, digest.lower()))
    if executable_digest is None or not resource_digests:
        raise Ab3PInstallationError(
            "Ab3P installation manifest lacks executable or semantic resources"
        )
    root = Path(installation.root) if installation.root else None
    executable_path = root / installation.executable if root else None
    if require_runtime:
        if root is None:
            raise Ab3PInstallationError(
                "Live Ab3P execution requires installation.root"
            )
        _verify_artifact(executable_path, executable_digest, "executable")
        for relative_path, digest in resource_digests:
            _verify_artifact(root / relative_path, digest, "semantic resource")
        if not (root / "path_Ab3P").is_file():
            raise Ab3PInstallationError(
                f"Ab3P installation is missing path_Ab3P under {root}"
            )
    return {
        "schema_version": "ab3p-identity-v1",
        "adapter_version": AB3P_ADAPTER_VERSION,
        "wrapper_version": AB3P_WRAPPER_VERSION,
        "output_format": config.output_format,
        "offset_schema_version": (
            AB3P_OFFSET_SCHEMA_VERSION
            if config.output_format == "offset_jsonl"
            else "none"
        ),
        "manifest_sha256": _sha256(manifest_path.read_bytes()),
        "executable_sha256": executable_digest,
        "resource_sha256": _sha256(
            json.dumps(resource_digests, separators=(",", ":")).encode("utf-8")
        ),
    }


def runtime_paths(config: Ab3PResolverConfig) -> tuple[Path, Path]:
    """Return verified executable and working-directory paths for live Ab3P."""

    if config.installation is None or config.installation.root is None:
        raise Ab3PInstallationError(
            "Live Ab3P execution requires installation.manifest and installation.root"
        )
    installation_identity(config, require_runtime=True)
    root = Path(config.installation.root).resolve()
    return root / config.installation.executable, root


def cache_key(document: Document, config: Ab3PResolverConfig) -> str:
    """Return a path-independent key for document and semantic invocation data."""

    identity = installation_identity(config, require_runtime=False)
    payload = {
        "adapter": AB3P_ADAPTER_VERSION,
        "document_id": document.document_id,
        "document_sha256": _sha256(document.text.encode("utf-8")),
        "input_sha256": _sha256(build_ab3p_input(document).encode("utf-8")),
        "cache_identity": identity,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


class Ab3PCache:
    """JSON cache whose entries contain raw input, output, and provenance."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self, document: Document, config: Ab3PResolverConfig) -> Ab3PRawResult:
        try:
            expected_identity = installation_identity(
                config, require_runtime=config.backend != "cache_only"
            )
        except Ab3PInstallationError as error:
            raise Ab3PCacheMiss(
                f"Ab3P cache identity is unavailable: {error}"
            ) from error
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
            or data.get("document_sha256") != _sha256(document.text.encode("utf-8"))
            or data.get("input_text") != expected_input
            or data.get("input_sha256") != _sha256(expected_input.encode("utf-8"))
            or data.get("cache_identity") != expected_identity
        ):
            if isinstance(data, dict) and data.get("schema_version") == "ab3p-cache-v2":
                raise Ab3PCacheMiss(
                    "Legacy label-only Ab3P cache entries are incompatible; "
                    "rebuild them"
                )
            raise Ab3PCacheMiss(
                f"Incompatible Ab3P cache entry for {document.document_id!r}"
            )
        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            raise Ab3PCacheMiss(
                f"Incompatible Ab3P cache entry for {document.document_id!r}"
            )
        if provenance.get("cache_identity") != expected_identity:
            raise Ab3PCacheMiss(
                f"Incompatible Ab3P installation for {document.document_id!r}"
            )
        try:
            stdout = data["stdout"]
            stderr = data["stderr"]
            exit_status = data["exit_status"]
            timed_out = data["timed_out"]
        except KeyError as error:
            raise Ab3PCacheMiss(
                f"Incomplete Ab3P cache entry for {document.document_id!r}"
            ) from error
        if (
            not isinstance(stdout, str)
            or not isinstance(stderr, str)
            or isinstance(exit_status, bool)
            or not isinstance(exit_status, int)
            or not isinstance(timed_out, bool)
        ):
            raise Ab3PCacheMiss(
                f"Invalid Ab3P cache entry for {document.document_id!r}"
            )
        digest = provenance.get("executable_sha256")
        return Ab3PRawResult(
            stdout,
            stderr,
            exit_status,
            timed_out,
            str(digest) if digest else None,
            expected_identity,
        )

    def write(
        self, document: Document, config: Ab3PResolverConfig, result: Ab3PRawResult
    ) -> Path:
        try:
            expected_identity = installation_identity(
                config, require_runtime=config.backend != "cache_only"
            )
        except Ab3PInstallationError as error:
            raise Ab3PCacheMiss(
                f"Ab3P cache identity is unavailable: {error}"
            ) from error
        if (
            result.cache_identity is not None
            and result.cache_identity != expected_identity
        ):
            raise Ab3PCacheMiss(
                "Live Ab3P installation fingerprint does not match configuration"
            )
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
            "cache_identity": expected_identity,
            "provenance": {
                "configured_executable": config.executable,
                "output_format": config.output_format,
                "invocation_arguments": [
                    "<configured executable>",
                    "<temporary input file>",
                ],
                "executable_sha256": result.executable_sha256,
                "installation_label": config.installation_label,
                "cache_identity": expected_identity,
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

    try:
        executable, working_directory = runtime_paths(config)
        identity = installation_identity(config, require_runtime=True)
    except Ab3PInstallationError as error:
        if config.installation is not None:
            raise Ab3PExecutionError(f"Invalid Ab3P installation: {error}") from error
        if not config.executable:
            raise Ab3PExecutionError(
                "Ab3P subprocess backend requires a verified installation"
            ) from error
        executable = Path(config.executable)
        working_directory = Path.cwd()
        try:
            identity = installation_identity(config, require_runtime=False)
        except Ab3PInstallationError as identity_error:
            raise Ab3PExecutionError(
                "Ab3P subprocess backend requires a verified installation: "
                f"{identity_error}"
            ) from identity_error
    input_text = build_ab3p_input(document)
    logger.info("Starting Ab3P resolver for %s", document.document_id)
    try:
        with tempfile.TemporaryDirectory(prefix="abrex-ab3p-") as directory:
            input_path = Path(directory) / "input.txt"
            input_path.write_bytes(input_text.encode("utf-8"))
            try:
                argv = [os.fspath(executable), os.fspath(input_path)]
                logger.debug("Ab3P executable=%s argv=%s", executable, argv)
                completed = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="strict",
                    timeout=config.timeout_seconds,
                    check=False,
                    cwd=working_directory,
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
    executable_digest: str | None = identity.get("executable_sha256")
    if config.installation is None:
        with suppress(OSError):
            executable_digest = _sha256(executable.read_bytes())
    result = Ab3PRawResult(
        completed.stdout,
        completed.stderr,
        completed.returncode,
        executable_sha256=executable_digest,
        cache_identity=identity,
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


def _verify_artifact(path: Path | None, expected: str, role: str) -> None:
    if path is None:
        raise Ab3PInstallationError(f"Missing Ab3P {role} path")
    try:
        actual = _sha256(path.read_bytes())
    except OSError as error:
        raise Ab3PInstallationError(f"Missing Ab3P {role} {path}: {error}") from error
    if actual != expected:
        raise Ab3PInstallationError(
            f"Ab3P {role} fingerprint mismatch for {path}: "
            f"expected {expected}, got {actual}"
        )


__all__ = [
    "Ab3PCache",
    "Ab3PCacheMiss",
    "Ab3PExecutionError",
    "Ab3PInstallationError",
    "Ab3PRawResult",
    "CACHE_SCHEMA_VERSION",
    "cache_key",
    "installation_identity",
    "run_ab3p",
    "runtime_paths",
]
