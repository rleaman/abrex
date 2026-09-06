"""Unit and contract coverage for the Schwartz--Hearst baseline."""

from __future__ import annotations

import pytest

from abrex.config import ComponentSpec
from abrex.domain import Document
from abrex.resolvers import (
    SCHWARTZ_HEARST_VERSION,
    SchwartzHearstResolver,
    SchwartzHearstResolverConfig,
    create_resolver_executor,
)


def test_standard_definition_preserves_exact_spans() -> None:
    document = Document("d1", "We measured tumor necrosis-factor (TNF) in serum.")
    prediction = tuple(SchwartzHearstResolver().resolve(document))[0]
    assert prediction.short_form_text == "TNF"
    assert prediction.long_form_text == "tumor necrosis-factor"
    assert prediction.short_form is not None
    assert prediction.long_form is not None
    assert document.text_for(prediction.short_form) == "TNF"
    assert document.text_for(prediction.long_form) == "tumor necrosis-factor"


def test_window_rejects_unrelated_prefix_and_reverse_order() -> None:
    document = Document(
        "d1", "A very long unrelated phrase (ABC). (MRI) magnetic resonance imaging"
    )
    assert tuple(SchwartzHearstResolver().resolve(document)) == ()
    assert tuple(SchwartzHearstResolver().resolve(Document("d2", "(AB)"))) == ()
    assert tuple(SchwartzHearstResolver().resolve(Document("d3", "a (AB)"))) == ()


def test_first_short_form_character_must_start_a_long_form_word() -> None:
    assert (
        tuple(SchwartzHearstResolver().resolve(Document("d1", "zz alpha beta (AB)")))[
            0
        ].long_form_text
        == "alpha beta"
    )
    assert (
        tuple(SchwartzHearstResolver().resolve(Document("d2", "xalpha beta (AB)")))
        == ()
    )


def test_default_window_uses_original_schwartz_hearst_bound() -> None:
    document = Document("d1", "one two three four (OF)")
    prediction = tuple(SchwartzHearstResolver().resolve(document))
    assert len(prediction) == 1
    assert prediction[0].long_form_text == "one two three four"
    assert (
        tuple(
            SchwartzHearstResolver().resolve(
                Document("d2", "one two three four five (OF)")
            )
        )
        == ()
    )


def test_explicit_configuration_controls_matching() -> None:
    document = Document("d1", "alpha beta (AB)")
    assert tuple(SchwartzHearstResolver(max_long_form_words=1).resolve(document)) == ()
    assert (
        len(tuple(SchwartzHearstResolver(max_long_form_words=2).resolve(document))) == 1
    )
    assert (
        len(
            tuple(
                SchwartzHearstResolver(ignore_non_alphanumeric=False).resolve(
                    Document("d2", "tumor necrosis-factor (TNF)")
                )
            )
        )
        == 1
    )


def test_short_form_length_and_case_configuration() -> None:
    document = Document("d1", "Alpha Beta (ab) X-ray (x)")
    assert len(tuple(SchwartzHearstResolver().resolve(document))) == 1
    assert tuple(SchwartzHearstResolver(case_sensitive=True).resolve(document)) == ()
    assert (
        tuple(SchwartzHearstResolver(minimum_short_form_length=3).resolve(document))
        == ()
    )


def test_registry_composition_and_metadata() -> None:
    executor = create_resolver_executor(
        ComponentSpec(type="schwartz_hearst", params={})
    )
    assert executor.metadata.key == "schwartz_hearst"
    assert executor.metadata.version == SCHWARTZ_HEARST_VERSION
    result = executor.resolve_document(Document("d1", "alpha beta (AB)"))
    assert result.predictions[0].prediction is not None
    assert result.predictions[0].prediction.component == "schwartz_hearst"


def test_configuration_rejects_unknown_parameters() -> None:
    with pytest.raises(ValueError, match="extra"):
        SchwartzHearstResolverConfig.model_validate({"unknown": True})
