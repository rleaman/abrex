from abrex.candidates import Candidate
from abrex.domain import Document, TextSpan
from abrex.evidence import (
    EvidenceAggregationConfig,
    EvidenceLedger,
    evidence_from_candidate,
)


def test_ledger_is_idempotent_and_deduplicates_source_family() -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    candidate = Candidate("d1", TextSpan(23, 26), TextSpan(0, 21), "test")
    positive = evidence_from_candidate(
        document,
        candidate,
        source_family="teacher",
        source_id="ab3p",
        source_version="1",
        polarity="positive",
    )
    duplicate = EvidenceLedger()
    assert duplicate.add(positive) == duplicate.add(positive)
    assert len(duplicate.records) == 1
    duplicate.add(
        evidence_from_candidate(
            document,
            candidate,
            source_family="teacher",
            source_id="other",
            source_version="1",
            polarity="positive",
            weight=0.5,
        )
    )
    assert (
        duplicate.label(
            document,
            candidate.short_form,
            candidate.long_form,
            EvidenceAggregationConfig(),
        ).status
        == "positive"
    )


def test_contradiction_abstains_and_missing_is_not_negative() -> None:
    document = Document("d1", "tumor necrosis factor (TNF)")
    candidate = Candidate("d1", TextSpan(23, 26), TextSpan(0, 21), "test")
    ledger = EvidenceLedger(
        [
            evidence_from_candidate(
                document,
                candidate,
                source_family="a",
                source_id="1",
                source_version="1",
                polarity="positive",
            ),
            evidence_from_candidate(
                document,
                candidate,
                source_family="b",
                source_id="2",
                source_version="1",
                polarity="negative",
            ),
        ]
    )
    label = ledger.label(
        document, candidate.short_form, candidate.long_form, EvidenceAggregationConfig()
    )
    assert label.status == "abstain"
    assert (
        ledger.label(
            document, TextSpan(0, 1), candidate.long_form, EvidenceAggregationConfig()
        ).status
        == "abstain"
    )
