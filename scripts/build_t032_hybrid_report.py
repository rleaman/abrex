"""Build the T032 hybrid benchmark report with per-proposal decisions."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.config import load_resolved_config
from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.evaluation import compare_resolvers
from abrex.resolvers import (
    TransparentHybridResolver,
    create_resolver_executor,
    fingerprint_prediction_artifact,
    read_prediction_artifact,
    resolver_config_from_resolved,
)


def build_report(
    config_path: Path,
    corpus_path: Path,
    manifest_path: Path,
    prediction_paths: dict[str, Path],
    output_path: Path,
) -> None:
    records, manifest = read_canonical_dataset(corpus_path, manifest_path)
    documents = {record.document.document_id: record.document for record in records}
    dataset_fingerprint = fingerprint_records(records)
    artifacts = {
        name: read_prediction_artifact(
            path, documents=documents, expected_dataset_fingerprint=dataset_fingerprint
        )
        for name, path in sorted(prediction_paths.items())
    }
    comparison = compare_resolvers(
        records,
        {name: artifact.records for name, artifact in artifacts.items()},
        bootstrap_samples=1000,
        seed=20260908,
    )
    configured = create_resolver_executor(
        resolver_config_from_resolved(load_resolved_config((config_path,)))
    ).resolver
    if not isinstance(configured, TransparentHybridResolver):
        raise TypeError("T032 report configuration must construct a transparent hybrid")
    evidence = []
    for record in records:
        result = configured.resolve_with_evidence(record.document)
        evidence.append(
            {
                "document_id": record.document.document_id,
                "children": [
                    {"child": child.child, "prediction_count": len(child.predictions)}
                    for child in result.children
                ],
                "decisions": [
                    {
                        "child": decision.child,
                        "accepted": decision.accepted,
                        "rule": decision.rule,
                        "reason": decision.reason,
                        "prediction_key": list(decision.prediction_key),
                    }
                    for decision in result.decisions
                ],
            }
        )
    payload = {
        "schema_version": "t032-transparent-hybrid-evidence-v1",
        "scope": "historical T022 smoke slice; exploratory development evidence",
        "dataset": {
            "dataset_id": manifest.dataset_id,
            "fingerprint": dataset_fingerprint,
            "records": len(records),
        },
        "artifacts": {
            name: {
                "path": str(prediction_paths[name]),
                "fingerprint": fingerprint_prediction_artifact(artifacts[name]),
            }
            for name in sorted(artifacts)
        },
        "comparison": comparison.to_dict(),
        "fusion": {
            "resolver": configured.cache_identity,
            "document_evidence": evidence,
        },
        "scientific_limits": [
            "The union comparison is exact-pair and does not pool span metrics.",
            "This hash-selected historical slice is exploratory, not representative.",
            "No precision promotion threshold was invented; native-offset Ab3P "
            "remains recommended on this slice.",
            "T030 provisional contemporary labels were not used.",
        ],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_prediction(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("prediction must use NAME=PATH")
    return name, Path(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--prediction", action="append", type=_parse_prediction, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_report(
        args.config, args.corpus, args.manifest, dict(args.prediction), args.output
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
