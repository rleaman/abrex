from abrex.domain import AbbreviationDefinition, TextSpan
from abrex.literature import (
    Article,
    ArticleSection,
    MentionLinkConfig,
    WholeArticleSegmenter,
    link_mentions,
)


def test_mentions_use_nearest_preceding_definition_and_report_undefined() -> None:
    article = Article(
        article_id="a1",
        sections=(
            ArticleSection(
                "body", "TNF occurs. Tumor necrosis factor (TNF). TNF occurs."
            ),
        ),
    )
    source = WholeArticleSegmenter().segment(article)[0]
    definitions = (
        AbbreviationDefinition("a1/article", TextSpan(35, 38), TextSpan(12, 33)),
    )
    links = link_mentions(source, definitions)
    assert [link.status for link in links] == ["undefined", "linked", "linked"]
    assert links[0].definition is None
    assert links[2].definition == definitions[0]


def test_section_scope_does_not_cross_section_redefinitions() -> None:
    article = Article(
        article_id="a2",
        sections=(
            ArticleSection("one", "Tumor necrosis factor (TNF). TNF."),
            ArticleSection("two", "Toll-like factor (TNF). TNF."),
        ),
    )
    source = WholeArticleSegmenter().segment(article)[0]
    definitions = (
        AbbreviationDefinition("a2/article", TextSpan(23, 26), TextSpan(0, 21)),
        AbbreviationDefinition("a2/article", TextSpan(53, 56), TextSpan(35, 51)),
    )
    links = link_mentions(source, definitions, MentionLinkConfig(scope="section"))
    assert [link.status for link in links] == ["linked", "linked", "linked", "linked"]
    assert links[-1].definition == definitions[1]
