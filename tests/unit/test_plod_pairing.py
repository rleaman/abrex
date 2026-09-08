from __future__ import annotations

from typing import Literal, cast

from abrex.domain import Document, TextSpan
from abrex.resolvers import (
    PlodConfig,
    PlodPairingConfig,
    PlodPairingResolver,
    PlodSpanRecord,
    PositionAnchoredPairing,
    ValidatedPlodSpan,
)


def _span(label: str, start: int, end: int, text: str) -> ValidatedPlodSpan:
    return ValidatedPlodSpan(
        cast(Literal["SF", "LF"], label), TextSpan(start, end), text[start:end], 0.8, 0
    )


def test_position_anchored_pattern_uses_candidate_slice_not_remote_match() -> None:
    text = "LF1 (SF1) unrelated LF2 SF2"
    document = Document("d", text)
    spans = (
        _span("LF", 0, 3, text),
        _span("SF", 5, 8, text),
        _span("LF", 20, 23, text),
        _span("SF", 24, 27, text),
    )
    config = PlodPairingConfig(
        detector=PlodConfig(checkpoint_path="missing"),
        require_local_pattern=True,
        max_gap=20,
    )

    result = PositionAnchoredPairing().pair(document, spans, config)

    assert len(result.selected) == 1
    assert result.selected[0].short_form.span == TextSpan(5, 8)
    assert "rejected_missing_local_pattern" in result.diagnostics


def test_pairing_handles_shared_long_form_and_rejects_overlap() -> None:
    text = "long form (SF1, SF2)"
    document = Document("d", text)
    spans = (
        _span("LF", 0, 9, text),
        _span("SF", 11, 14, text),
        _span("SF", 16, 19, text),
        _span("LF", 11, 14, text),
    )
    config = PlodPairingConfig(
        detector=PlodConfig(checkpoint_path="missing"),
        selection="shared_long_form",
        max_gap=20,
    )

    result = PositionAnchoredPairing().pair(document, spans, config)

    assert len(result.selected) == 2
    assert "rejected_overlapping_spans" in result.diagnostics


def test_composed_resolver_preserves_pair_and_separate_span_scores() -> None:
    text = "tumor necrosis factor (TNF)"
    document = Document("d", text)

    class FakeDetector:
        cache_identity: dict[str, object]

        def __init__(self, identity: dict[str, object]) -> None:
            self.cache_identity = identity

        def detect(self, value: Document) -> PlodSpanRecord:
            return PlodSpanRecord(
                value.document_id,
                (),
                (
                    _span("LF", 0, 21, value.text),
                    _span("SF", 23, 26, value.text),
                ),
            )

    detector = FakeDetector({"checkpoint_sha256": "a" * 64})
    resolver = PlodPairingResolver(
        detector=detector, detector_config=PlodConfig(checkpoint_path="missing")
    )
    predictions = tuple(resolver.resolve(document))

    assert len(predictions) == 1
    assert predictions[0].short_form_text == "TNF"
    assert predictions[0].long_form_text == "tumor necrosis factor"
    assert predictions[0].prediction is not None
    assert predictions[0].prediction.score == 1.0
    assert predictions[0].provenance is not None
    assert "short_span_score:0.8" in predictions[0].provenance.transformation_notes
