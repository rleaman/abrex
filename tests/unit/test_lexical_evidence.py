"""Tests for local lexical candidates and resource evidence features."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from abrex.candidates import Candidate, LexicalResourceCandidateGenerator
from abrex.domain import Document, TextSpan
from abrex.features import LexicalResourceEvidenceFeatureExtractor
from abrex.resources import FrequencyResourceConfig, import_frequency_resource


def _resource(tmp_path: Path, name: str, label: str, value: object) -> Path:
    source = tmp_path / f"{name}.json.gz"
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(value, stream)
    database = tmp_path / f"{name}.sqlite"
    import_frequency_resource(
        FrequencyResourceConfig(
            source_path=source,
            sqlite_path=database,
            source_label=label,
            count_unit="test-count",
            normalization="casefold",
        )
    )
    return database


def test_lexical_generator_requires_both_exact_local_spans(tmp_path: Path) -> None:
    database = _resource(
        tmp_path, "one", "source-one", {"TNF": {"tumor necrosis factor": 4}}
    )
    generator = LexicalResourceCandidateGenerator(
        resource_paths=(database,), maximum_window=100
    )
    result = generator.generate(Document("doc-1", "TNF is tumor necrosis factor."))
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.short_form == TextSpan(0, 3)
    assert candidate.long_form == TextSpan(7, 28)
    assert candidate.provenance is not None
    assert candidate.provenance.source_record_id is not None
    assert candidate.provenance.source_record_id.startswith("source-one:")
    assert "source-one:" in generator.cache_identity

    missing = generator.generate(Document("doc-2", "TNF is common."))
    assert missing.candidates == ()
    assert any(item.code == "resource_pair_not_local" for item in missing.diagnostics)


def test_resource_features_preserve_ambiguity_and_source_agreement(
    tmp_path: Path,
) -> None:
    first = _resource(
        tmp_path, "one", "source-one", {"TNF": {"tumor necrosis factor": 4}}
    )
    second = _resource(
        tmp_path, "two", "source-two", {"TNF": {"tumor necrosis factor receptor": 2}}
    )
    document = Document("doc-1", "TNF is tumor necrosis factor.")
    candidate = Candidate(
        "doc-1", TextSpan(0, 3), TextSpan(7, 28), "resource_local_window"
    )
    extractor = LexicalResourceEvidenceFeatureExtractor(
        resource_paths=(first, second), context_characters=100
    )
    values = extractor.extract(document, candidate)
    assert values["resource_variant_count"] == 2
    assert values["resource_source_count"] == 2
    assert values["resource_source_agreement"] == 1
    assert values["resource_ambiguity_count"] == 2
    assert values["resource_observed_count"] == 6
    assert values["resource_local_pair_match"] == 1
    assert values["resource_contextual_short_count"] == 2
    assert "source-one:" in extractor.cache_identity
    assert "source-two:" in extractor.cache_identity
