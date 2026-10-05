"""Replay and exact-offset analysis for the pinned CLP V5.1 boundary."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

CLP_REPLAY_SCHEMA = "clp-v5.1-compact-replay-v1"


@dataclass(frozen=True, slots=True)
class OffsetPair:
    """One literal CLP pair mapped to half-open canonical offsets."""

    short_form: str
    long_form: str
    short_span: tuple[int, int] | None
    long_span: tuple[int, int] | None
    rule: str
    source_passage_indexes: tuple[int, ...]

    @property
    def mapped(self) -> bool:
        """Return whether both endpoints map to unique source occurrences."""

        return self.short_span is not None and self.long_span is not None

    def exact_key(self) -> tuple[int, int, int, int] | None:
        """Return the exact pair key when both endpoints are mapped."""

        if self.short_span is None or self.long_span is None:
            return None
        return (*self.short_span, *self.long_span)

    def normalized_key(self) -> tuple[str, str]:
        """Return a deliberately narrow case-folded string key."""

        return (_normalized(self.short_form), _normalized(self.long_form))


def read_json(path: Path) -> Mapping[str, Any]:
    """Read one JSON object."""

    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def read_jsonl(path: Path) -> tuple[Mapping[str, Any], ...]:
    """Read JSON objects from a JSON Lines artifact."""

    rows: list[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            rows.append(_mapping(value, f"{path}:{line_number}"))
    return tuple(rows)


def compact_replay(
    snapshot_rows: Sequence[Mapping[str, Any]],
    sequence_rows: Iterable[Mapping[str, Any]],
    *,
    variant: str,
    source_identity: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Select CLP sequence decisions that exactly match the tracked 200 sections."""

    wanted = {_snapshot_source_key(row): row for row in snapshot_rows}
    selected: dict[tuple[str, str, int], Mapping[str, Any]] = {}
    for sequence in sequence_rows:
        base = _mapping(sequence.get("base"), "sequence.base")
        key = _sequence_source_key(base)
        if key not in wanted:
            continue
        if key in selected:
            raise ValueError(f"duplicate CLP replay identity: {key!r}")
        selected[key] = sequence
    missing = sorted(set(wanted) - set(selected))
    if missing:
        raise ValueError(f"CLP replay omitted {len(missing)} selected sections")

    rows: list[dict[str, Any]] = []
    for key in sorted(wanted):
        snapshot = wanted[key]
        sequence = selected[key]
        candidate_value = sequence.get("final_candidate")
        candidate = (
            _mapping(candidate_value, "sequence.final_candidate")
            if candidate_value is not None
            else None
        )
        pairs: list[dict[str, Any]] = []
        if candidate is not None:
            raw_pairs = candidate.get("pairs", [])
            if not isinstance(raw_pairs, list):
                raise TypeError("sequence.final_candidate.pairs must be an array")
            pairs = [_compact_pair(_mapping(pair, "CLP pair")) for pair in raw_pairs]
        provenance = _mapping(snapshot.get("provenance"), "snapshot.provenance")
        rows.append(
            {
                "schema_version": CLP_REPLAY_SCHEMA,
                "variant": variant,
                "record_id": _required_string(snapshot, "record_id"),
                "document_id": _required_string(snapshot, "document_id"),
                "source": {
                    "filename": key[0],
                    "document_id": key[1],
                    "start_index": key[2],
                    "source_commit": provenance.get("source_commit"),
                },
                "disposition": sequence.get("disposition"),
                "decision_source": sequence.get("decision_source"),
                "decision_reason": sequence.get("decision_reason"),
                "pattern": candidate.get("pattern") if candidate is not None else None,
                "subpattern": (
                    candidate.get("subpattern") if candidate is not None else None
                ),
                "end_index": (
                    candidate.get("end_index") if candidate is not None else None
                ),
                "pairs": pairs,
                "source_identity": dict(source_identity),
            }
        )
    return tuple(rows)


