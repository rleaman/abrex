"""Build and summarize the configured historical corpus variants.

This intentionally consumes the same typed configuration and canonical
serialization path as the CLI.  It emits a small report, while raw sources
and canonical JSONL remain user-managed/ignored artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from abrex.config import load_resolved_config, serialize_resolved_config
from abrex.corpora import (
    CorpusAdapterError,
    corpus_config_from_resolved,
    create_corpus_pipeline,
    fingerprint_file,
    write_canonical_dataset,
)

DEFAULT_CONFIGS = tuple(sorted(Path("configs/corpora").glob("*.yaml")))


def audit_config(path: Path) -> dict[str, object]:
    """Build one configured corpus and return compact source-to-canonical data."""

    resolved = load_resolved_config((path,))
    config = corpus_config_from_resolved(resolved)
    source = config.source.to_resource()
    entry: dict[str, object] = {
        "config": str(path),
        "dataset_id": source.identifier,
        "semantics": (
            config.semantics.model_dump(mode="json")
            if config.semantics is not None
            else None
        ),
        "source": {
            "identifier": source.identifier,
            "path": str(source.location) if source.location is not None else None,
            "format": source.format,
        },
    }
    if source.location is None or not source.location.is_file():
        entry["status"] = "unavailable_source"
        entry["source_error"] = "configured source file is absent"
        return entry

    entry["source"] = {
        "identifier": source.identifier,
        "path": str(source.location),
        "format": source.format,
        "sha256": fingerprint_file(source.location),
    }
    entry["raw_inventory"] = inspect_source(source.location, config.adapter.type)
    pipeline = create_corpus_pipeline(config)
    try:
        build = pipeline.build(source)
    except CorpusAdapterError as error:
        entry["status"] = "parse_error"
        entry["source_error"] = str(error)
        return entry
    if config.output is None:
        raise ValueError(f"Historical audit config must declare output: {path}")

    config_fingerprint = hashlib.sha256(
        serialize_resolved_config(resolved, format="json").encode("utf-8")
    ).hexdigest()
    manifest = write_canonical_dataset(
        build,
        config.output.jsonl_path,
        manifest_path=config.output.manifest_path,
        mode="strict" if config.strict else "permissive",
        config_fingerprint=config_fingerprint,
    )
    codes = Counter(item.code for item in build.diagnostics.diagnostics)
    eligible_metric = config.semantics.eligible_metric if config.semantics else None
    eligible_scoreable_units = sum(
        (
            annotation.short_form is not None and annotation.long_form is not None
            if eligible_metric == "exact_pair"
            else annotation.short_form is not None or annotation.long_form is not None
            if eligible_metric == "exact_span"
            else False
        )
        for record in build.records
        for annotation in record.gold_annotations
    )
    entry["status"] = "built"
    entry["adapter"] = {
        "identity": build.adapter_identity,
        "version": build.adapter_version,
        "policy_identity": getattr(pipeline.adapter, "policy_identity", None),
    }
    entry["counts"] = {
        "raw_records_parsed": build.source_record_count,
        "parsed_annotations_emitted": build.source_annotation_count,
        "canonical_records": manifest.record_count,
        "canonical_annotations": manifest.annotation_count,
        "eligible_metric": eligible_metric,
        "eligible_scoreable_units": eligible_scoreable_units,
        "diagnostics": build.diagnostics.total,
        "diagnostics_by_code": dict(sorted(codes.items())),
        "validation": {
            "records_seen": manifest.validation.records_seen,
            "records_kept": manifest.validation.records_kept,
            "records_dropped": manifest.validation.records_dropped,
            "repaired": manifest.validation.repaired,
            "ambiguous": manifest.validation.ambiguous,
            "unscoreable": manifest.validation.unscoreable,
        },
    }
    entry["artifacts"] = {
        "canonical_jsonl": str(config.output.jsonl_path),
        "canonical_jsonl_sha256": manifest.fingerprint,
        "manifest": str(config.output.manifest_path),
    }
    return entry


def inspect_source(path: Path, adapter_type: str) -> dict[str, int]:
    """Count source units without applying canonical pairing or validation."""

    if path.suffix.lower() == ".xml":
        root = ET.parse(path).getroot()
        documents = tuple(root.iter("document"))
        annotations = tuple(root.iter("annotation"))
        relations = tuple(root.iter("relation"))
        locations = tuple(root.iter("location"))
        duplicate_documents = 0
        for document in documents:
            identifiers = [
                annotation.get("id") for annotation in document.iter("annotation")
            ]
            if len(identifiers) != len(set(identifiers)):
                duplicate_documents += 1
        return {
            "records": len(documents),
            "annotation_nodes": len(annotations),
            "relation_nodes": len(relations),
            "location_nodes": len(locations),
            "discontinuous_annotations": sum(
                len(tuple(annotation.findall("location"))) > 1
                for annotation in annotations
            ),
            "records_with_duplicate_annotation_ids": duplicate_documents,
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    documents = raw.get("documents", []) if isinstance(raw, dict) else raw
    if not isinstance(documents, list):
        raise CorpusAdapterError("JSON source must contain a list of records")
    annotation_nodes = relation_nodes = location_nodes = 0
    discontinuous = duplicate_documents = 0
    for document in documents:
        if not isinstance(document, dict):
            continue
        if adapter_type == "sdu_aaai22_ae":
            acronyms = document.get("acronyms", [])
            long_forms = document.get("long-forms", document.get("long_forms", []))
            source_spans = len(acronyms) + len(long_forms)
            annotation_nodes += source_spans
            location_nodes += source_spans
        elif adapter_type == "sdu_aaai21_ai":
            annotation_nodes += sum(
                isinstance(label, str) and label.startswith("B-")
                for label in document.get("labels", [])
            )
        else:
            annotations = document.get("annotations", [])
            if not isinstance(annotations, list):
                continue
            ids: list[object] = []
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                annotation_nodes += 1
                ids.append(annotation.get("id"))
                locations = annotation.get("locations", [])
                if isinstance(locations, list):
                    location_nodes += len(locations)
                    discontinuous += len(locations) > 1
            duplicate_documents += len(ids) != len(set(ids))
            relations = document.get("relations", [])
            relation_nodes += len(relations) if isinstance(relations, list) else 0
    if adapter_type == "sdu_aaai21_ad":
        annotation_nodes = len(documents)
    return {
        "records": len(documents),
        "annotation_nodes": annotation_nodes,
        "relation_nodes": relation_nodes,
        "location_nodes": location_nodes,
        "discontinuous_annotations": discontinuous,
        "records_with_duplicate_annotation_ids": duplicate_documents,
    }


def build_report(configs: tuple[Path, ...]) -> dict[str, object]:
    """Audit all requested configs, continuing across absent source variants."""

    entries = tuple(audit_config(path) for path in configs)
    return {
        "schema_version": "historical-corpus-audit-v1",
        "configs": [str(path) for path in configs],
        "entries": list(entries),
        "excluded_variants": [
            {
                "dataset_id": "schwartz_hearst_badrex",
                "status": "unavailable_settled",
                "reason": "docs/badrex-availability.md",
            },
            {
                "dataset_id": "medstract_badrex",
                "status": "unavailable_settled",
                "reason": "docs/badrex-availability.md",
            },
        ],
    }


def main() -> int:
    """Run the historical audit report command."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("configs", nargs="*", type=Path)
    args = parser.parse_args()
    configs = tuple(args.configs) or DEFAULT_CONFIGS
    report: dict[str, object] = build_report(configs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
