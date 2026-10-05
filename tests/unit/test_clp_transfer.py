"""Tests for pinned CLP replay and exact-offset analysis."""

from __future__ import annotations

from abrex.evaluation.clp_transfer import analyze_exact_offsets, compact_replay


def _snapshot() -> dict[str, object]:
    return {
        "record_id": "section-1",
        "document_id": "clp:1:2",
        "decision": "valid_abbreviation_section",
        "provenance": {
            "source_filename": "source.xml.gz",
            "source_document_id": "1",
            "source_start_index": 2,
            "source_commit": "a" * 40,
        },
        "passages": [
            {
                "index": 2,
                "canonical_start": 0,
                "text": "ABC\talpha beta complex",
            }
        ],
        "annotations": [
            {
                "short_form": "ABC",
                "long_form": "alpha beta complex",
                "short_span": [0, 3],
                "long_span": [4, 22],
                "source_passage_indexes": [2],
            },
            {
                "short_form": "ABC",
                "long_form": "unmapped reference",
                "short_span": None,
                "long_span": None,
                "source_passage_indexes": [2],
            },
        ],
    }


def _sequence() -> dict[str, object]:
    return {
        "base": {
            "filename": "source.xml.gz",
            "document_id": "1",
            "start_index": 2,
        },
        "disposition": "ACCEPTED",
        "decision_source": "DETERMINISTIC",
        "decision_reason": "clear",
        "final_candidate": {
            "pattern": "PATTERN_3",
            "subpattern": "TWO_COLUMN_TABLE",
            "end_index": 3,
            "pairs": [
                {
                    "first": "ABC",
                    "second": "alpha beta complex",
                    "orientation": "FIRST_IS_SF",
                    "orientation_evidence": ["STRUCTURAL_FIRST_IS_SF"],
                    "source_passage_indexes": [2],
                    "source_occurrences": [[2]],
                    "parser_pattern": "PATTERN_3",
                    "parser_subpattern": "TWO_COLUMN_TABLE",
                }
            ],
        },
    }


def test_compact_replay_preserves_structure_and_decision_identity() -> None:
    rows = compact_replay(
        [_snapshot()],
        [_sequence()],
        variant="rules_only",
        source_identity={"sha256": "abc"},
    )

    assert len(rows) == 1
    assert rows[0]["record_id"] == "section-1"
    assert rows[0]["pattern"] == "PATTERN_3"
    assert rows[0]["pairs"][0]["source_occurrences"] == [[2]]
    assert rows[0]["source_identity"] == {"sha256": "abc"}


def test_exact_analysis_keeps_mapping_loss_out_of_false_positives() -> None:
    replay = compact_replay(
        [_snapshot()],
        [_sequence()],
        variant="full",
        source_identity={"sha256": "abc"},
    )

    report = analyze_exact_offsets([_snapshot()], replay)

    assert report["counts"]["gold_pairs_native"] == 2
    assert report["counts"]["gold_pairs_exact_scoreable"] == 1
    assert report["counts"]["gold_pairs_unmapped"] == 1
    assert report["counts"]["true_positives"] == 1
    assert report["counts"]["false_positives"] == 0
    assert report["counts"]["false_negatives"] == 0
    assert report["error_categories"]["source_structure_mapping"] == 1


def test_compact_replay_rejects_missing_selected_sections() -> None:
    try:
        compact_replay(
            [_snapshot()],
            [],
            variant="full",
            source_identity={},
        )
    except ValueError as error:
        assert "omitted 1 selected sections" in str(error)
    else:
        raise AssertionError("missing section was not rejected")
