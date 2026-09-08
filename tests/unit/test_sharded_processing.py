from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.domain import Document
from abrex.experiments import (
    ShardedProcessingConfig,
    run_sharded,
    shard_for_document,
)


def _config(root: Path, *, shards: int = 2) -> ShardedProcessingConfig:
    return ShardedProcessingConfig(
        output_root=str(root),
        shard_count=shards,
        retry_limit=1,
        source_identity="source-v1",
        processor_identity="processor-v1",
        configuration_identity="config-v1",
    )


def test_sharded_run_is_bounded_disk_backed_and_reusable(tmp_path: Path) -> None:
    documents = tuple(Document(str(i), f"text-{i}") for i in range(8))
    calls: list[str] = []

    def processor(document: Document) -> dict[str, object]:
        calls.append(document.document_id)
        return {"length": len(document.text)}

    config = _config(tmp_path)
    first = run_sharded(
        (document for document in documents),
        processor,
        config,
        input_fingerprint="input-v1",
    )

    assert first.processed_documents == len(documents)
    assert first.failed_documents == 0
    assert first.reused is False
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert manifest["measurements"]["peak_memory_bytes"] is None
    assert not list(tmp_path.rglob("*.part"))

    def should_not_run(document: Document) -> dict[str, object]:
        raise AssertionError(document.document_id)

    reused = run_sharded(
        documents, should_not_run, config, input_fingerprint="input-v1"
    )
    assert reused.reused is True
    assert reused.processed_documents == len(documents)


def test_failures_are_quarantined_and_retried(tmp_path: Path) -> None:
    attempts: dict[str, int] = {}

    def processor(document: Document) -> dict[str, object]:
        attempts[document.document_id] = attempts.get(document.document_id, 0) + 1
        if document.document_id == "bad":
            raise ValueError("known failure")
        return {"ok": True}

    result = run_sharded(
        (Document("good", "x"), Document("bad", "y")),
        processor,
        _config(tmp_path, shards=1),
        input_fingerprint="input-v1",
    )

    assert result.processed_documents == 1
    assert result.failed_documents == 1
    assert attempts["bad"] == 2
    quarantine = next((tmp_path / result.run_key).rglob("quarantine/*.jsonl"))
    rows = [
        json.loads(line) for line in quarantine.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["error_type"] == "ValueError"


def test_interrupted_run_discards_partial_inputs_on_resume(tmp_path: Path) -> None:
    config = _config(tmp_path, shards=1)
    documents = (Document("d", "text"),)

    def interrupted(document: Document) -> dict[str, object]:
        raise KeyboardInterrupt(document.document_id)

    with pytest.raises(KeyboardInterrupt):
        run_sharded(documents, interrupted, config, input_fingerprint="input-v1")
    assert list(tmp_path.rglob("*.part"))

    resumed = run_sharded(
        documents,
        lambda document: {"id": document.document_id},
        config,
        input_fingerprint="input-v1",
    )
    assert resumed.reused is False
    assert resumed.processed_documents == 1
    assert not list(tmp_path.rglob("*.part"))


def test_shard_membership_is_deterministic_and_input_identity_changes_run(
    tmp_path: Path,
) -> None:
    assert shard_for_document("doc", 3) == shard_for_document("doc", 3)
    config = _config(tmp_path)

    def processor(document: Document) -> dict[str, object]:
        return {"id": document.document_id}

    first = run_sharded(
        (Document("d", "text"),), processor, config, input_fingerprint="one"
    )
    second = run_sharded(
        (Document("d", "text"),), processor, config, input_fingerprint="two"
    )
    assert first.run_key != second.run_key
