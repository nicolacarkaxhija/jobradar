from jobradar.models import Extracted, Listing, Verdict
from jobradar.store import Store


def listing(title: str, company: str = "Acme", url: str = "") -> Listing:
    return Listing(
        source="test",
        title=title,
        company=company,
        location="Remote",
        url=url or f"https://example.com/{title.replace(' ', '-')}",
    )


def verdict(score: int) -> Verdict:
    return Verdict(
        score=score,
        tier=1,
        category="sfcc",
        reason="test",
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


def test_exact_dedupe_by_id() -> None:
    with Store(":memory:") as store:
        item = listing("SFCC Developer")
        store.add(item, status="new")
        assert store.has(item.id)
        assert not store.has("unknown")


def test_fuzzy_cross_board_duplicate() -> None:
    with Store(":memory:") as store:
        original = listing("Senior SFCC Developer (m/w/d)", url="https://boardA.example/1")
        store.add(original, status="new")
        repost = listing("Senior SFCC Developer m/w/d", url="https://boardB.example/99")
        assert store.find_fuzzy_duplicate(repost, threshold=0.85) == original.id


def test_different_roles_are_not_duplicates() -> None:
    with Store(":memory:") as store:
        store.add(listing("Senior SFCC Developer"), status="new")
        other = listing("Data Engineer", company="Other GmbH")
        assert store.find_fuzzy_duplicate(other, threshold=0.85) is None


def test_digest_selection_and_marking() -> None:
    with Store(":memory:") as store:
        high = listing("High")
        low = listing("Low")
        store.add(high, status="new", verdict=verdict(90))
        store.add(low, status="new", verdict=verdict(30))
        pending = store.pending_digest(min_score=50)
        assert [item.id for item in pending] == [high.id]
        store.mark_digested([high.id])
        assert store.pending_digest(min_score=50) == []


def test_draft_path_roundtrip() -> None:
    with Store(":memory:") as store:
        item = listing("Drafted")
        store.add(item, status="pushed", verdict=verdict(95), draft_path="drafts/x.md")
        pending = store.pending_digest(min_score=50)
        assert pending[0].draft_path == "drafts/x.md"


def test_migration_adds_draft_path_to_old_schema(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE listings (id TEXT PRIMARY KEY, source TEXT NOT NULL,"
        " title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL,"
        " url TEXT NOT NULL, dedupe_key TEXT NOT NULL, posted_at TEXT NOT NULL,"
        " first_seen TEXT NOT NULL, score INTEGER, tier INTEGER, category TEXT,"
        " reason TEXT, extracted TEXT, status TEXT NOT NULL, dup_of TEXT)"
    )
    conn.commit()
    conn.close()

    with Store(db) as store:  # opening migrates in place
        item = listing("Migrated")
        store.add(item, status="new", verdict=verdict(60), draft_path=None)
        assert store.pending_digest(min_score=50)[0].draft_path is None


def test_source_run_quota() -> None:
    with Store(":memory:") as store:
        assert store.runs_today("remotive") == 0
        store.record_run("remotive")
        store.record_run("remotive")
        assert store.runs_today("remotive") == 2
        assert store.runs_today("adzuna") == 0
