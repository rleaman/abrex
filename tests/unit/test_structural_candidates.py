from __future__ import annotations

from abrex.candidates import (
    NestedParentheticalCandidateGenerator,
    ReverseOrderCandidateGenerator,
    StructuredRelationCandidateGenerator,
)
from abrex.domain import Document, TextSpan
from abrex.literature.models import (
    ArticleDocument,
    ArticleDocumentProvenance,
    ArticleSectionLocation,
    ArticleStructure,
)


def _article(text: str, structures: tuple[ArticleStructure, ...]) -> ArticleDocument:
    document = Document("article-1", text)
    return ArticleDocument(
        document,
        ArticleDocumentProvenance(
            "article-1", None, None, None, "article", None, None, None, ("body",)
        ),
        (ArticleSectionLocation("body", TextSpan(0, len(text))),),
        structures,
    )


def test_reverse_order_generator_emits_candidate_without_accepting_it() -> None:
    document = Document("d", "(TNF) Tumor necrosis factor; β-catenin (BC)")
    result = ReverseOrderCandidateGenerator().generate(document)
    assert result.candidates[0].construction == "reverse_order"
    assert (
        document.text[
            result.candidates[0].short_form.start : result.candidates[0].short_form.end
        ]
        == "TNF"
    )
    assert result.candidates[0].provenance is not None


def test_nested_generator_is_bounded_and_deterministic() -> None:
    document = Document("d", "Tumor necrosis (factor (TNF))")
    generator = NestedParentheticalCandidateGenerator(maximum_long_form_words=2)
    first = generator.generate(document)
    second = generator.generate(document)
    assert first == second
    assert first.candidates[0].construction == "nested_parenthetical"


def test_structured_generator_maps_table_rows_and_preserves_paths() -> None:
    structures = (
        ArticleStructure(
            "cell-sf", "table-header-cell", "SF", "article/table/tr[1]/th[1]", "table-1"
        ),
        ArticleStructure(
            "cell-lf", "table-cell", "long form", "article/table/tr[1]/td[1]", "table-1"
        ),
    )
    result = StructuredRelationCandidateGenerator().generate_article(
        _article("SF\tlong form", structures)
    )
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.short_form == TextSpan(0, 2)
    assert candidate.long_form == TextSpan(3, 12)
    assert candidate.provenance is not None
    assert (
        "source_path:article/table/tr[1]/th[1]"
        in candidate.provenance.transformation_notes
    )


def test_structured_generator_requires_article_metadata() -> None:
    result = StructuredRelationCandidateGenerator().generate(
        Document("d", "SF long form")
    )
    assert result.candidates == ()
    assert result.diagnostics[0].code == "structure_metadata_required"
