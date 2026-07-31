from __future__ import annotations

import requests

from jobradar.config import ArbeitnowConfig
from jobradar.models import Listing
from jobradar.sources.base import USER_AGENT, Source

_API = "https://www.arbeitnow.com/api/job-board-api"


class Arbeitnow(Source):
    """Free, keyless DACH-tech job API. No server-side search — the prefilter does the cut."""

    name = "arbeitnow"

    def __init__(self, cfg: ArbeitnowConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg

    def fetch(self) -> list[Listing]:
        from datetime import UTC, datetime

        from jobradar.sources.base import html_to_text

        def posted(value: object) -> str:
            # arbeitnow sends created_at as a unix epoch int
            if isinstance(value, int):
                return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d")
            return str(value or "")

        listings: list[Listing] = []
        for page in range(1, self._cfg.pages + 1):
            response = requests.get(
                _API, params={"page": page}, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            response.raise_for_status()
            for item in response.json().get("data", []):
                listings.append(
                    Listing(
                        source=self.name,
                        title=str(item.get("title", "")),
                        company=str(item.get("company_name", "")),
                        location=str(item.get("location", "")),
                        url=str(item.get("url", "")),
                        description=html_to_text(str(item.get("description", ""))),
                        posted_at=posted(item.get("created_at")),
                    )
                )
        return listings
