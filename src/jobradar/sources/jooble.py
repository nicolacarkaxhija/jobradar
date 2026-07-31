from __future__ import annotations

import os

import requests

from jobradar.config import JoobleConfig
from jobradar.models import Listing
from jobradar.sources.base import USER_AGENT, Source, html_to_text

_API = "https://jooble.org/api/{key}"


class Jooble(Source):
    """Official Jooble API (free key on request). Snippet-level descriptions."""

    name = "jooble"

    def __init__(self, cfg: JoobleConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg
        self._key = os.environ.get("JOOBLE_API_KEY", "")

    def fetch(self) -> list[Listing]:
        if not self._key:
            raise RuntimeError("JOOBLE_API_KEY not set")
        listings: list[Listing] = []
        for query in self._cfg.queries:
            try:
                response = requests.post(
                    _API.format(key=self._key),
                    json={"keywords": query, "location": self._cfg.location},
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                # the key sits in the URL path; keep it out of logs and tracebacks
                raise RuntimeError(str(exc).replace(self._key, "***")) from None
            for job in response.json().get("jobs", []):
                description = html_to_text(str(job.get("snippet", "")))
                salary = str(job.get("salary", "") or "")
                if salary:
                    description += f"\n[salary: {salary}]"
                job_type = str(job.get("type", "") or "")
                if job_type:
                    description += f"\n[type: {job_type}]"
                listings.append(
                    Listing(
                        source=self.name,
                        title=str(job.get("title", "")),
                        company=str(job.get("company", "")),
                        location=str(job.get("location", "")),
                        url=str(job.get("link", "")),
                        description=description,
                        posted_at=str(job.get("updated", "")),
                    )
                )
        return listings