def analyze_exact_offsets(
    snapshot_rows: Sequence[Mapping[str, Any]],
    replay_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare one CLP replay to the scoreable Abrex exact-offset projection."""

    replay_by_id = {_required_string(row, "record_id"): row for row in replay_rows}
    if len(replay_by_id) != len(replay_rows):
        raise ValueError("duplicate record_id in CLP replay")

    totals: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_article: dict[str, Counter[str]] = defaultdict(Counter)
    for snapshot in snapshot_rows:
        record_id = _required_string(snapshot, "record_id")
        replay = replay_by_id.get(record_id)
        if replay is None:
            raise ValueError(f"CLP replay missing {record_id}")
        provenance = _mapping(snapshot.get("provenance"), "snapshot.provenance")
        article_id = _required_string(provenance, "source_document_id")
        decision = snapshot.get("decision")
        gold = _gold_pairs(snapshot)
        predicted = _prediction_pairs(snapshot, replay)
        totals["sections"] += 1
        by_article[article_id]["sections"] += 1

        if decision == "needs_parser_extension":
            totals["excluded_parser_extension_sections"] += 1
            totals["excluded_parser_extension_pairs"] += len(gold)
            continue
        totals["scored_sections"] += 1
        mapped_gold = [pair for pair in gold if pair.mapped]
        unmapped_gold = [pair for pair in gold if not pair.mapped]
        mapped_predicted = [pair for pair in predicted if pair.mapped]
        unmapped_predicted = [pair for pair in predicted if not pair.mapped]
        totals["gold_pairs_native"] += len(gold)
        totals["gold_pairs_exact_scoreable"] += len(mapped_gold)
        totals["gold_pairs_unmapped"] += len(unmapped_gold)
        totals["predicted_pairs"] += len(predicted)
        totals["predicted_pairs_mapped"] += len(mapped_predicted)
        totals["predicted_pairs_unmapped"] += len(unmapped_predicted)

        gold_exact = Counter(
            cast(tuple[int, int, int, int], pair.exact_key()) for pair in mapped_gold
        )
        predicted_exact = Counter(
            cast(tuple[int, int, int, int], pair.exact_key())
            for pair in mapped_predicted
        )
        unscorable_strings = Counter(pair.normalized_key() for pair in unmapped_gold)
        predicted_by_exact: dict[tuple[int, int, int, int], list[OffsetPair]] = (
            defaultdict(list)
        )
        for pair in mapped_predicted:
            key = pair.exact_key()
            if key is not None:
                predicted_by_exact[key].append(pair)

        true_positive = gold_exact & predicted_exact
        tp = sum(true_positive.values())
        fn_counter = gold_exact - predicted_exact
        fp_counter = predicted_exact - gold_exact
        excluded = 0
        for exact_key, count in tuple(fp_counter.items()):
            pair = predicted_by_exact[exact_key][0]
            available = unscorable_strings[pair.normalized_key()]
            moved = min(count, available)
            if moved:
                excluded += moved
                fp_counter[exact_key] -= moved
                unscorable_strings[pair.normalized_key()] -= moved
                if fp_counter[exact_key] == 0:
                    del fp_counter[exact_key]
        fp = sum(fp_counter.values())
        fn = sum(fn_counter.values())
        totals.update(
            {
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "excluded_unmapped_reference_predictions": excluded,
            }
        )
        by_article[article_id].update(
            {"true_positives": tp, "false_positives": fp, "false_negatives": fn}
        )

        predicted_normalized = Counter(pair.normalized_key() for pair in predicted)
        predicted_short = {_normalized(pair.short_form) for pair in predicted}
        predicted_long = {_normalized(pair.long_form) for pair in predicted}
        accepted = replay.get("disposition") in {"ACCEPTED", "ACCEPTED_WITH_REVIEW"}
        gold_by_exact = {
            cast(tuple[int, int, int, int], pair.exact_key()): pair
            for pair in mapped_gold
        }
        for exact_key, count in fn_counter.items():
            pair = gold_by_exact[exact_key]
            category = _error_category(
                pair,
                accepted=accepted,
                predicted_normalized=predicted_normalized,
                predicted_short=predicted_short,
                predicted_long=predicted_long,
            )
            error_counts[category] += count
            _add_example(examples, category, record_id, article_id, pair, count)
        if unmapped_gold:
            error_counts["source_structure_mapping"] += len(unmapped_gold)
            for pair in unmapped_gold:
                _add_example(
                    examples,
                    "source_structure_mapping",
                    record_id,
                    article_id,
                    pair,
                    1,
                )

    tp = totals["true_positives"]
    fp = totals["false_positives"]
    fn = totals["false_negatives"]
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "matching_policy": "half-open exact short-form and long-form offsets",
        "counts": dict(sorted(totals.items())),
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall),
        },
        "error_categories": dict(sorted(error_counts.items())),
        "examples": {key: value for key, value in sorted(examples.items())},
        "article_groups": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_article.items())
        },
        "limitations": [
            "Exact-offset denominators contain only uniquely mapped gold occurrences.",
            (
                "Predictions matching an unmapped gold string pair are excluded, "
                "not false positives."
            ),
            "Parser-extension sections are outside strict scoring and remain explicit.",
            "This risk-stratified development set is not independent validation.",
        ],
    }


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    """Write deterministic JSON Lines and return its SHA-256."""

    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compact_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    raw_occurrences = pair.get("source_occurrences", [])
    if not isinstance(raw_occurrences, list):
        raise TypeError("CLP pair source_occurrences must be an array")
    raw_indexes = pair.get("source_passage_indexes", [])
    if not isinstance(raw_indexes, list):
        raise TypeError("CLP pair source_passage_indexes must be an array")
    return {
        "first": _required_string(pair, "first"),
        "second": _required_string(pair, "second"),
        "orientation": pair.get("orientation"),
        "orientation_evidence": pair.get("orientation_evidence", []),
        "source_passage_indexes": [int(value) for value in raw_indexes],
        "source_occurrences": [
            list(_integer_tuple(occurrence))
            for occurrence in raw_occurrences
            if isinstance(occurrence, list)
        ],
        "parser_pattern": pair.get("parser_pattern"),
        "parser_subpattern": pair.get("parser_subpattern"),
    }


def _gold_pairs(snapshot: Mapping[str, Any]) -> list[OffsetPair]:
    raw_annotations = snapshot.get("annotations", [])
    if not isinstance(raw_annotations, list):
        raise TypeError("snapshot.annotations must be an array")
    pairs: list[OffsetPair] = []
    for raw in raw_annotations:
        annotation = _mapping(raw, "snapshot annotation")
        pairs.append(
            OffsetPair(
                _required_string(annotation, "short_form"),
                _required_string(annotation, "long_form"),
                _optional_span(annotation.get("short_span")),
                _optional_span(annotation.get("long_span")),
                "gold",
                _integer_tuple(annotation.get("source_passage_indexes", [])),
            )
        )
    return pairs


def _prediction_pairs(
    snapshot: Mapping[str, Any], replay: Mapping[str, Any]
) -> list[OffsetPair]:
    raw_pairs = replay.get("pairs", [])
    if not isinstance(raw_pairs, list):
        raise TypeError("replay.pairs must be an array")
    pairs: list[OffsetPair] = []
    for raw in raw_pairs:
        pair = _mapping(raw, "replay pair")
        orientation = pair.get("orientation")
        first = _required_string(pair, "first")
        second = _required_string(pair, "second")
        if orientation == "FIRST_IS_SF":
            short_form, long_form = first, second
        elif orientation == "SECOND_IS_SF":
            short_form, long_form = second, first
        else:
            continue
        raw_occurrences = pair.get("source_occurrences", [])
        occurrences = (
            [_integer_tuple(value) for value in raw_occurrences]
            if isinstance(raw_occurrences, list) and raw_occurrences
            else [_integer_tuple(pair.get("source_passage_indexes", []))]
        )
        for passage_indexes in occurrences:
            pairs.append(
                OffsetPair(
                    short_form,
                    long_form,
                    _map_unique(snapshot, short_form, passage_indexes),
                    _map_unique(snapshot, long_form, passage_indexes),
                    str(pair.get("parser_pattern") or "unknown"),
                    passage_indexes,
                )
            )
    return pairs


def _map_unique(
    snapshot: Mapping[str, Any], value: str, indexes: Sequence[int]
) -> tuple[int, int] | None:
    raw_passages = snapshot.get("passages", [])
    if not isinstance(raw_passages, list):
        raise TypeError("snapshot.passages must be an array")
    wanted = set(indexes)
    matches: list[tuple[int, int]] = []
    for raw in raw_passages:
        passage = _mapping(raw, "snapshot passage")
        if int(passage["index"]) not in wanted:
            continue
        text = str(passage.get("text", ""))
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
    return matches[0] if len(matches) == 1 else None


def _error_category(
    pair: OffsetPair,
    *,
    accepted: bool,
    predicted_normalized: Counter[tuple[str, str]],
    predicted_short: set[str],
    predicted_long: set[str],
) -> Literal[
    "acceptance",
    "endpoint_boundaries",
    "orientation",
    "pairing",
    "candidate_omission",
]:
    if not accepted:
        return "acceptance"
    short_form, long_form = pair.normalized_key()
    if predicted_normalized[(long_form, short_form)]:
        return "orientation"
    if predicted_normalized[(short_form, long_form)]:
        return "endpoint_boundaries"
    if short_form in predicted_short and long_form in predicted_long:
        return "pairing"
    return "candidate_omission"


def _add_example(
    examples: dict[str, list[dict[str, Any]]],
    category: str,
    record_id: str,
    article_id: str,
    pair: OffsetPair,
    count: int,
) -> None:
    if len(examples[category]) >= 5:
        return
    examples[category].append(
        {
            "record_id": record_id,
            "article_group_id": article_id,
            "short_form": pair.short_form,
            "long_form": pair.long_form,
            "short_span": list(pair.short_span) if pair.short_span else None,
            "long_span": list(pair.long_span) if pair.long_span else None,
            "occurrences": count,
        }
    )


def _snapshot_source_key(row: Mapping[str, Any]) -> tuple[str, str, int]:
    provenance = _mapping(row.get("provenance"), "snapshot.provenance")
    return (
        _required_string(provenance, "source_filename"),
        _required_string(provenance, "source_document_id"),
        int(provenance["source_start_index"]),
    )


def _sequence_source_key(base: Mapping[str, Any]) -> tuple[str, str, int]:
    return (
        _required_string(base, "filename"),
        _required_string(base, "document_id"),
        int(base["start_index"]),
    )


def _optional_span(value: object) -> tuple[int, int] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise TypeError("span must be a two-integer array or null")
    return int(value[0]), int(value[1])


def _integer_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise TypeError("passage indexes must be an array")
    return tuple(int(item) for item in value)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise TypeError(f"{key} must be a non-empty string")
    return result


__all__ = [
    "CLP_REPLAY_SCHEMA",
    "OffsetPair",
    "analyze_exact_offsets",
    "compact_replay",
    "read_json",
    "read_jsonl",
    "sha256_file",
    "write_jsonl",
]
