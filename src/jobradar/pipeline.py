from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from jobradar.config import JobRadarConfig
from jobradar.models import Listing, Verdict
from jobradar.notify.markdown_archive import MarkdownArchive
from jobradar.notify.telegram import Telegram
from jobradar.prefilter import Prefilter
from jobradar.scoring import Scorer
from jobradar.sources import build_sources
from jobradar.store import Store

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunStats:
    fetched: int = 0
    already_seen: int = 0
    dropped: int = 0
    duplicates: int = 0
    scored: int = 0
    pushed: int = 0
    digested: int = 0
    source_errors: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"fetched={self.fetched} seen={self.already_seen} dropped={self.dropped} "
            f"dups={self.duplicates} scored={self.scored} pushed={self.pushed} "
            f"digested={self.digested} errors={len(self.source_errors)}"
        )


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
    prefilter = Prefilter(cfg.relevance, cfg.prefilter)
    scorer = Scorer(cfg)
    telegram = Telegram(cfg.delivery.telegram)
    archive = MarkdownArchive(cfg.delivery.markdown_archive, cfg.storage)
    if dry_run:
        telegram.enabled = False

    with store:
        for source in build_sources(cfg, only=only):
            quota = source.max_runs_per_day
            if quota is not None and store.runs_today(source.name) >= quota:
                logger.info("%s: daily quota (%d) reached, skipping", source.name, quota)
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
                _process(listing, store, prefilter, scorer, telegram, cfg, stats, score_limit)

        if digest:
            items = store.pending_digest(cfg.scoring.digest_min)
            if items:
                if telegram.enabled:
                    telegram.digest(items)
                if archive.enabled and not dry_run:
                    archive.write(items)
                store.mark_digested([item.id for item in items])
                stats.digested = len(items)

    logger.info("run complete: %s", stats.summary())
    return stats


def _process(
    listing: Listing,
    store: Store,
    prefilter: Prefilter,
    scorer: Scorer,
    telegram: Telegram,
    cfg: JobRadarConfig,
    stats: RunStats,
    score_limit: int | None,
) -> None:
    if store.has(listing.id):
        stats.already_seen += 1
        return

    result = prefilter.check(listing)
    if not result.keep:
        store.add(listing, status="dropped", reason=result.reason)
        stats.dropped += 1
        return

    dup_of = store.find_fuzzy_duplicate(listing, cfg.prefilter.fuzzy_dedupe_threshold)
    if dup_of is not None:
        store.add(listing, status="duplicate", dup_of=dup_of)
        stats.duplicates += 1
        return

    verdict: Verdict | None = None
    if scorer.available and (score_limit is None or stats.scored < score_limit):
        verdict = scorer.score(listing)
        if verdict is not None:
            stats.scored += 1
            logger.info(
                "scored %d [%s] %s @ %s — %s",
                verdict.score,
                verdict.category,
                listing.title,
                listing.company,
                verdict.reason,
            )

    pushed = False
    if verdict is not None and verdict.score >= cfg.scoring.push_threshold and telegram.enabled:
        telegram.push(listing, verdict)
        pushed = True
        stats.pushed += 1

    store.add(listing, status="pushed" if pushed else "new", verdict=verdict)
