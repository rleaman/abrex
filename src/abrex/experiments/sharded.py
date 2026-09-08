"""Resumable, bounded-memory document processing orchestration."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from abrex.domain import Document


class ShardedProcessingConfig(BaseModel):
    """Explicit limits and identities for one sharded processing run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_root: str
    shard_count: int = Field(default=1, ge=1)
    retry_limit: int = Field(default=0, ge=0)
    max_documents: int | None = Field(default=None, ge=1)
    source_identity: str = Field(min_length=1)
    processor_identity: str = Field(min_length=1)
    configuration_identity: str = Field(min_length=1)


class DocumentProcessor(Protocol):
    """Application boundary for one-document processing."""

    def __call__(self, document: Document) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class ShardedRunResult:
    """Published run metadata and bounded processing counts."""

    run_key: str
    manifest_path: Path
    shard_paths: tuple[Path, ...]
    processed_documents: int
    failed_documents: int
    reused: bool
    elapsed_seconds: float
    output_bytes: int


def run_sharded(
    documents: Iterable[Document],
    processor: DocumentProcessor,
    config: ShardedProcessingConfig,
    *,
    input_fingerprint: str,
    resume: bool = True,
) -> ShardedRunResult:
    """Route and process documents using bounded disk-backed shard buffers.

    A complete run manifest is the only reuse authority. Partial input/output
    files are ignored and replaced on rerun. Each output row retains the input
    document hash and processor identities, and failed documents are quarantined
    instead of being converted into successful empty outputs.
    """

    root = Path(config.output_root)
    run_key = _run_key(config, input_fingerprint)
    run_root = root / run_key
    manifest_path = run_root / "run-manifest.json"
    expected_identity = _identity(config, input_fingerprint, run_key)
    if resume and manifest_path.is_file():
        existing = _read_json(manifest_path)
        if (
            existing.get("identity") == expected_identity
            and existing.get("complete") is True
        ):
            return _result_from_manifest(manifest_path, existing, reused=True)
    run_root.mkdir(parents=True, exist_ok=True)
    _remove_partial_files(run_root)
    input_root = run_root / "inputs"
    output_root = run_root / "outputs"
    quarantine_root = run_root / "quarantine"
    input_root.mkdir(exist_ok=True)
    output_root.mkdir(exist_ok=True)
    quarantine_root.mkdir(exist_ok=True)
    input_handles: dict[int, Any] = {}
    input_counts = [0] * config.shard_count
    started = time.perf_counter()
    try:
        for index, document in enumerate(documents):
            if config.max_documents is not None and index >= config.max_documents:
                break
            if not isinstance(document, Document):
                raise TypeError("documents must contain Document values")
            shard = shard_for_document(document.document_id, config.shard_count)
            handle = input_handles.get(shard)
            if handle is None:
                path = input_root / f"shard-{shard:05d}.jsonl.part"
                handle = path.open("w", encoding="utf-8", newline="\n")
                input_handles[shard] = handle
            _write_json_line(
                handle,
                {
                    "document_id": document.document_id,
                    "text": document.text,
                    "input_sha256": _document_fingerprint(document),
                },
            )
            input_counts[shard] += 1
    finally:
        for handle in input_handles.values():
            handle.close()
    processed = 0
    failed = 0
    shard_paths: list[Path] = []
    shard_manifests: list[dict[str, object]] = []
    for shard in range(config.shard_count):
        input_path = input_root / f"shard-{shard:05d}.jsonl.part"
        output_part = output_root / f"shard-{shard:05d}.jsonl.part"
        output_path = output_root / f"shard-{shard:05d}.jsonl"
        quarantine_path = quarantine_root / f"shard-{shard:05d}.jsonl"
        shard_processed, shard_failed = _process_shard(
            input_path,
            output_part,
            output_path,
            quarantine_path,
            processor,
            config.retry_limit,
        )
        processed += shard_processed
        failed += shard_failed
        if input_path.exists():
            input_path.unlink()
        shard_paths.append(output_path)
        shard_manifests.append(
            {
                "shard": shard,
                "input_documents": input_counts[shard],
                "processed_documents": shard_processed,
                "failed_documents": shard_failed,
                "path": str(output_path),
                "quarantine_path": str(quarantine_path),
            }
        )
    elapsed = time.perf_counter() - started
    output_bytes = sum(path.stat().st_size for path in shard_paths if path.exists())
    manifest = {
        "schema_version": "sharded-run-v1",
        "complete": True,
        "identity": expected_identity,
        "run_key": run_key,
        "created_utc": datetime.now(UTC).isoformat(),
        "limits": config.model_dump(mode="json"),
        "counts": {
            "processed_documents": processed,
            "failed_documents": failed,
            "input_documents": sum(input_counts),
        },
        "measurements": {
            "elapsed_seconds": elapsed,
            "output_bytes": output_bytes,
            "peak_memory_bytes": None,
        },
        "shards": shard_manifests,
    }
    _atomic_write_json(manifest_path, manifest)
    return ShardedRunResult(
        run_key,
        manifest_path,
        tuple(shard_paths),
        processed,
        failed,
        False,
        elapsed,
        output_bytes,
    )


