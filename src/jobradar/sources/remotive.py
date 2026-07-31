from __future__ import annotations

import requests

from jobradar.config import RemotiveConfig
from jobradar.models import Listing
from jobradar.sources.base import USER_AGENT, Source, html_to_text

_API = "https://remotive.com/api/remote-jobs"


class Remotive(Source):
    """Remotive public API. Hard limits: <=4 polls/day, listings appear with ~24h delay."""

    name = "remotive"

    def __init__(self, cfg: RemotiveConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg

    def fetch(self) -> list[Listing]:
        response = requests.get(
            _API,
            params={"search": self._cfg.search, "limit": "100"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        listings: list[Listing] = []
        for job in response.json().get("jobs", []):
            description = html_to_text(str(job.get("description", "")))
            salary = str(job.get("salary", "") or "")
            if salary:
                description = f"{description}\n[salary: {salary}]"
            listings.append(
                Listing(
                    source=self.name,
                    title=str(job.get("title", "")),
                    company=str(job.get("company_name", "")),
                    location=str(job.get("candidate_required_location", "")),
                    url=str(job.get("url", "")),
                    description=description,
                    posted_at=str(job.get("publication_date", "")),
                )
            )
        return listings
