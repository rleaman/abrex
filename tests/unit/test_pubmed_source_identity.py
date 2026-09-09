"""Regressions for source identity and abstract-arm eligibility."""

import pytest

from abrex.literature.parsers import ArticleParseError, parse_pubmed_xml


@pytest.mark.parametrize(
    "abstract", ["", "<Abstract><AbstractText> </AbstractText></Abstract>"]
)
def test_title_does_not_make_an_empty_abstract_eligible(abstract: str) -> None:
    payload = (
        "<PubmedArticle><MedlineCitation><PMID>42</PMID><Article>"
        f"<ArticleTitle>A title</ArticleTitle>{abstract}"
        "</Article></MedlineCitation></PubmedArticle>"
    )
    with pytest.raises(ArticleParseError, match="no non-empty abstract"):
        parse_pubmed_xml(payload, include_title=True)


def test_reference_identifiers_cannot_supply_article_counterpart() -> None:
    payload = """<PubmedArticle><MedlineCitation><PMID>42</PMID><Article>
    <ArticleTitle>Source article</ArticleTitle>
    <Abstract><AbstractText>  True abstract α (TA).  </AbstractText></Abstract>
    </Article></MedlineCitation><PubmedData><ReferenceList><Reference>
    <ArticleIdList><ArticleId IdType="pmc">PMC999</ArticleId></ArticleIdList>
    </Reference></ReferenceList></PubmedData></PubmedArticle>"""
    article = parse_pubmed_xml(payload, include_title=True).article
    assert article.stable_id == "42"
    assert article.pmcid is None
    assert article.sections[1].text == "  True abstract α (TA).  "


def test_primary_counterpart_wins_over_reference_identifiers() -> None:
    payload = """<PubmedArticle><MedlineCitation><PMID>42</PMID><Article>
    <Abstract><AbstractText>Source text.</AbstractText></Abstract></Article>
    </MedlineCitation><PubmedData><ReferenceList><Reference><ArticleIdList>
    <ArticleId IdType="pmc">PMC999</ArticleId></ArticleIdList></Reference>
    </ReferenceList><ArticleIdList><ArticleId IdType="pmc">PMC42</ArticleId>
    </ArticleIdList></PubmedData></PubmedArticle>"""
    assert parse_pubmed_xml(payload).article.pmcid == "PMC42"


def test_batch_response_cannot_silently_drop_an_article() -> None:
    record = (
        "<PubmedArticle><PMID>42</PMID><Abstract>"
        "<AbstractText>Text.</AbstractText></Abstract></PubmedArticle>"
    )
    with pytest.raises(ArticleParseError, match="exactly one"):
        parse_pubmed_xml(f"<PubmedArticleSet>{record}{record}</PubmedArticleSet>")
