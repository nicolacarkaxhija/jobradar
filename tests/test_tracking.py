from jobradar.models import Extracted, Listing, Verdict
from jobradar.store import Store
from jobradar.tracking import render_tracking


def listing(title: str, url: str) -> Listing:
    return Listing(source="test", title=title, company="Acme GmbH", location="Remote", url=url)


def verdict(score: int) -> Verdict:
    return Verdict(
        score=score,
        tier=1,
        category="sfcc",
        reason="match",
        extracted=Extracted(
            comp=None,
            employment_type="permanent",
            work_mode="remote",
            location="Remote",
            germany_eligible="yes",
            seniority="senior",
            language="en",
        ),
    )


def test_track_by_url_and_by_id_prefix() -> None:
    with Store(":memory:") as store:
        item = listing("SFCC Dev", "https://example.com/sfcc-dev")
        store.add(item, status="pushed", verdict=verdict(88))

        tracked = store.track("https://example.com/sfcc-dev", "applied", "via portal")
        assert tracked is not None and tracked.app_status == "applied"

        tracked2 = store.track(item.id[:10], "interviewing", "")
        assert tracked2 is not None and tracked2.app_status == "interviewing"


def test_track_unknown_term_returns_none() -> None:
    with Store(":memory:") as store:
        assert store.track("https://example.com/nope", "applied", "") is None
        assert store.track("short", "applied", "") is None  # id prefixes need >= 8 chars


def test_render_tracking_groups_and_escapes() -> None:
    with Store(":memory:") as store:
        evil = Listing(
            source="test",
            title="SFCC Dev](https://evil.example)",
            company="Acme",
            location="Remote",
            url="https://example.com/x?a=(b)",
        )
        store.add(evil, status="pushed", verdict=verdict(90))
        store.track(evil.url, "applied", "note [with] brackets")
        text = render_tracking(store.tracked())
    assert "## Applied (1)" in text
    assert "](https://evil.example)" not in text.replace("(<https", "(SAFE")  # escaped, not raw
    assert "%28b%29" in text  # parens in URL are encoded


def test_render_tracking_empty_state() -> None:
    assert "Nothing tracked yet" in render_tracking([])
