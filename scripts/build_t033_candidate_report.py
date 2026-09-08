"""Measure bounded structural candidate expansion on a fixed gold universe."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.candidates import CandidatePipelineConfig, create_candidate_pipeline
from abrex.corpora import fingerprint_records, read_canonical_dataset


def build_report(corpus: Path, manifest: Path, output: Path) -> None:
    records, dataset_manifest = read_canonical_dataset(corpus, manifest)
    fingerprint = fingerprint_records(records)
    variants = {
        "parenthetical": CandidatePipelineConfig.model_validate(
            {"generators": [{"type": "parenthetical", "params": {}}]}
        ),
        "structural_prose": CandidatePipelineConfig.model_validate(
            {
                "generators": [
                    {"type": "parenthetical", "params": {}},
                    {"type": "reverse_order", "params": {}},
                    {"type": "nested_parenthetical", "params": {}},
                ],
                "deduplicate": True,
            }
        ),
    }
    measurements = {}
    for name, config in variants.items():
        pipeline = create_candidate_pipeline(config)
        candidate_count = 0
        covered = 0
        gold_count = 0
        diagnostics = 0
        for record in records:
            result = pipeline.generate(record.document)
            candidate_count += len(result.candidates)
            diagnostics += len(result.diagnostics)
            candidate_keys = {
                (candidate.short_form, candidate.long_form)
                for candidate in result.candidates
            }
            for annotation in record.gold_annotations:
                if annotation.short_form is None or annotation.long_form is None:
                    continue
                gold_count += 1
                covered += int(
                    (annotation.short_form, annotation.long_form) in candidate_keys
                )
        measurements[name] = {
            "candidate_count": candidate_count,
            "diagnostic_count": diagnostics,
            "gold_count": gold_count,
            "covered_gold": covered,
            "candidate_recall": covered / gold_count if gold_count else 0.0,
        }
    payload = {
        "schema_version": "t033-candidate-evidence-v1",
        "scope": "historical T022 smoke slice; candidate recall is exploratory",
        "dataset": {
            "dataset_id": dataset_manifest.dataset_id,
            "fingerprint": fingerprint,
            "records": len(records),
        },
        "variants": measurements,
        "structural_pilot": {
            "structured_relations": (
                "requires ArticleDocument structures and is not silently applied "
                "to canonical-only records"
            ),
            "image_only_regions": "uncovered; no OCR or fabricated text",
        },
        "limitations": [
            "Candidate coverage is not resolver precision or final acceptance.",
            "The hash-selected T022 slice is not representative.",
            "T030 provisional labels were not used for model selection.",
        ],
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_report(args.corpus, args.manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
