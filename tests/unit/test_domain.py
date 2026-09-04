"""Unit tests for the canonical domain schema."""

import math
from typing import Any, cast

import pytest

from abrex.domain import (
    AbbreviationDefinition,
    AnnotationProvenance,
    CorpusRecord,
    Document,
    InvalidAnnotationError,
    InvalidSpanError,
    PredictionMetadata,
    SourceTextSpan,
    SpanValidationError,
    TextSpan,
)


def test_text_span_has_half_open_length_and_allows_zero_length() -> None:
    span = TextSpan(2, 5)
    assert span.length == 3
    assert not span.is_zero_length
    empty = TextSpan(4, 4)
    assert empty.length == 0
    assert empty.is_zero_length


def test_text_span_rejects_negative_and_reversed_coordinates() -> None:
    with pytest.raises(InvalidSpanError, match="non-negative"):
        TextSpan(-1, 2)
    with pytest.raises(InvalidSpanError, match="exceed"):
        TextSpan(3, 2)
    with pytest.raises(TypeError, match="integer"):
        TextSpan(0.0, 2)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="integer"):
        TextSpan(True, 2)
    with pytest.raises(TypeError, match="integer"):
        TextSpan(0, 2.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="string"):
        TextSpan(0, 1).validate_against(1)  # type: ignore[arg-type]


def test_document_validates_unicode_bounds_and_captured_text() -> None:
    document = Document("doc-unicode", "αβ TNF-α is repeated: TNF-α")
    first = TextSpan(3, 6)
    assert document.text_for(first) == "TNF"
    document.validate_span(first, "TNF")
    with pytest.raises(SpanValidationError, match="Text mismatch"):
        document.validate_span(first, "wrong")
    with pytest.raises(SpanValidationError, match="exceeds"):
        document.validate_span(TextSpan(0, len(document.text) + 1))
    with pytest.raises(TypeError, match="span"):
        document.validate_span(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected_text"):
        document.validate_span(TextSpan(0, 1), 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="document_id"):
        Document(" ", "text")
    with pytest.raises(TypeError, match="text"):
        Document("doc", 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="string"):
        Document(1, "text")  # type: ignore[arg-type]


def test_definition_supports_repeated_and_overlapping_spans() -> None:
    document = Document("doc-1", "The ABCD/ABC pair and ABC again")
    first = AbbreviationDefinition(
        document_id=document.document_id,
        short_form=TextSpan(9, 12),
        long_form=TextSpan(4, 8),
        short_form_text="ABC",
        long_form_text="ABCD",
    )
    repeated = AbbreviationDefinition(
        document_id=document.document_id,
        short_form=TextSpan(25, 28),
        long_form=TextSpan(4, 8),
    )
    first.validate_against(document)
    repeated.validate_against(document)
    document.validate_definition(first)
    assert first.short_form != repeated.short_form
    assert document.id == document.document_id


def test_definition_rejects_identity_and_text_errors() -> None:
    document = Document("doc-1", "ABC means alpha beta")
    definition = AbbreviationDefinition(
        "other",
        TextSpan(0, 3),
        TextSpan(10, 15),
        "ABC",
        "wrong",
    )
    with pytest.raises(InvalidAnnotationError, match="does not match"):
        definition.validate_against(document)

    same_document = AbbreviationDefinition(
        "doc-1", TextSpan(0, 3), TextSpan(10, 15), "ABC", "wrong"
    )
    with pytest.raises(SpanValidationError, match="Text mismatch"):
        same_document.validate_against(document)


def test_incomplete_source_annotation_is_explicit_and_not_inferred() -> None:
    source_only_text = SourceTextSpan(text="TNF")
    source_only_coordinates = SourceTextSpan(start=3, end=6)
    assert not source_only_text.has_coordinates
    assert source_only_coordinates.has_coordinates
    assert source_only_text.start is None
    assert source_only_coordinates.text is None
    with pytest.raises(ValueError, match="both be present"):
        SourceTextSpan(start=3)
    with pytest.raises(InvalidSpanError):
        SourceTextSpan(start=8, end=2)
    with pytest.raises(InvalidSpanError):
        SourceTextSpan(start=-1, end=2)
    with pytest.raises(InvalidSpanError, match="non-negative"):
        SourceTextSpan(start=1, end=-1)
    with pytest.raises(TypeError, match="integer"):
        SourceTextSpan(start=1.0, end=2)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="integer"):
        SourceTextSpan(start=1, end=2.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="string"):
        SourceTextSpan(text=1)  # type: ignore[arg-type]


