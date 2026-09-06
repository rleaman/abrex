"""Regression tests for canonical records, Ab3P output, and exact scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from abrex.corpora import read_canonical_jsonl, record_to_dict, serialize_records
from abrex.evaluation import Evaluator, ExactPairMatchingPolicy, PairPRFMetric
from abrex.resolvers import (
    PredictionArtifact,
    PredictionRecord,
    ResolverMetadata,
    parse_ab3p_output,
    reconstruct_predictions,
)
from abrex.resolvers.serialization import read_prediction_artifact

FIXTURES = Path(__file__).parents[1] / "fixtures" / "regression"


def test_reviewed_canonical_fixture_is_stable() -> None:
    path = FIXTURES / "canonical_gold.jsonl"
    records = read_canonical_jsonl(path)
    reviewed_lines = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    )
    assert reviewed_lines == tuple(record_to_dict(record) for record in records)
    assert serialize_records(records).endswith("\n")
    assert len(records) == 6
    assert records[1].document.text[33] == "α"
    assert records[2].gold_annotations[0].long_form_text == "Interleukin-6"


def test_ab3p_golden_predictions_match_reviewed_artifact() -> None:
    records = read_canonical_jsonl(FIXTURES / "canonical_gold.jsonl")
    documents = {record.document.document_id: record.document for record in records}
    outputs = json.loads((FIXTURES / "ab3p_outputs.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (FIXTURES / "ab3p_outputs.provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["fixture"] == "ab3p_outputs.json"
    assert provenance["source_kind"] == "curated_synthetic_output"
    expected = read_prediction_artifact(
        FIXTURES / "expected_predictions.jsonl", documents=documents
    )

    actual_records: list[PredictionRecord] = []
    for record in records:
        raw_output = _string_value(outputs, record.document.document_id)
        actual_records.append(
            PredictionRecord(
                record.document.document_id,
                reconstruct_predictions(record.document, parse_ab3p_output(raw_output)),
                record_id=record.record_id,
            )
        )
    actual = PredictionArtifact(ResolverMetadata("ab3p", "1"), tuple(actual_records))
    assert actual.records == expected.records


def test_exact_evaluation_matches_reviewed_outcomes() -> None:
    gold = read_canonical_jsonl(FIXTURES / "canonical_gold.jsonl")
    documents = {record.document.document_id: record.document for record in gold}
    predictions = read_prediction_artifact(
        FIXTURES / "expected_predictions.jsonl", documents=documents
    )
    result = Evaluator(ExactPairMatchingPolicy(), (PairPRFMetric(),)).evaluate(
        gold, predictions
    )
    expected = json.loads(
        (FIXTURES / "expected_evaluation.json").read_text(encoding="utf-8")
    )
    metric = result.metric("pair_prf")
    assert {key: metric.value(key) for key in expected["metrics"]} == expected[
        "metrics"
    ]
    assert {
        document.document_id: [outcome.status for outcome in document.outcomes]
        for document in result.documents
    } == expected["documents"]


def _string_value(values: Any, key: str) -> str:
    value = values[key]
    assert isinstance(value, str)
    return value
