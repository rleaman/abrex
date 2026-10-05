"""Build reproducible candidate-coverage and cost evidence for Milestone B."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora import read_canonical_dataset
from abrex.resolvers.direct_extraction import DirectExtractionResolver
from abrex.resolvers.jev import JevCandidateJudgeResolver


def build_preflight(
    corpus_path: Path,
    manifest_path: Path,
    milestone_a_report: Path,
    output_path: Path,
) -> dict[str, object]:
    """Measure current generator coverage and serialize the bounded route."""

    records, manifest = read_canonical_dataset(corpus_path, manifest_path)
    judge = JevCandidateJudgeResolver(
        client=cast(Any, object()),
        cache_only=True,
        definition_threshold=0.75,
        orientation_threshold=0.95,
    )
    extractor = DirectExtractionResolver(
        client=cast(Any, object()),
        maximum_network_attempts=len(records),
        maximum_estimated_input_tokens=25_000,
        maximum_output_tokens_per_request=2_048,
        monetary_cap_usd=0.05,
        retries=0,
    )
    total_gold = 0
    covered = 0
    candidate_count = 0
    missing: list[dict[str, object]] = []
    per_document: list[dict[str, object]] = []
    request_characters = 0
    estimated_input_tokens = 0
    for record in records:
        candidates = tuple(judge.pipeline.generate(record.document).candidates)
        candidate_count += len(candidates)
        candidate_keys = {
            (
                item.short_form.start,
                item.short_form.end,
                item.long_form.start,
                item.long_form.end,
            )
            for item in candidates
        } | {
            (
                item.long_form.start,
                item.long_form.end,
                item.short_form.start,
                item.short_form.end,
            )
            for item in candidates
        }
        document_covered = 0
        for gold in record.gold_annotations:
            assert gold.short_form is not None and gold.long_form is not None
            total_gold += 1
            key = (
                gold.short_form.start,
                gold.short_form.end,
                gold.long_form.start,
                gold.long_form.end,
            )
            if key in candidate_keys:
                covered += 1
                document_covered += 1
            else:
                missing.append(
                    {
                        "document_id": record.document.document_id,
                        "short_form": {
                            "text": gold.short_form_text,
                            "start": gold.short_form.start,
                            "end": gold.short_form.end,
                        },
                        "long_form": {
                            "text": gold.long_form_text,
                            "start": gold.long_form.start,
                            "end": gold.long_form.end,
                        },
                    }
                )
        payload_text = json.dumps(
            extractor.request_payload(record.document),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        request_characters += len(payload_text)
        estimated_input_tokens += max(1, len(payload_text) // 4)
        per_document.append(
            {
                "document_id": record.document.document_id,
                "gold_relations": len(record.gold_annotations),
                "covered_relations": document_covered,
                "generated_candidates": len(candidates),
                "request_characters": len(payload_text),
            }
        )
    milestone_a = _object(milestone_a_report)
    comparisons = _mapping(
        milestone_a.get("existing_method_comparison"), "existing method comparison"
    )
    method_metrics = _mapping(comparisons.get("methods"), "existing methods")
    judge_metrics = _mapping(
        method_metrics.get("jev_candidate_judge"), "Jev candidate judge metrics"
    )
    maximum_output_tokens = (
        len(records) * extractor.config.maximum_output_tokens_per_request
    )
    worst_cost = (
        estimated_input_tokens * extractor.config.input_usd_per_million_tokens
        + maximum_output_tokens * extractor.config.output_usd_per_million_tokens
    ) / 1_000_000
    report: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-b-preflight-v1",
        "evidence_class": "assisted_development",
        "corpus": {
            "dataset_id": manifest.dataset_id,
            "fingerprint": manifest.fingerprint,
            "documents": len(records),
            "strict_relations": total_gold,
            "text_characters": sum(len(item.document.text) for item in records),
            "overlap_warnings": manifest.validation.ambiguous,
        },
        "candidate_judging": {
            "generator_identity": judge.cache_identity,
            "generated_candidates": candidate_count,
            "gold_covered": covered,
            "gold_omitted": total_gold - covered,
            "coverage": covered / total_gold,
            "final_exact_metrics": dict(judge_metrics),
            "missing_relations": missing,
        },
        "direct_extraction_route": {
            "cache_identity": extractor.cache_identity,
            "documents": len(records),
            "request_characters": request_characters,
            "estimated_input_tokens": estimated_input_tokens,
            "maximum_output_tokens": maximum_output_tokens,
            "standard_price_worst_case_usd": worst_cost,
            "monetary_cap_usd": extractor.config.monetary_cap_usd,
            "automatic_retries": extractor.config.retries,
            "maximum_network_attempts": (extractor.config.maximum_network_attempts),
            "external_requests_issued": 0,
        },
        "per_document": per_document,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-b/t062-development.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-b/t062-development.manifest.json"
        ),
    )
    parser.add_argument(
        "--milestone-a-report",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-a/clp-milestone-a-report-v1.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-b/direct-extraction-preflight-v1.json"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build configured report and print its compact headline."""

    args = _parser().parse_args(argv)
    report = build_preflight(
        args.corpus, args.manifest, args.milestone_a_report, args.output
    )
    print(
        json.dumps(
            {
                "candidate_judging": report["candidate_judging"],
                "direct_extraction_route": report["direct_extraction_route"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
