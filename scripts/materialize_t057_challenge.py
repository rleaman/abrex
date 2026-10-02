"""Materialize the frozen T057 strict challenge as a canonical dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from abrex.corpora import (
    CorpusBuildResult,
    DiagnosticsSummary,
    SourceResource,
    write_canonical_dataset,
)
from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    TextSpan,
)

ADAPTER_IDENTITY = "t057_strict_development_view"
ADAPTER_VERSION = "1"


def materialize(
    packet_path: Path,
    strict_view_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> tuple[int, int, str]:
    """Join frozen text and strict relations, validating every source identity."""

    packet = _object(packet_path)
    strict = _object(strict_view_path)
    packet_cases = {
        _string(case, "case_id"): case
        for case in _objects(packet.get("cases"), "packet cases")
    }
    records: list[CorpusRecord] = []
    relation_count = 0
    for strict_case in _objects(strict.get("cases"), "strict cases"):
        case_id = _string(strict_case, "case_id")
        try:
            packet_case = packet_cases[case_id]
        except KeyError as error:
            raise ValueError(f"strict case is absent from packet: {case_id}") from error
        text = _string(packet_case, "text")
        expected_hash = _string(strict_case, "canonical_text_sha256")
        actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"canonical text hash mismatch for {case_id}")
        document = Document(case_id, text)
        annotations: list[AbbreviationDefinition] = []
        for pair in _objects(strict_case.get("exact_pairs"), "exact pairs"):
            short = _span(pair, "short_form", document)
            long = _span(pair, "long_form", document)
            decision_id = _string(pair, "decision_id")
            annotation = AbbreviationDefinition(
                case_id,
                short_form=short,
                long_form=long,
                short_form_text=document.text_for(short),
                long_form_text=document.text_for(long),
                provenance=AnnotationProvenance(
                    source_corpus="T057-development-guidelines-v1",
                    source_record_id=case_id,
                    source_annotation_id=decision_id,
                    adapter_identity=ADAPTER_IDENTITY,
                    adapter_version=ADAPTER_VERSION,
                    transformation_notes=(
                        "assisted_development_evidence",
                        f"article_group_id={_string(strict_case, 'article_group_id')}",
                        f"arm={_string(strict_case, 'arm')}",
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
                record_id=case_id,
                provenance=AnnotationProvenance(
                    source_corpus="T057-development-guidelines-v1",
                    source_record_id=case_id,
                    adapter_identity=ADAPTER_IDENTITY,
                    adapter_version=ADAPTER_VERSION,
                    transformation_notes=(
                        "frozen_strict_exact_pair_projection",
                        "not_independent_gold",
                    ),
                ),
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    result = CorpusBuildResult(
        tuple(records),
        DiagnosticsSummary(),
        SourceResource.from_path(
            "T057-development-guidelines-v1",
            strict_view_path,
            format="t057-development-views-v1",
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
        dataset_id="t057-strict-development-v1",
        manifest_path=manifest_path,
        mode="strict",
    )
    return len(records), relation_count, manifest.fingerprint


def _span(pair: Mapping[str, Any], name: str, document: Document) -> TextSpan:
    value = _mapping(pair.get(name), name)
    start = _integer(value, "start")
    end = _integer(value, "end")
    text = _string(value, "text")
    span = TextSpan(start, end)
    document.validate_span(span, text)
    return span


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
        "--packet", type=Path, default=Path("evidence/T052/review-packet-v2.json")
    )
    parser.add_argument(
        "--strict-view",
        type=Path,
        default=Path("evidence/T057/strict-exact-pair-development.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/T059/t057-strict-development.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evidence/T059/t057-strict-development.manifest.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Materialize the configured paths and print a compact summary."""

    args = _parser().parse_args(argv)
    records, relations, fingerprint = materialize(
        args.packet, args.strict_view, args.output, args.manifest
    )
    print(
        json.dumps(
            {
                "records": records,
                "relations": relations,
                "fingerprint": fingerprint,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
