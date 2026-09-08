from abrex.candidates import Candidate
from abrex.domain import Document, TextSpan
from abrex.evidence import evidence_from_candidate
from abrex.patterns import (
    PatternInductionConfig,
    extract_template,
    induce_patterns,
    validate_pattern,
)


def test_template_masks_literal_forms_and_induction_requires_distinct_support() -> None:
    first = Document("d1", "The tumor necrosis factor (TNF) increased.")
    second = Document("d2", "The interleukin six (IL6) increased.")
    a = Candidate("d1", TextSpan(27, 30), TextSpan(4, 25), "test")
    b = Candidate("d2", TextSpan(21, 24), TextSpan(4, 19), "test")
    assert "TNF" not in extract_template(first, a.short_form, a.long_form).template
    records = [
        evidence_from_candidate(
            first,
            a,
            source_family="rule",
            source_id="1",
            source_version="1",
            polarity="positive",
        ),
        evidence_from_candidate(
            second,
            b,
            source_family="rule",
            source_id="1",
            source_version="1",
            polarity="positive",
        ),
    ]
    patterns = induce_patterns(
        records, {"d1": first, "d2": second}, PatternInductionConfig()
    )
    assert len(patterns) == 1
    assert patterns[0].status == "promoted"
    assert (
        validate_pattern(patterns[0], records, {"d1": first, "d2": second})[
            "matched_records"
        ]
        == 2
    )
