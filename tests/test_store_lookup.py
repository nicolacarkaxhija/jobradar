"""Round-tripping a stored listing back out (for on-demand drafts) and the
per-channel digest delivery ledger added after the second review."""

from jobradar.models import Extracted, Listing, Verdict
from jobradar.store import Store


def listing(title: str = "Senior SFCC Developer") -> Listing:
    return Listing(
        source="test",
        title=title,
        company="Acme",
        location="Berlin",
        url=f"https://example.com/{title.replace(' ', '-')}",
        description="SFRA cartridges and OCAPI integrations",
        posted_at="2026-07-30",
    )


def verdict(score: int = 72) -> Verdict:
    return Verdict(
        score=score,
        tier=1,
        category="sfcc",
        reason="solid match",
        extracted=Extracted(
            comp="85.000 EUR",
            employment_type="permanent",
            work_mode="remote",
            location="Berlin",
            germany_eligible="yes",
            seniority="senior",
            language="de",
        ),
    )


def test_find_roundtrips_listing_and_verdict() -> None:
    with Store(":memory:") as store:
        item = listing()
        store.add(item, status="new", verdict=verdict())
        found = store.find(item.url)
        assert found is not None
        restored, restored_verdict = found
        assert restored.title == item.title
        assert restored.description == item.description  # needed to tailor a draft
        assert restored.posted_at == item.posted_at
        assert restored_verdict is not None
        assert restored_verdict.score == 72
        assert restored_verdict.extracted.language == "de"  # drives draft language


def test_find_by_id_prefix_and_misses() -> None:
    with Store(":memory:") as store:
        item = listing()
        store.add(item, status="new", verdict=verdict())
        assert store.find(item.id[:12]) is not None
        assert store.find("https://example.com/nope") is None
        assert store.find("short") is None


def test_find_returns_none_verdict_for_unscored() -> None:
    with Store(":memory:") as store:
        item = listing("Unscored Role")
        store.add(item, status="new")
        found = store.find(item.url)
        assert found is not None and found[1] is None


def test_set_draft_path_is_visible_in_digest() -> None:
    with Store(":memory:") as store:
        item = listing()
        store.add(item, status="new", verdict=verdict())
        store.set_draft_path(item.id, "drafts/2026-07-31-acme.md")
        assert store.pending_digest(min_score=50)[0].draft_path == "drafts/2026-07-31-acme.md"


def test_delivery_ledger_is_per_channel() -> None:
    with Store(":memory:") as store:
        item = listing()
        store.add(item, status="new", verdict=verdict())
        items = store.pending_digest(min_score=50)

        assert store.undelivered(items, "telegram") == items
        store.mark_delivered([items[0].id], "telegram")
        assert store.undelivered(items, "telegram") == []
        # a failure on one channel must not suppress the others
        assert store.undelivered(items, "email") == items


def test_mark_delivered_is_idempotent() -> None:
    with Store(":memory:") as store:
        item = listing()
        store.add(item, status="new", verdict=verdict())
        items = store.pending_digest(min_score=50)
        store.mark_delivered([items[0].id], "telegram")
        store.mark_delivered([items[0].id], "telegram")  # must not raise on the PK
        assert store.undelivered(items, "telegram") == []