def test_provenance_is_immutable_and_preserves_source_details() -> None:
    provenance = AnnotationProvenance(
        source_corpus="toy",
        source_record_id="record-7",
        source_annotation_id="ann-2",
        original_short_form=SourceTextSpan(text="TNF"),
        original_long_form=SourceTextSpan(3, 19, "tumor necrosis factor"),
        adapter_identity="toy_adapter",
        adapter_version="1.2",
        transformation_notes=("trimmed source marker", "mapped canonical text"),
    )
    assert provenance.source_record_id == "record-7"
    assert provenance.original_long_form is not None
    assert provenance.original_long_form.text == "tumor necrosis factor"
    with pytest.raises((AttributeError, TypeError)):
        provenance.source_corpus = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError, match="tuple"):
        AnnotationProvenance(transformation_notes=cast(Any, ["mutable"]))
    with pytest.raises(TypeError, match="tuple"):
        AnnotationProvenance(transformation_notes=(1,))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="string"):
        AnnotationProvenance(source_corpus=1)  # type: ignore[arg-type]


def test_prediction_metadata_is_separate_and_validates_values() -> None:
    metadata = PredictionMetadata(
        confidence=0.75, score=-2.5, component="toy", component_version="1"
    )
    prediction = AbbreviationDefinition("doc-1", prediction=metadata)
    gold = AbbreviationDefinition("doc-1")
    assert prediction.is_prediction
    assert prediction.confidence == 0.75
    assert not gold.is_prediction
    assert gold.confidence is None
    with pytest.raises(ValueError, match="between 0 and 1"):
        PredictionMetadata(confidence=1.1)
    with pytest.raises(ValueError, match="finite"):
        PredictionMetadata(score=math.inf)
    with pytest.raises(TypeError, match="real number"):
        PredictionMetadata(confidence=True)
    with pytest.raises(TypeError, match="real number"):
        PredictionMetadata(score=True)
    with pytest.raises(TypeError, match="string"):
        PredictionMetadata(component=1)  # type: ignore[arg-type]


def test_corpus_record_normalizes_annotation_sequence_and_validates() -> None:
    document = Document("doc-1", "ABC means alpha")
    annotation = AbbreviationDefinition("doc-1", TextSpan(0, 3), TextSpan(10, 15))
    record = CorpusRecord(
        document=document,
        gold_annotations=[annotation],  # type: ignore[arg-type]
        record_id="source-1",
    )
    assert record.gold_annotations == (annotation,)
    assert record.id == "source-1"
    record.validate()
    assert CorpusRecord(document).id == "doc-1"
    with pytest.raises(InvalidAnnotationError, match="does not match"):
        CorpusRecord(document, (AbbreviationDefinition("other"),))
    with pytest.raises(SpanValidationError, match="exceeds"):
        CorpusRecord(
            document, (AbbreviationDefinition("doc-1", TextSpan(0, 99)),)
        ).validate()
    with pytest.raises(TypeError, match="sequence"):
        CorpusRecord(document, "not annotations")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="document"):
        CorpusRecord(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="contain"):
        CorpusRecord(document, cast(Any, [object()]))
    with pytest.raises(ValueError, match="record_id"):
        CorpusRecord(document, record_id=" ")
    with pytest.raises(TypeError, match="provenance"):
        CorpusRecord(document, provenance=object())  # type: ignore[arg-type]


def test_domain_objects_reject_incompatible_annotation_inputs() -> None:
    with pytest.raises(TypeError, match="document_id"):
        AbbreviationDefinition(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="short_form"):
        AbbreviationDefinition("doc", short_form=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="long_form"):
        AbbreviationDefinition("doc", long_form=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="provenance"):
        AbbreviationDefinition("doc", provenance=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="prediction"):
        AbbreviationDefinition("doc", prediction=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="short_form_text"):
        AbbreviationDefinition("doc", short_form_text=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="long_form_text"):
        AbbreviationDefinition("doc", long_form_text=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="document"):
        AbbreviationDefinition("doc").validate_against(object())  # type: ignore[arg-type]
