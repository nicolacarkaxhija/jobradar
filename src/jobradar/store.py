from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from jobradar.models import Listing, ListingStatus, Verdict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT NOT NULL,
    url         TEXT NOT NULL,
    dedupe_key  TEXT NOT NULL,
    posted_at   TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    score       INTEGER,
    tier        INTEGER,
    category    TEXT,
    reason      TEXT,
    extracted   TEXT,
    status      TEXT NOT NULL,
    dup_of      TEXT,
    draft_path  TEXT
);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen);
CREATE TABLE IF NOT EXISTS source_runs (
    day     TEXT NOT NULL,
    source  TEXT NOT NULL,
    runs    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, source)
);
"""


@dataclass(frozen=True, slots=True)
class StoredListing:
    id: str
    source: str
    title: str
    company: str
    location: str
    url: str
    posted_at: str
    first_seen: str
    score: int | None
    tier: int | None
    category: str | None
    reason: str | None
    status: str
    draft_path: str | None


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class Store:
    """SQLite-backed state: seen listings, verdicts, delivery status, source quotas."""

    def __init__(self, path: str | Path) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        # CREATE TABLE IF NOT EXISTS never alters an existing table — patch older DBs here.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(listings)")}
        if "draft_path" not in columns:
            self._conn.execute("ALTER TABLE listings ADD COLUMN draft_path TEXT")
            self._conn.commit()

    def __enter__(self) -> Store:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def has(self, listing_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,)).fetchone()
        return row is not None

    def find_fuzzy_duplicate(
        self, listing: Listing, threshold: float, days: int = 30
    ) -> str | None:
        """Same job cross-posted on another board: near-identical title+company recently seen."""
        cutoff = datetime.now(UTC).strftime(
            "%Y-%m-%d",
        )
        rows: list[tuple[str, str]] = self._conn.execute(
            "SELECT id, dedupe_key FROM listings "
            "WHERE first_seen >= date(?, ?) AND status != 'dropped'",
            (cutoff, f"-{days} days"),
        ).fetchall()
        for listing_id, key in rows:
            if difflib.SequenceMatcher(None, key, listing.dedupe_key).ratio() >= threshold:
                return listing_id
        return None

    def add(
        self,
        listing: Listing,
        status: ListingStatus,
        verdict: Verdict | None = None,
        reason: str | None = None,
        dup_of: str | None = None,
        draft_path: str | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO listings "
            "(id, source, title, company, location, url, dedupe_key, posted_at, first_seen,"
            " score, tier, category, reason, extracted, status, dup_of, draft_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                listing.id,
                listing.source,
                listing.title,
                listing.company,
                listing.location,
                listing.url,
                listing.dedupe_key,
                listing.posted_at,
                _utcnow(),
                verdict.score if verdict else None,
                verdict.tier if verdict else None,
                verdict.category if verdict else None,
                verdict.reason if verdict else reason,
                verdict.extracted.model_dump_json() if verdict else None,
                status,
                dup_of,
                draft_path,
            ),
        )
        self._conn.commit()

    def pending_digest(self, min_score: int) -> list[StoredListing]:
        rows = self._conn.execute(
            "SELECT id, source, title, company, location, url, posted_at, first_seen,"
            " score, tier, category, reason, status, draft_path "
            "FROM listings WHERE status IN ('new', 'pushed') AND score >= ? "
            "ORDER BY score DESC",
            (min_score,),
        ).fetchall()
        return [StoredListing(*row) for row in rows]

    def mark_digested(self, ids: list[str]) -> None:
        self._conn.executemany(
            "UPDATE listings SET status = 'digested' WHERE id = ?", [(i,) for i in ids]
        )
        self._conn.commit()

    def last_run_day(self, source: str) -> str | None:
        row = self._conn.execute(
            "SELECT MAX(day) FROM source_runs WHERE source = ?", (source,)
        ).fetchone()
        return str(row[0]) if row and row[0] else None

    def runs_today(self, source: str) -> int:
        row = self._conn.execute(
            "SELECT runs FROM source_runs WHERE day = ? AND source = ?", (_today(), source)
        ).fetchone()
        return int(row[0]) if row else 0

    def record_run(self, source: str) -> None:
        self._conn.execute(
            "INSERT INTO source_runs (day, source, runs) VALUES (?, ?, 1) "
            "ON CONFLICT(day, source) DO UPDATE SET runs = runs + 1",
            (_today(), source),
        )
        self._conn.commit()
