"""Regression tests for the two state machines hardened after the adversarial review:
scoring retry semantics (a scoreable listing is only persisted with a verdict) and
digest delivery gating (items stay pending until every enabled channel delivered)."""

import pytest

from jobradar.config import (
    EmailDeliveryConfig,
    JobRadarConfig,
    MarkdownArchiveConfig,
    RelevanceConfig,
    StorageConfig,
    TelegramConfig,
)
from jobradar.drafts import DraftWriter
from jobradar.models import Extracted, Listing, Verdict
from jobradar.notify.email_digest import EmailDigest
from jobradar.notify.markdown_archive import MarkdownArchive
from jobradar.notify.telegram import Telegram
from jobradar.pipeline import RunStats, _deliver_digest, _process, _Runtime
from jobradar.prefilter import Prefilter
from jobradar.scoring import Scorer
from jobradar.store import Store


def make_config() -> JobRadarConfig:
    return JobRadarConfig.model_validate(
        {"relevance": RelevanceConfig(tier1_signals=("SFCC",)).model_dump()}
    )


def listing(title: str = "Senior SFCC Developer") -> Listing:
    return Listing(
        source="test",
        title=title,
        company="Acme",
        location="Remote",
        url=f"https://example.com/{title.replace(' ', '-')}",
        description="SFRA cartridges",
    )


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


def make_runtime(
    store: Store, monkeypatch: pytest.MonkeyPatch, score_limit: int | None = None
) -> _Runtime:
    cfg = make_config()
    scorer = Scorer(cfg)
    telegram = Telegram(TelegramConfig(enabled=False))
    drafts = DraftWriter(cfg)
    return _Runtime(
        cfg=cfg,
        store=store,
        prefilter=Prefilter(cfg.relevance, cfg.prefilter),
        scorer=scorer,
        drafts=drafts,
        telegram=telegram,
        stats=RunStats(),
        score_limit=score_limit,
    )


def test_scoring_failure_leaves_listing_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(":memory:") as store:
        rt = make_runtime(store, monkeypatch)
        rt.scorer.available = True
        monkeypatch.setattr(rt.scorer, "score", lambda _l: None)
        item = listing()
        _process(item, rt)
        assert not store.has(item.id)  # left unseen so the next run retries


def test_score_limit_defers_without_persisting(monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(":memory:") as store:
        rt = make_runtime(store, monkeypatch, score_limit=0)
        rt.scorer.available = True

        def boom(_l: Listing) -> Verdict:
            raise AssertionError("score() must not be called past the limit")

        monkeypatch.setattr(rt.scorer, "score", boom)
        item = listing()
        _process(item, rt)
        assert not store.has(item.id)


def test_collect_only_mode_persists_unscored(monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(":memory:") as store:
        rt = make_runtime(store, monkeypatch)
        rt.scorer.available = False  # no credentials: collect-only is deliberate
        item = listing()
        _process(item, rt)
        assert store.has(item.id)
        assert store.pending_digest(min_score=0) == []  # unscored never enters a digest


def test_push_flow_marks_status_pushed(monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(":memory:") as store:
        rt = make_runtime(store, monkeypatch)
        rt.scorer.available = True
        monkeypatch.setattr(rt.scorer, "score", lambda _l: verdict(95))
        rt.telegram.enabled = True
        sent: list[str] = []
        monkeypatch.setattr(rt.telegram, "_send", lambda text: sent.append(text) or True)
        item = listing()
        _process(item, rt)
        assert sent, "expected an instant push"
        pending = store.pending_digest(min_score=50)
        assert pending[0].status == "pushed"
        assert rt.stats.pushed == 1


def make_digest_fixtures(
    tmp_path: object, archive_enabled: bool = False
) -> tuple[Telegram, EmailDigest, MarkdownArchive]:
    telegram = Telegram(TelegramConfig(enabled=False))
    email = EmailDigest(EmailDeliveryConfig(enabled=False))
    storage = StorageConfig(archive_dir=f"{tmp_path}/archive")
    archive = MarkdownArchive(MarkdownArchiveConfig(enabled=archive_enabled), storage)
    return telegram, email, archive


def seeded_store() -> Store:
    store = Store(":memory:")
    store.add(listing(), status="new", verdict=verdict(70))
    return store


def test_digest_failure_leaves_items_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    with seeded_store() as store:
        telegram, email, archive = make_digest_fixtures(tmp_path)
        telegram.enabled = True
        monkeypatch.setattr(telegram, "_send", lambda _t: False)  # e.g. Telegram 429
        stats = RunStats()
        items = store.pending_digest(min_score=50)
        _deliver_digest(items, telegram, email, archive, store, stats, dry_run=False)
        assert stats.digested == 0
        assert store.pending_digest(min_score=50), "failed delivery must stay pending"


def test_digest_success_consumes_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    with seeded_store() as store:
        telegram, email, archive = make_digest_fixtures(tmp_path)
        telegram.enabled = True
        monkeypatch.setattr(telegram, "_send", lambda _t: True)
        stats = RunStats()
        items = store.pending_digest(min_score=50)
        _deliver_digest(items, telegram, email, archive, store, stats, dry_run=False)
        assert stats.digested == 1
        assert store.pending_digest(min_score=50) == []


def test_partial_channel_failure_blocks_consumption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    with seeded_store() as store:
        telegram, email, archive = make_digest_fixtures(tmp_path)
        telegram.enabled = True
        monkeypatch.setattr(telegram, "_send", lambda _t: False)
        email.enabled = True
        monkeypatch.setattr(email, "digest", lambda _i: True)
        stats = RunStats()
        items = store.pending_digest(min_score=50)
        _deliver_digest(items, telegram, email, archive, store, stats, dry_run=False)
        assert stats.digested == 0, "one failed channel must keep items pending"


def test_archive_alone_counts_as_delivery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    with seeded_store() as store:
        telegram, email, archive = make_digest_fixtures(tmp_path, archive_enabled=True)
        stats = RunStats()
        items = store.pending_digest(min_score=50)
        _deliver_digest(items, telegram, email, archive, store, stats, dry_run=False)
        assert stats.digested == 1  # no push channels configured: the archive is the delivery
