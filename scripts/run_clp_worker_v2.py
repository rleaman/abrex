"""Run pinned full CLP V5.1 behind the structure-aware JSON V2 boundary.

This script is intentionally standalone so it can run with the
CellLiteraturePipeline environment, which owns the BioC and TypeSafe runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PINNED_COMMIT = "323fd4f51aa3c5b54ed30f37dd297b00b49e277e"
PINNED_POLICY = "abbr-section-choice-v5.1"
PINNED_MODEL = "jev-1.13.0"
PINNED_THRESHOLD = 0.52
PINNED_ARCHIVE_SHA256 = (
    "290a52ad53216de64fca78abff2682057cc77b0d3c3ee698580a8ca9f94df7d7"
)
PINNED_BLOB_SHA256 = {
    "src/clp/abbr/explore_bioc_abbr_tables.py": (
        "597dc6acf5564744fc3b1dcc374fbc89a504e7ba8a44f55a0b07fc11049c2fdc"
    ),
    "src/clp/abbr/explore_bioc_abbr_tables_jev.py": (
        "e3fd19dbc6cbef5a5eb7684a7be54e0e7b0634ace21995465d3240034aa119e7"
    ),
}


def main(argv: Sequence[str] | None = None) -> int:
    """Validate, execute, and write one CLP V2 response."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument(
        "--source-archive",
        type=Path,
        default=Path("resources/clp/clp-v5.1-source.zip"),
    )
    parser.add_argument("--dictionary", required=True, type=Path)
    parser.add_argument("--jev-cache", type=Path)
    parser.add_argument(
        "--mode", choices=("rules-only", "cached-full"), default="cached-full"
    )
    args = parser.parse_args(argv)

    request = _object(json.loads(args.request.read_text(encoding="utf-8")), "request")
    if request.get("schema_version") != "clp-abbr-worker-request-v2":
        raise ValueError("request schema_version must be clp-abbr-worker-request-v2")
    documents = request.get("documents")
    if not isinstance(documents, list):
        raise TypeError("request.documents must be an array")
    identities = [
        str(_object(item, "document").get("document_id")) for item in documents
    ]
    if len(set(identities)) != len(identities):
        raise ValueError("request document IDs must be unique")
    if args.mode == "cached-full" and args.jev_cache is None:
        raise ValueError("cached-full mode requires --jev-cache")

    _validate_pinned_source_archive(args.source_archive)
    sys.path.insert(0, f"{args.source_archive.resolve()}/src")
    import bioc
    from clp.abbr import explore_bioc_abbr_tables as base
    from clp.abbr import explore_bioc_abbr_tables_jev as hybrid

    dictionary = base.load_ab3p_dictionary(args.dictionary)
    judge = (
        hybrid.TypeSafeJevJudge(
            model="jev-latest",
            cache_path=args.jev_cache,
            cache_only=True,
        )
        if args.mode == "cached-full"
        else None
    )
    results = []
    for raw_document in documents:
        document_request = _object(raw_document, "document")
        source_document = _bioc_document(bioc, document_request)
        analysis = hybrid.analyze_section(
            str(document_request["source_filename"]),
            source_document,
            int(document_request["start_position"]),
            judge,
            dictionary,
            confidence_threshold=PINNED_THRESHOLD,
        )
        results.append(_result(document_request, analysis))

    response = {
        "schema_version": "clp-abbr-worker-response-v2",
        "request_id": str(request["request_id"]),
        "worker_identity": "CellLiteraturePipeline/full-clp",
        "worker_version": PINNED_COMMIT,
        "policy_version": PINNED_POLICY,
        "model_version": PINNED_MODEL,
        "documents": results,
    }
    args.response.write_text(
        json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "documents": len(results),
                "mode": args.mode,
                "response": str(args.response),
            },
            sort_keys=True,
        )
    )
    return 0


def _validate_pinned_source_archive(archive: Path) -> None:
    actual_archive = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual_archive != PINNED_ARCHIVE_SHA256:
        raise RuntimeError(f"pinned CLP archive hash mismatch: {actual_archive}")
    with zipfile.ZipFile(archive) as stream:
        for relative, expected in PINNED_BLOB_SHA256.items():
            actual = hashlib.sha256(stream.read(relative)).hexdigest()
            if actual != expected:
                raise RuntimeError(
                    f"pinned CLP source hash mismatch for {relative}: {actual}"
                )


