from __future__ import annotations

import os

import requests

from jobradar.config import AdzunaConfig
from jobradar.models import Listing
from jobradar.sources.base import USER_AGENT, Source

_API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class Adzuna(Source):
    """Official Adzuna API (free key). Descriptions are truncated server-side,
    so the scorer judges on title + snippet for this source."""

    name = "adzuna"

    def __init__(self, cfg: AdzunaConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg
        self._app_id = os.environ.get("ADZUNA_APP_ID", "")
        self._app_key = os.environ.get("ADZUNA_APP_KEY", "")

    def fetch(self) -> list[Listing]:
        if not self._app_id or not self._app_key:
            raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
        listings: list[Listing] = []
        for country in self._cfg.countries:
            for query in self._cfg.queries:
                try:
                    response = requests.get(
                        _API.format(country=country),
                        params={
                            "app_id": self._app_id,
                            "app_key": self._app_key,
                            "what": query,
                            "results_per_page": str(self._cfg.results_per_page),
                            "content-type": "application/json",
                        },
                        headers={"User-Agent": USER_AGENT},
                        timeout=30,
                    )
                    response.raise_for_status()
                except requests.RequestException as exc:
                    # credentials ride in the query string; keep them out of logs
                    message = str(exc).replace(self._app_key, "***").replace(self._app_id, "***")
                    raise RuntimeError(message) from None
                for item in response.json().get("results", []):
                    description = str(item.get("description", ""))
                    salary_min, salary_max = item.get("salary_min"), item.get("salary_max")
                    if salary_min or salary_max:
                        predicted = " (predicted)" if item.get("salary_is_predicted") == "1" else ""
                        description += f"\n[salary: {salary_min}-{salary_max}{predicted}]"
                    listings.append(
                        Listing(
                            source=self.name,
                            title=str(item.get("title", "")),
                            company=str((item.get("company") or {}).get("display_name", "")),
                            location=str((item.get("location") or {}).get("display_name", "")),
                            url=str(item.get("redirect_url", "")),
                            description=description,
                            posted_at=str(item.get("created", "")),
                        )
                    )
        return listings