def shard_for_document(document_id: str, shard_count: int) -> int:
    """Return deterministic shard membership from a stable document ID."""

    if not document_id or shard_count < 1:
        raise ValueError("document_id must be non-empty and shard_count positive")
    digest = hashlib.sha256(document_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def _process_shard(
    input_path: Path,
    output_part: Path,
    output_path: Path,
    quarantine_path: Path,
    processor: DocumentProcessor,
    retry_limit: int,
) -> tuple[int, int]:
    processed = 0
    failed = 0
    if not input_path.exists():
        output_path.touch()
        return 0, 0
    with (
        input_path.open("r", encoding="utf-8") as source,
        output_part.open("w", encoding="utf-8", newline="\n") as output,
        quarantine_path.open("w", encoding="utf-8", newline="\n") as quarantine,
    ):
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            document = Document(row["document_id"], row["text"])
            error: BaseException | None = None
            result: Mapping[str, object] | None = None
            for _attempt in range(retry_limit + 1):
                try:
                    result = processor(document)
                    error = None
                    break
                except Exception as caught:
                    error = caught
            if error is not None or result is None:
                failed += 1
                _write_json_line(
                    quarantine,
                    {
                        "document_id": document.document_id,
                        "line": line_number,
                        "error_type": type(error).__name__ if error else "Unknown",
                        "error": str(error),
                        "input_sha256": row["input_sha256"],
                    },
                )
                continue
            processed += 1
            _write_json_line(
                output,
                {
                    "document_id": document.document_id,
                    "input_sha256": row["input_sha256"],
                    "output": dict(result),
                },
            )
    output_part.replace(output_path)
    return processed, failed


def _run_key(config: ShardedProcessingConfig, input_fingerprint: str) -> str:
    return _sha256(
        json.dumps(
            {
                "source": config.source_identity,
                "processor": config.processor_identity,
                "configuration": config.configuration_identity,
                "input": input_fingerprint,
                "shards": config.shard_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def _identity(
    config: ShardedProcessingConfig, input_fingerprint: str, run_key: str
) -> dict[str, object]:
    return {
        "run_key": run_key,
        "source_identity": config.source_identity,
        "processor_identity": config.processor_identity,
        "configuration_identity": config.configuration_identity,
        "input_fingerprint": input_fingerprint,
    }


def _document_fingerprint(document: Document) -> str:
    return _sha256((document.document_id + "\0" + document.text).encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json_line(handle: Any, value: Mapping[str, object]) -> None:
    handle.write(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    partial = path.with_suffix(path.suffix + ".part")
    with partial.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    partial.replace(path)


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Manifest must contain an object: {path}")
    return value


def _remove_partial_files(root: Path) -> None:
    for path in root.rglob("*.part"):
        path.unlink()


def _result_from_manifest(
    path: Path, manifest: Mapping[str, object], *, reused: bool
) -> ShardedRunResult:
    counts = manifest.get("counts")
    measurements = manifest.get("measurements")
    shards = manifest.get("shards")
    if (
        not isinstance(counts, dict)
        or not isinstance(measurements, dict)
        or not isinstance(shards, list)
    ):
        raise ValueError("Malformed sharded run manifest")
    shard_paths = tuple(Path(item["path"]) for item in shards if isinstance(item, dict))
    return ShardedRunResult(
        str(manifest["run_key"]),
        path,
        shard_paths,
        int(counts["processed_documents"]),
        int(counts["failed_documents"]),
        reused,
        float(measurements["elapsed_seconds"]),
        int(measurements["output_bytes"]),
    )


__all__ = [
    "DocumentProcessor",
    "ShardedProcessingConfig",
    "ShardedRunResult",
    "run_sharded",
    "shard_for_document",
]
