"""Run a bounded no-lexicon versus lexical candidate ablation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.candidates import CandidatePipelineConfig, create_candidate_pipeline
from abrex.corpora import fingerprint_records, read_canonical_dataset


def build_report(corpus: Path, manifest: Path, resource: Path, output: Path) -> None:
    records, dataset_manifest = read_canonical_dataset(corpus, manifest)
    variants = {
        "no_lexicon": CandidatePipelineConfig.model_validate(
            {"generators": [{"type": "parenthetical", "params": {}}]}
        ),
        "lexical_local": CandidatePipelineConfig.model_validate(
            {
                "generators": [
                    {"type": "parenthetical", "params": {}},
                    {
                        "type": "lexical_resource",
                        "params": {"resource_paths": [str(resource)]},
                    },
                ],
                "deduplicate": True,
            }
        ),
    }
    measurements: dict[str, object] = {}
    for name, config in variants.items():
        pipeline = create_candidate_pipeline(config)
        candidate_count = covered = true_candidate_count = gold_count = diagnostics = 0
        for record in records:
            result = pipeline.generate(record.document)
            candidate_count += len(result.candidates)
            diagnostics += len(result.diagnostics)
            gold_pairs = {
                (item.short_form, item.long_form)
                for item in record.gold_annotations
                if item.short_form is not None and item.long_form is not None
            }
            gold_count += len(gold_pairs)
            covered += sum(
                (candidate.short_form, candidate.long_form) in gold_pairs
                for candidate in result.candidates
            )
            true_candidate_count += len(
                {
                    (candidate.short_form, candidate.long_form)
                    for candidate in result.candidates
                    if (candidate.short_form, candidate.long_form) in gold_pairs
                }
            )
        measurements[name] = {
            "candidate_count": candidate_count,
            "diagnostic_count": diagnostics,
            "gold_pair_count": gold_count,
            "covered_gold_pairs": true_candidate_count,
            "candidate_precision_against_gold": (
                true_candidate_count / candidate_count if candidate_count else 0.0
            ),
            "candidate_recall_against_gold": (
                true_candidate_count / gold_count if gold_count else 0.0
            ),
        }
    lexical = measurements["lexical_local"]
    baseline = measurements["no_lexicon"]
    assert isinstance(lexical, dict) and isinstance(baseline, dict)
    payload = {
        "schema_version": "t034-lexical-evidence-ablation-v1",
        "scope": "historical T022 smoke slice; candidate metrics are exploratory",
        "dataset": {
            "dataset_id": dataset_manifest.dataset_id,
            "fingerprint": fingerprint_records(records),
            "records": len(records),
        },
        "resource": {
            "path": str(resource),
            "summary": "aggregate T028 pilot; no document frequency",
        },
        "variants": measurements,
        "delta": {
            "novel_candidates": lexical["candidate_count"]
            - baseline["candidate_count"],
            "precision_delta": lexical["candidate_precision_against_gold"]
            - baseline["candidate_precision_against_gold"],
            "recall_delta": lexical["candidate_recall_against_gold"]
            - baseline["candidate_recall_against_gold"],
        },
        "leakage_controls": [
            "Only exact local spans are emitted; aggregate rows cannot fabricate "
            "a long-form span.",
            "T029 evaluation/challenge records are not used to build this "
            "resource view.",
            "Resource source label and SHA-256 remain in candidate provenance; "
            "aggregate document frequency is unknown.",
        ],
        "limitations": [
            "The bounded T028 pilot has one short-form key and is not a "
            "lexical-benefit study.",
            "Gold comparisons are coverage diagnostics, not resolver precision "
            "or scientific validation.",
            "No global acronym disambiguation or terminology authority is applied.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--resource", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_report(args.corpus, args.manifest, args.resource, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
