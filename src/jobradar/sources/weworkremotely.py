from __future__ import annotations

import feedparser

from jobradar.config import WeWorkRemotelyConfig
from jobradar.models import Listing
from jobradar.sources.base import Source, html_to_text


class WeWorkRemotely(Source):
    """Official WWR category RSS feeds. Titles come as 'Company: Role'."""

    name = "weworkremotely"

    def __init__(self, cfg: WeWorkRemotelyConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        for feed_url in self._cfg.feeds:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                raw_title = str(getattr(entry, "title", ""))
                company, _, title = raw_title.partition(":")
                if not title:
                    company, title = "", raw_title
                listings.append(
                    Listing(
                        source=self.name,
                        title=title.strip(),
                        company=company.strip(),
                        location=str(getattr(entry, "region", "Remote")),
                        url=str(getattr(entry, "link", "")),
                        description=html_to_text(str(getattr(entry, "summary", ""))),
                        posted_at=str(getattr(entry, "published", "")),
                    )
                )
        return listings
