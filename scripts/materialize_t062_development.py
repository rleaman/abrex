"""Materialize the reconciled T062 strict development ledger as canonical data."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora import (
    CorpusBuildResult,
    DiagnosticsSummary,
    SourceResource,
    read_canonical_dataset,
    write_canonical_dataset,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    TextSpan,
)

ADAPTER_IDENTITY = "t062_strict_development_view"
ADAPTER_VERSION = "1"


def materialize(
    base_path: Path,
    base_manifest_path: Path,
    ledger_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> tuple[int, int, str]:
    """Join reconciled strict relations to the unchanged 20 source texts."""

    base_records, _ = read_canonical_dataset(base_path, base_manifest_path)
    ledger = _object(ledger_path)
    by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for ledger_relation in _objects(ledger.get("relations"), "ledger relations"):
        if ledger_relation.get("disposition") == "strict":
            by_case[_string(ledger_relation, "case_id")].append(ledger_relation)
    known = {record.document.document_id for record in base_records}
    unknown = sorted(set(by_case) - known)
    if unknown:
        raise ValueError(f"ledger references unknown cases: {unknown!r}")
    records: list[CorpusRecord] = []
    relation_count = 0
    for base in base_records:
        document = base.document
        annotations: list[AbbreviationDefinition] = []
        for relation in by_case.get(document.document_id, []):
            short = _span(relation, "short_form", document.text)
            long = _span(relation, "long_form", document.text)
            annotation = AbbreviationDefinition(
                document.document_id,
                short_form=short,
                long_form=long,
                short_form_text=document.text_for(short),
                long_form_text=document.text_for(long),
                provenance=AnnotationProvenance(
                    source_corpus=_string(ledger, "policy_id"),
                    source_record_id=document.document_id,
                    source_annotation_id=_string(relation, "decision_id"),
                    adapter_identity=ADAPTER_IDENTITY,
                    adapter_version=ADAPTER_VERSION,
                    transformation_notes=(
                        "assisted_development_evidence",
                        f"article_group_id={_string(relation, 'article_group_id')}",
                        f"arm={_string(relation, 'arm')}",
                        f"origin={_string(relation, 'source')}",
                    ),
                ),
            )
            annotation.validate_against(document)
            annotations.append(annotation)
        relation_count += len(annotations)
        records.append(
            CorpusRecord(
                document,
                tuple(annotations),
                record_id=base.record_id,
                provenance=AnnotationProvenance(
                    source_corpus=_string(ledger, "policy_id"),
                    source_record_id=document.document_id,
                    adapter_identity=ADAPTER_IDENTITY,
                    adapter_version=ADAPTER_VERSION,
                    transformation_notes=(
                        "reconciled_strict_exact_pair_projection",
                        "not_independent_gold",
                    ),
                ),
            )
        )
    expected = _mapping(ledger.get("counts"), "ledger counts").get("strict_relations")
    if relation_count != expected:
        raise ValueError(
            f"strict relation count mismatch: expected {expected}, got {relation_count}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    result = CorpusBuildResult(
        tuple(records),
        DiagnosticsSummary(),
        SourceResource.from_path(
            _string(ledger, "policy_id"),
            ledger_path,
            format="t062-development-ledger-v1",
        ),
        ADAPTER_IDENTITY,
        ADAPTER_VERSION,
        (),
        source_record_count=len(records),
        source_annotation_count=relation_count,
    )
    manifest = write_canonical_dataset(
        result,
        output_path,
        dataset_id="t062-strict-development-v1",
        manifest_path=manifest_path,
        mode="strict",
    )
    return len(records), relation_count, manifest.fingerprint


def _span(relation: Mapping[str, Any], name: str, text: str) -> TextSpan:
    value = _mapping(relation.get(name), name)
    start = _integer(value, "start")
    end = _integer(value, "end")
    quote = _string(value, "text")
    if text[start:end] != quote:
        raise ValueError(f"{name} literal mismatch in {_string(relation, 'case_id')}")
    return TextSpan(start, end)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _objects(value: object, name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise TypeError(f"{name} must be an array of objects")
    return tuple(cast(dict[str, Any], item) for item in value)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _string(value: Mapping[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise TypeError(f"{name} must be a non-empty string")
    return result


def _integer(value: Mapping[str, Any], name: str) -> int:
    result = value.get(name)
    if isinstance(result, bool) or not isinstance(result, int):
        raise TypeError(f"{name} must be an integer")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", type=Path, default=Path("evidence/T059/t057-strict-development.jsonl")
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        default=Path("evidence/T059/t057-strict-development.manifest.json"),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("evidence/T062/development-ledger-v1.json"),
    )
    parser.add_argument(
        "--output",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Materialize configured paths and print a compact verified identity."""

    args = _parser().parse_args(argv)
    records, relations, fingerprint = materialize(
        args.base, args.base_manifest, args.ledger, args.output, args.manifest
    )
    print(
        json.dumps(
            {"records": records, "relations": relations, "fingerprint": fingerprint},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
