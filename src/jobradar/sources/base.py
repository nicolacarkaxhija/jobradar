from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from jobradar.models import Listing

USER_AGENT = "jobradar/0.1 (+https://github.com/nicolacarkaxhija/jobradar)"


class Source(ABC):
    """One place listings come from. Fetch errors are the pipeline's problem, not the source's."""

    name: ClassVar[str]

    def __init__(self, max_runs_per_day: int | None, every_days: int | None = None) -> None:
        self.max_runs_per_day = max_runs_per_day
        self.every_days = every_days
        # dry runs must not mutate external state (e.g. mark alert emails \Seen)
        self.read_only = False

    @abstractmethod
    def fetch(self) -> list[Listing]: ...


def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html or "", "html.parser").get_text(separator=" ", strip=True)
