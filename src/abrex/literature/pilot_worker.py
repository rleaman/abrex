"""Isolated optional-runtime worker for T051 resolver execution."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from abrex.domain import AbbreviationDefinition, Document
from abrex.resolvers import (
    Ab3PResolver,
    PlodConfig,
    PlodPairingConfig,
    PlodSpanDetector,
    PositionAnchoredPairing,
)


def run_worker(
    method: str, documents: Sequence[Mapping[str, object]], params: Mapping[str, object]
) -> dict[str, object]:
    """Run one optional resolver stack once over a bounded document batch."""

    started = time.monotonic()
    try:
        if method == "ab3p":
            resolver: Any = Ab3PResolver(**params)
            identity = resolver.identity
            version = resolver.version
        elif method == "plodv2":
            detector_config = PlodConfig.model_validate(params)
            detector = PlodSpanDetector(config=detector_config)
            pairing_config = PlodPairingConfig(detector=detector_config)
            pairing = PositionAnchoredPairing()
            identity = detector.identity
            version = detector.version
        else:
            raise ValueError(f"unsupported worker method: {method}")
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        return {
            "method": method,
            "status": "unavailable",
            "identity": method,
            "version": "unavailable",
            "elapsed_seconds": time.monotonic() - started,
            "diagnostics": [f"runtime_probe_failed:{type(error).__name__}:{error}"],
            "records": [],
        }

    records: list[dict[str, object]] = []
    for raw in documents:
        document_id = raw.get("document_id")
        text = raw.get("text")
        if not isinstance(document_id, str) or not isinstance(text, str):
            records.append(
                {
                    "document_id": str(document_id),
                    "status": "failed",
                    "coverage": "none",
                    "pairs": [],
                    "spans": [],
                    "diagnostics": ["invalid_worker_document"],
                    "elapsed_seconds": 0.0,
                }
            )
            continue
        document = Document(document_id, text)
        record_started = time.monotonic()
        try:
            if method == "ab3p":
                predictions = tuple(resolver.resolve(document))
                pairs = [_pair(item) for item in predictions]
                spans: list[dict[str, object]] = []
                diagnostics: list[str] = []
            else:
                span_record = detector.detect(document)
                pair_record = pairing.pair(
                    document, span_record.validated_spans, pairing_config
                )
                spans = [
                    {
                        "label": item.label,
                        "start": item.span.start,
                        "end": item.span.end,
                        "text": item.text,
                        "score": item.score,
                        "source_window_start": item.source_window_start,
                    }
                    for item in span_record.validated_spans
                ]
                pairs = [
                    {
                        "short_form": {
                            "start": item.short_form.span.start,
                            "end": item.short_form.span.end,
                            "text": item.short_form.text,
                        },
                        "long_form": {
                            "start": item.long_form.span.start,
                            "end": item.long_form.span.end,
                            "text": item.long_form.text,
                        },
                        "score": 1.0 if item.cost == 0 else 1.0 / (1.0 + item.cost),
                        "provenance": {
                            "pairing_strategy": pairing.identity,
                            "cost": item.cost,
                            "pattern": item.pattern,
                        },
                    }
                    for item in pair_record.selected
                ]
                diagnostics = list(span_record.diagnostics + pair_record.diagnostics)
            records.append(
                {
                    "document_id": document_id,
                    "status": "completed",
                    "coverage": "complete",
                    "pairs": pairs,
                    "spans": spans,
                    "diagnostics": diagnostics,
                    "elapsed_seconds": time.monotonic() - record_started,
                }
            )
        except (OSError, RuntimeError, ValueError) as error:
            records.append(
                {
                    "document_id": document_id,
                    "status": "failed",
                    "coverage": "none",
                    "pairs": [],
                    "spans": [],
                    "diagnostics": [
                        f"resolver_execution_failed:{type(error).__name__}:{error}"
                    ],
                    "elapsed_seconds": time.monotonic() - record_started,
                }
            )
    try:
        runtime_identity = (
            resolver.cache_identity if method == "ab3p" else detector.cache_identity
        )
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "method": method,
            "status": "unavailable",
            "identity": identity,
            "version": version,
            "elapsed_seconds": time.monotonic() - started,
            "diagnostics": [f"runtime_identity_failed:{type(error).__name__}:{error}"],
            "records": [],
        }
    return {
        "method": method,
        "status": "completed",
        "identity": identity,
        "version": version,
        "runtime_identity": runtime_identity,
        "elapsed_seconds": time.monotonic() - started,
        "diagnostics": [],
        "records": records,
    }


def _pair(item: AbbreviationDefinition) -> dict[str, object]:
    if item.short_form is None or item.long_form is None:
        raise ValueError("paired resolver returned an incomplete relation")
    return {
        "short_form": {
            "start": item.short_form.start,
            "end": item.short_form.end,
            "text": item.short_form_text,
        },
        "long_form": {
            "start": item.long_form.start,
            "end": item.long_form.end,
            "text": item.long_form_text,
        },
        "score": item.prediction.score if item.prediction is not None else None,
        "provenance": {
            "adapter_identity": item.provenance.adapter_identity
            if item.provenance is not None
            else None,
            "transformation_notes": list(item.provenance.transformation_notes)
            if item.provenance is not None
            else [],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Read worker inputs and write one deterministic JSON result."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("ab3p", "plodv2"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--params", type=Path, required=True)
    args = parser.parse_args(argv)
    documents = json.loads(args.input.read_text(encoding="utf-8"))
    params = json.loads(args.params.read_text(encoding="utf-8"))
    if not isinstance(documents, list) or not isinstance(params, dict):
        raise ValueError("worker input must be a document list and params object")
    result = run_worker(args.method, documents, params)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())


__all__ = ["main", "run_worker"]
