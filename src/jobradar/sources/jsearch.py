from __future__ import annotations

import os

import requests

from jobradar.config import JSearchConfig
from jobradar.models import Listing
from jobradar.sources.base import Source

_API = "https://jsearch.p.rapidapi.com/search"


class JSearch(Source):
    """JSearch (RapidAPI) — aggregates Google-for-Jobs, surfacing LinkedIn/Indeed/
    StepStone posts indirectly. Free tier is only 200 requests/month, so this
    source is off by default and quota-limited to one run per day when enabled."""

    name = "jsearch"

    def __init__(self, cfg: JSearchConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg
        self._key = os.environ.get("JSEARCH_API_KEY", "")

    def fetch(self) -> list[Listing]:
        if not self._key:
            raise RuntimeError("JSEARCH_API_KEY not set")
        listings: list[Listing] = []
        for query in self._cfg.queries:
            response = requests.get(
                _API,
                params={"query": query, "num_pages": "1"},
                headers={
                    "X-RapidAPI-Key": self._key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                },
                timeout=30,
            )
            response.raise_for_status()
            for item in response.json().get("data", []):
                city = str(item.get("job_city", "") or "")
                country = str(item.get("job_country", "") or "")
                listings.append(
                    Listing(
                        source=self.name,
                        title=str(item.get("job_title", "")),
                        company=str(item.get("employer_name", "")),
                        location=", ".join(part for part in (city, country) if part),
                        url=str(item.get("job_apply_link", "")),
                        description=str(item.get("job_description", "")),
                        posted_at=str(item.get("job_posted_at_datetime_utc", "") or ""),
                    )
                )
        return listings
