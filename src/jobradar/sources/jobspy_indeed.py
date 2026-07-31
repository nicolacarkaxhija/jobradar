from __future__ import annotations

import math
from typing import Any

from jobradar.config import JobspyIndeedConfig
from jobradar.models import Listing
from jobradar.sources.base import Source


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


class JobspyIndeed(Source):
    """Indeed via python-jobspy's mobile-app API path — the one scraping route that
    holds up from datacenter IPs (GitHub Actions runners). Optional dependency:
    pip install jobradar[jobspy]."""

    name = "jobspy_indeed"

    def __init__(self, cfg: JobspyIndeedConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg

    def fetch(self) -> list[Listing]:
        from jobspy import scrape_jobs  # heavy import (pandas) — keep it lazy

        listings: list[Listing] = []
        for query in self._cfg.queries:
            frame = scrape_jobs(
                site_name=["indeed"],
                search_term=query,
                country_indeed=self._cfg.country,
                results_wanted=self._cfg.results_per_query,
                hours_old=self._cfg.hours_old,
            )
            for row in frame.to_dict("records"):
                listings.append(
                    Listing(
                        source=self.name,
                        title=_text(row.get("title")),
                        company=_text(row.get("company")),
                        location=_text(row.get("location")),
                        url=_text(row.get("job_url")),
                        description=_text(row.get("description")),
                        posted_at=_text(row.get("date_posted")),
                    )
                )
        return listings
