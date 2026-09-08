"""Materialize a deterministic, resolver-independent T022 benchmark slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from abrex.corpora import (
    read_canonical_dataset,
    write_canonical_jsonl,
)


def _selection_key(record_id: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{record_id}".encode()).hexdigest()


def materialize(
    source_jsonl: Path,
    source_manifest: Path,
    output_jsonl: Path,
    output_manifest: Path,
    *,
    count: int,
    seed: str,
) -> dict[str, Any]:
    """Write a fixed-size hash-selected slice and its auditable manifest."""

    records, source = read_canonical_dataset(source_jsonl, source_manifest)
    eligible = tuple(record for record in records if record.gold_annotations)
    if count <= 0 or count > len(eligible):
        raise ValueError(f"count must be between 1 and {len(eligible)}")
    selected = tuple(
        sorted(
            sorted(eligible, key=lambda item: item.record_id)[:count]
            if seed == "canonical-prefix"
            else sorted(
                eligible,
                key=lambda item: (_selection_key(item.record_id, seed), item.record_id),
            )[:count],
            key=lambda item: item.record_id,
        )
    )
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    subset_fingerprint = write_canonical_jsonl(selected, output_jsonl)
    manifest: dict[str, Any] = {
        "manifest_version": "manifest-v1",
        "schema_version": "canonical-v1",
        "dataset_id": "ab3p_corpus_t022_smoke",
        "fingerprint": subset_fingerprint,
        "record_count": len(selected),
        "annotation_count": sum(len(record.gold_annotations) for record in selected),
        "adapter": {
            "identity": source.adapter_identity,
            "version": source.adapter_version,
        },
        "normalizers": list(source.normalizer_identities),
        "config_fingerprint": source.config_fingerprint,
        "source": {
            "identifier": source.source_identifier,
            "format": source.source_format,
            "fingerprint": source.source_fingerprint,
        },
        "validation": {
            "total": 0,
            "records_seen": len(selected),
            "records_kept": len(selected),
            "records_dropped": 0,
            "by_action": {
                "observed": 0,
                "repaired": 0,
                "dropped": 0,
                "ambiguous": 0,
                "unscoreable": 0,
            },
            "by_severity": {"info": 0, "warning": 0, "error": 0},
            "diagnostics": [],
        },
        "selection": {
            "method": "sha256(seed:record_id) ascending",
            "seed": seed,
            "eligible_definition": "record.gold_annotations is non-empty",
            "eligible_record_count_in_full_dataset": len(eligible),
            "full_dataset_id": source.dataset_id,
            "full_dataset_fingerprint": source.fingerprint,
            "record_ids": [record.record_id for record in selected],
        },
    }
    output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-jsonl", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--seed", default="t022-real-baseline-v1")
    args = parser.parse_args()
    manifest = materialize(
        args.source_jsonl,
        args.source_manifest,
        args.output_jsonl,
        args.output_manifest,
        count=args.count,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "fingerprint": manifest["fingerprint"],
                "record_count": manifest["record_count"],
                "annotation_count": manifest["annotation_count"],
                "manifest": str(args.output_manifest),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
