from jobradar.config import PrefilterConfig, RelevanceConfig
from jobradar.models import Listing
from jobradar.prefilter import Prefilter

RELEVANCE = RelevanceConfig(
    tier1_signals=("Salesforce Commerce Cloud", "SFCC", "SFRA", "Demandware"),
    tier2_signals=("commercetools", "composable commerce"),
    hard_negatives=("Marketing Cloud", "Service Cloud", "Apex", "Salesforce Administrator"),
    seniority_exclude=("junior", "intern", "werkstudent"),
)


def make_prefilter() -> Prefilter:
    return Prefilter(RELEVANCE, PrefilterConfig())


def listing(title: str, description: str = "") -> Listing:
    return Listing(
        source="test",
        title=title,
        company="Acme",
        location="Berlin",
        url=f"https://example.com/{title}",
        description=description,
    )


def test_sfcc_listing_passes() -> None:
    result = make_prefilter().check(
        listing("Senior SFCC Developer", "SFRA cartridges, OCAPI integrations")
    )
    assert result.keep


def test_unrelated_listing_dropped() -> None:
    result = make_prefilter().check(listing("PHP Developer", "Laravel and MySQL"))
    assert not result.keep
    assert "no relevance signal" in result.reason


def test_crm_only_listing_dropped_without_tier1() -> None:
    result = make_prefilter().check(
        listing("Salesforce Developer", "Apex, Service Cloud, commercetools migration maybe")
    )
    assert not result.keep


def test_keyword_soup_with_tier1_reaches_scorer() -> None:
    # consultancy listing both SFCC and CRM keywords — the semantic call is the LLM's job
    result = make_prefilter().check(
        listing("Commerce Consultant", "Salesforce Commerce Cloud, Marketing Cloud, Apex")
    )
    assert result.keep


def test_junior_title_dropped() -> None:
    result = make_prefilter().check(listing("Junior SFCC Developer", "SFRA"))
    assert not result.keep
    assert "seniority" in result.reason


def test_tier2_only_listing_passes() -> None:
    result = make_prefilter().check(listing("Backend Engineer", "commercetools platform"))
    assert result.keep
