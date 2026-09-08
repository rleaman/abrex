"""Build the reproducible T031 resolver comparison evidence artifact."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.corpora import fingerprint_records, read_canonical_dataset
from abrex.evaluation import (
    compare_resolvers,
    write_comparative_report,
)
from abrex.resolvers import (
    fingerprint_prediction_artifact,
    read_prediction_artifact,
)


def build_report(
    corpus_path: Path,
    manifest_path: Path,
    prediction_paths: dict[str, Path],
    output_path: Path,
    *,
    bootstrap_samples: int = 1000,
    seed: int = 20260908,
) -> str:
    """Validate artifacts, compare resolvers, and write a stable evidence report."""

    records, manifest = read_canonical_dataset(corpus_path, manifest_path)
    documents = {record.document.document_id: record.document for record in records}
    dataset_fingerprint = fingerprint_records(records)
    artifacts = {
        name: read_prediction_artifact(
            path,
            documents=documents,
            expected_dataset_fingerprint=dataset_fingerprint,
        )
        for name, path in sorted(prediction_paths.items())
    }
    report = compare_resolvers(
        records,
        {name: artifact.records for name, artifact in artifacts.items()},
        mode="exact_pair",
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    evidence = {
        "schema_version": "t031-comparative-evidence-v1",
        "scope": "historical T022 smoke slice; exploratory development evidence",
        "dataset": {
            "dataset_id": manifest.dataset_id,
            "fingerprint": dataset_fingerprint,
            "records": len(records),
            "gold_pairs": sum(len(record.gold_annotations) for record in records),
            "grouping": (
                "document_id; no cross-document article-group metadata supplied"
            ),
        },
        "artifacts": {
            name: {
                "path": str(prediction_paths[name]),
                "fingerprint": fingerprint_prediction_artifact(artifacts[name]),
                "records": len(artifacts[name].records),
                "execution_diagnostics": sum(
                    len(record.diagnostics) for record in artifacts[name].records
                ),
            }
            for name in sorted(artifacts)
        },
        "comparison": report.to_dict(),
        "scientific_limits": [
            "This exact-pair comparison does not pool independent span metrics.",
            "The union recall is gold-assisted and is not a deployable resolver score.",
            "The hash-selected historical smoke slice is exploratory, "
            "not representative.",
            "The provisional T030 contemporary labels were intentionally not used.",
            "Bootstrap resamples document IDs as article groups because no linked "
            "group metadata is available.",
            "BioADI is excluded until its abstention policy and occurrence mapping "
            "are approved for comparison.",
        ],
    }
    serialized = (
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return write_comparative_report(output_path.with_suffix(".core.json"), report)


def _parse_prediction(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("prediction must use NAME=PATH")
    return name, Path(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--prediction", action="append", type=_parse_prediction, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args(argv)
    build_report(
        args.corpus,
        args.manifest,
        dict(args.prediction),
        args.output,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
