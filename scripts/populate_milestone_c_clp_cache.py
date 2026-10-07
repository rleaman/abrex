"""Populate the one bounded live Jev decision needed by frozen full CLP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PINNED_ARCHIVE_SHA256 = (
    "290a52ad53216de64fca78abff2682057cc77b0d3c3ee698580a8ca9f94df7d7"
)
PINNED_MODEL = "jev-1.13.0"


def _object(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bioc_document(bioc: Any, request: Mapping[str, Any]) -> Any:
    raw_passages = request.get("passages")
    if not isinstance(raw_passages, list) or not raw_passages:
        raise ValueError("V2 document requires passages")
    document = bioc.BioCDocument()
    document.id = str(request["document_id"])
    document.infons = {"source_filename": str(request["source_filename"])}
    for raw_passage in raw_passages:
        value = _object(raw_passage, "passage")
        passage = bioc.BioCPassage()
        passage.offset = int(value["source_offset"])
        passage.text = str(value["text"])
        passage.infons = {
            "section_type": str(value.get("section_type", "")),
            "type": str(value.get("passage_type", "")),
        }
        if value.get("xml") is not None:
            passage.infons["xml"] = str(value["xml"])
        document.passages.append(passage)
    return document


def populate(
    request_path: Path,
    source_archive: Path,
    dictionary_path: Path,
    cache_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    """Issue at most one no-retry request and retain only the pinned model."""

    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        raise RuntimeError("TYPESAFE_API_KEY is required")
    if _sha256(source_archive) != PINNED_ARCHIVE_SHA256:
        raise RuntimeError("pinned CLP source archive hash mismatch")
    if cache_path.exists():
        raise FileExistsError(f"refusing to replace existing cache: {cache_path}")
    pending = cache_path.with_name(cache_path.name + ".pending")
    if pending.exists():
        raise FileExistsError(f"pending cache requires inspection: {pending}")

    request = _object(json.loads(request_path.read_text(encoding="utf-8")), "request")
    documents = request.get("documents")
    if not isinstance(documents, list) or len(documents) != 1:
        raise ValueError("Milestone C CLP live execution requires exactly one document")

    sys.path.insert(0, f"{source_archive.resolve()}/src")
    import bioc
    from clp.abbr import explore_bioc_abbr_tables as base
    from clp.abbr import explore_bioc_abbr_tables_jev as hybrid

    dictionary = base.load_ab3p_dictionary(dictionary_path)
    judge = hybrid.TypeSafeJevJudge(
        model="jev-latest",
        cache_path=pending,
        cache_only=False,
        max_network_calls=1,
        retries=0,
        retry_delay=0,
    )
    raw_document = _object(documents[0], "document")
    analysis = hybrid.analyze_section(
        str(raw_document["source_filename"]),
        _bioc_document(bioc, raw_document),
        int(raw_document["start_position"]),
        judge,
        dictionary,
        confidence_threshold=0.52,
    )
    if judge.network_calls != 1 or not pending.is_file():
        raise RuntimeError(
            "frozen CLP case did not produce exactly one durable Jev request"
        )
    response = analysis.jev_response
    actual_model = str(response.model) if response is not None else ""
    if actual_model != PINNED_MODEL:
        mismatch = cache_path.with_name(cache_path.name + ".model-mismatch")
        pending.replace(mismatch)
        raise RuntimeError(
            f"TypeSafe returned {actual_model!r}, expected {PINNED_MODEL!r}; "
            f"response retained at {mismatch}"
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pending.replace(cache_path)
    receipt: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-clp-live-receipt-v1",
        "request_id": request["request_id"],
        "document_id": raw_document["document_id"],
        "requested_model_alias": "jev-latest",
        "returned_model": actual_model,
        "network_requests": judge.network_calls,
        "retries": 0,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "provider_request_id": response.request_id,
        "disposition": str(analysis.disposition.value),
        "decision_source": str(analysis.decision_source.value),
        "cache_path": cache_path.as_posix(),
        "cache_sha256": _sha256(cache_path),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--request",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/clp-rules-only-request-v1.json"
        ),
    )
    parser.add_argument(
        "--source-archive",
        type=Path,
        default=Path("resources/clp/clp-v5.1-source.zip"),
    )
    parser.add_argument("--dictionary", required=True, type=Path)
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/clp-jev-cache-v1.jsonl"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/clp-live-receipt-v1.json"),
    )
    args = parser.parse_args(argv)
    receipt = populate(
        args.request,
        args.source_archive,
        args.dictionary,
        args.cache,
        args.receipt,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
