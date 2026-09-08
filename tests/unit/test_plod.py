from __future__ import annotations

from typing import Any, cast

import pytest

from abrex.domain import Document
from abrex.resolvers import (
    PlodConfig,
    PlodSpanDetector,
    RawPlodSpan,
    serialize_span_record,
)


class FakeTagger:
    def predict(self, text: str) -> tuple[RawPlodSpan, ...]:
        result: list[RawPlodSpan] = []
        if "TNF" in text:
            start = text.index("TNF")
            result.append(RawPlodSpan("AC", start, start + 3, 0.9))
        if "tumor necrosis factor" in text:
            start = text.index("tumor necrosis factor")
            result.append(RawPlodSpan("LF", start, start + 21, 0.8))
        return tuple(result)


def _detector(**kwargs: object) -> PlodSpanDetector:
    return PlodSpanDetector(
        config=PlodConfig(
            checkpoint_path="missing.bin", **cast(dict[str, Any], kwargs)
        ),
        tagger=FakeTagger(),
    )


def test_detector_maps_ac_to_short_form_and_preserves_scores() -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    record = _detector().detect(document)

    actual = [
        (x.label, x.text, x.span.start, x.span.end) for x in record.validated_spans
    ]
    assert sorted(actual) == sorted(
        [("LF", "tumor necrosis factor", 0, 21), ("SF", "TNF", 23, 26)]
    )
    predictions = tuple(_detector().resolve(document))
    assert predictions[0].prediction is not None
    assert {item.prediction.score for item in predictions if item.prediction} == {
        0.8,
        0.9,
    }
    assert any(
        item.short_form_text == "TNF" and item.long_form is None for item in predictions
    )


def test_detector_windows_translate_offsets_and_deduplicate() -> None:
    document = Document("d1", "x TNF y TNF z")
    detector = _detector(max_chars_per_window=8, window_overlap=4)
    record = detector.detect(document)

    assert [(x.span.start, x.span.end) for x in record.validated_spans] == [
        (2, 5),
        (8, 11),
    ]
    assert all(x.source_window_start >= 0 for x in record.validated_spans)


def test_detector_records_unknown_labels_and_serializes_raw_and_validated() -> None:
    class UnknownTagger:
        def predict(self, text: str) -> tuple[RawPlodSpan, ...]:
            return (RawPlodSpan("OTHER", 0, 1, 0.1),)

    detector = PlodSpanDetector(
        config=PlodConfig(checkpoint_path="missing.bin"), tagger=UnknownTagger()
    )
    record = detector.detect(Document("d1", "x"))
    encoded = serialize_span_record(record)

    assert "ignored_label:OTHER" in encoded
    assert '"raw_spans"' in encoded
    assert '"validated_spans":[]' in encoded


def test_config_rejects_invalid_checkpoint_hash() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        PlodConfig(checkpoint_path="x", checkpoint_sha256="A")


def test_cache_identity_includes_checkpoint_and_segmentation_config() -> None:
    detector = PlodSpanDetector(
        config=PlodConfig(
            checkpoint_path="model.bin",
            checkpoint_sha256="a" * 64,
            max_chars_per_window=100,
        ),
        tagger=FakeTagger(),
    )
    changed = PlodSpanDetector(
        config=PlodConfig(
            checkpoint_path="model.bin",
            checkpoint_sha256="a" * 64,
            max_chars_per_window=101,
        ),
        tagger=FakeTagger(),
    )
    assert detector.cache_identity["checkpoint_sha256"] == "a" * 64
    assert detector.cache_identity != changed.cache_identity