def _bioc_document(bioc: Any, request: Mapping[str, Any]) -> Any:
    raw_passages = request.get("passages")
    if not isinstance(raw_passages, list) or not raw_passages:
        raise ValueError("V2 document requires passages")
    document = bioc.BioCDocument()
    document.id = str(request["document_id"])
    document.infons = {"source_filename": str(request["source_filename"])}
    positions = []
    for raw_passage in raw_passages:
        value = _object(raw_passage, "passage")
        positions.append(int(value["position"]))
        passage = bioc.BioCPassage()
        passage.offset = int(value["source_offset"])
        passage.text = str(value["text"])
        passage.infons = {
            "section_type": str(value.get("section_type", "")),
            "type": str(value.get("passage_type", "")),
        }
        if value.get("xml") is not None:
            passage.infons["xml"] = str(value["xml"])
        document.passages.append(passage)
    if positions != list(range(len(raw_passages))):
        raise ValueError("V2 passage positions must be contiguous and ordered")
    return document


def _result(request: Mapping[str, Any], analysis: Any) -> dict[str, Any]:
    candidate = analysis.final_candidate
    pairs = []
    if candidate is not None:
        for pair_number, pair in enumerate(candidate.pairs):
            occurrences = pair.source_occurrences or [pair.source_passage_indexes]
            for occurrence_number, positions in enumerate(occurrences):
                pairs.append(
                    _pair_result(
                        request,
                        pair,
                        tuple(int(value) for value in positions),
                        f"pair-{pair_number:04d}-{occurrence_number:03d}",
                    )
                )
    return {
        "document_id": str(request["document_id"]),
        "disposition": _enum_value(analysis.disposition),
        "decision_source": _enum_value(analysis.decision_source),
        "pairs": pairs,
    }


def _pair_result(
    request: Mapping[str, Any], pair: Any, positions: tuple[int, ...], pair_id: str
) -> dict[str, Any]:
    orientation = _enum_value(pair.orientation)
    if orientation == "FIRST_IS_SF":
        short_form, long_form = str(pair.first), str(pair.second)
    elif orientation == "SECOND_IS_SF":
        short_form, long_form = str(pair.second), str(pair.first)
    else:
        return {
            "pair_id": pair_id,
            "decision": "unscorable",
            "short_form": str(pair.first),
            "long_form": str(pair.second),
            "short_span": None,
            "long_span": None,
            "rule": f"{pair.parser_pattern}:{pair.parser_subpattern or ''}",
            "orientation": "FIRST_IS_SF",
            "source_passage_indexes": [],
            "mapping_status": "orientation_unknown",
        }
    short_span = _unique_span(request, short_form, positions)
    long_span = _unique_span(request, long_form, positions)
    mapped = short_span is not None and long_span is not None
    raw_passages = request["passages"]
    if not isinstance(raw_passages, list):
        raise TypeError("V2 document passages must be an array")
    source_indexes = [
        int(_object(raw_passages[position], "passage")["source_index"])
        for position in positions
    ]
    return {
        "pair_id": pair_id,
        "decision": "accepted" if mapped else "unscorable",
        "short_form": short_form,
        "long_form": long_form,
        "short_span": short_span,
        "long_span": long_span,
        "rule": f"{pair.parser_pattern}:{pair.parser_subpattern or ''}",
        "orientation": orientation,
        "source_passage_indexes": source_indexes,
        "mapping_status": "mapped" if mapped else "ambiguous_or_missing_occurrence",
    }


def _unique_span(
    request: Mapping[str, Any], value: str, positions: tuple[int, ...]
) -> dict[str, int] | None:
    raw_passages = request.get("passages")
    if not isinstance(raw_passages, list):
        raise TypeError("V2 document passages must be an array")
    matches: list[tuple[int, int]] = []
    for position in positions:
        passage = _object(raw_passages[position], "passage")
        text = str(passage["text"])
        canonical_start = int(passage["canonical_start"])
        cursor = 0
        while True:
            found = text.find(value, cursor)
            if found < 0:
                break
            matches.append(
                (canonical_start + found, canonical_start + found + len(value))
            )
            cursor = found + 1
    if len(matches) != 1:
        return None
    return {"start": matches[0][0], "end": matches[0][1]}


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _object(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
