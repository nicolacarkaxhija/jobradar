from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from jobradar.config import JobRadarConfig
from jobradar.drafts import DraftWriter
from jobradar.models import Listing, Verdict
from jobradar.notify.email_digest import EmailDigest
from jobradar.notify.markdown_archive import MarkdownArchive
from jobradar.notify.telegram import Telegram
from jobradar.prefilter import Prefilter
from jobradar.scoring import Scorer
from jobradar.sources import build_sources
from jobradar.store import Store, StoredListing

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunStats:
    fetched: int = 0
    already_seen: int = 0
    dropped: int = 0
    duplicates: int = 0
    scored: int = 0
    pushed: int = 0
    drafted: int = 0
    digested: int = 0
    source_errors: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"fetched={self.fetched} seen={self.already_seen} dropped={self.dropped} "
            f"dups={self.duplicates} scored={self.scored} pushed={self.pushed} "
            f"drafted={self.drafted} digested={self.digested} errors={len(self.source_errors)}"
        )


@dataclass(slots=True)
class _Runtime:
    cfg: JobRadarConfig
    store: Store
    prefilter: Prefilter
    scorer: Scorer
    drafts: DraftWriter
    telegram: Telegram
    stats: RunStats
    score_limit: int | None


def run(
    config_path: str | Path,
    digest: bool = False,
    dry_run: bool = False,
    only: frozenset[str] | None = None,
    score_limit: int | None = None,
) -> RunStats:
    cfg = JobRadarConfig.load(config_path)
    stats = RunStats()

    store = Store(":memory:" if dry_run else cfg.storage.db_path)
    telegram = Telegram(cfg.delivery.telegram)
    email = EmailDigest(cfg.delivery.email)
    archive = MarkdownArchive(cfg.delivery.markdown_archive, cfg.storage)
    drafts = DraftWriter(cfg)
    if dry_run:
        telegram.enabled = False
        email.enabled = False
        drafts.available = False
        if score_limit is None:
            score_limit = 0  # no unbounded paid scoring against an in-memory DB

    runtime = _Runtime(
        cfg=cfg,
        store=store,
        prefilter=Prefilter(cfg.relevance, cfg.prefilter),
        scorer=Scorer(cfg),
        drafts=drafts,
        telegram=telegram,
        stats=stats,
        score_limit=score_limit,
    )

    with store:
        for source in build_sources(cfg, only=only):
            source.read_only = dry_run  # e.g. don't mark alert emails \Seen from a dry run
            quota = source.max_runs_per_day
            if quota is not None and store.runs_today(source.name) >= quota:
                logger.info("%s: daily quota (%d) reached, skipping", source.name, quota)
                continue
            if source.every_days is not None and not _due(store, source.name, source.every_days):
                logger.info(
                    "%s: ran within the last %d days, skipping", source.name, source.every_days
                )
                continue
            try:
                listings = source.fetch()
            except Exception as exc:  # one broken source must not kill the run
                logger.error("%s: fetch failed: %s", source.name, exc)
                stats.source_errors[source.name] = str(exc)
                continue
            store.record_run(source.name)
            logger.info("%s: %d listings", source.name, len(listings))
            stats.fetched += len(listings)
            for listing in listings:
                _process(listing, runtime)

        if digest:
            items = store.pending_digest(cfg.scoring.digest_min)
            if items:
                _deliver_digest(items, telegram, email, archive, store, stats, dry_run)

    logger.info("run complete: %s", stats.summary())
    return stats


def _deliver_digest(
    items: list[StoredListing],
    telegram: Telegram,
    email: EmailDigest,
    archive: MarkdownArchive,
    store: Store,
    stats: RunStats,
    dry_run: bool,
) -> None:
    delivered = False
    failed = False
    if telegram.enabled:
        ok = telegram.digest(items)
        delivered |= ok
        failed |= not ok
    if email.enabled:
        ok = email.digest(items)
        delivered |= ok
        failed |= not ok
    if archive.enabled and not dry_run:
        archive.write(items)
        # the passive archive only counts as delivery when no push channel is configured
        delivered = delivered or not (telegram.enabled or email.enabled)
    # only consume the queue when every enabled channel actually delivered;
    # a failed channel leaves items pending so the next digest retries them
    if delivered and not failed:
        store.mark_digested([item.id for item in items])
        stats.digested = len(items)
    else:
        logger.error(
            "digest delivery incomplete — leaving %d item(s) pending for retry", len(items)
        )


def _due(store: Store, source_name: str, every_days: int) -> bool:
    last = store.last_run_day(source_name)
    if last is None:
        return True
    elapsed = datetime.now(UTC).date() - date.fromisoformat(last)
    return elapsed.days >= every_days


def _process(listing: Listing, rt: _Runtime) -> None:
    if rt.store.has(listing.id):
        rt.stats.already_seen += 1
        return

    result = rt.prefilter.check(listing)
    if not result.keep:
        rt.store.add(listing, status="dropped", reason=result.reason)
        rt.stats.dropped += 1
        return

    dup_of = rt.store.find_fuzzy_duplicate(listing, rt.cfg.prefilter.fuzzy_dedupe_threshold)
    if dup_of is not None:
        rt.store.add(listing, status="duplicate", dup_of=dup_of)
        rt.stats.duplicates += 1
        return

    verdict: Verdict | None = None
    if rt.scorer.available:
        # A listing eligible for scoring is only persisted WITH a verdict. Stored
        # unscored it would be undeliverable forever (store.has short-circuits and
        # pending_digest needs a score) — so on failure or deferral, leave it
        # unseen and let the next scheduled run retry.
        if rt.score_limit is not None and rt.stats.scored >= rt.score_limit:
            return
        verdict = rt.scorer.score(listing)
        if verdict is None:
            logger.warning("no verdict for %s — left unseen to retry next run", listing.url)
            return
        rt.stats.scored += 1
        logger.info(
            "scored %d [%s] %s @ %s — %s",
            verdict.score,
            verdict.category,
            listing.title,
            listing.company,
            verdict.reason,
        )

    pushed = verdict is not None and verdict.score >= rt.cfg.scoring.push_threshold
    draft_path: str | None = None
    if pushed and verdict is not None:
        path = rt.drafts.write(listing, verdict) if rt.drafts.available else None
        if path is not None:
            draft_path = path.as_posix()
            rt.stats.drafted += 1
        if rt.telegram.enabled:
            rt.telegram.push(listing, verdict, draft_path)
            rt.stats.pushed += 1

    rt.store.add(
        listing,
        status="pushed" if pushed and rt.telegram.enabled else "new",
        verdict=verdict,
        draft_path=draft_path,
    )
