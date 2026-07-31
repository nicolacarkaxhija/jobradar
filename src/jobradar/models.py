from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

ListingStatus = Literal["new", "pushed", "digested", "dropped", "duplicate"]

_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")


def normalize(text: str) -> str:
    return _NORMALIZE_RE.sub(" ", (text or "").lower()).strip()


@dataclass(frozen=True, slots=True)
class Listing:
    """A raw job listing as fetched from a source, before scoring."""

    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_at: str = ""

    @property
    def id(self) -> str:
        # URL is the primary identity; title+company for sources without stable URLs
        key = self.url or f"{normalize(self.title)}|{normalize(self.company)}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    @property
    def dedupe_key(self) -> str:
        return f"{normalize(self.title)}|{normalize(self.company)}"

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.company}\n{self.location}\n{self.description}"


class ExtractedListing(BaseModel):
    """One listing pulled out of unstructured text (alert emails, web-sweep notes)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    company: str
    location: str
    url: str
    snippet: str


class ExtractedListings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    listings: tuple[ExtractedListing, ...]


class Extracted(BaseModel):
    """Structured facts the scorer pulls out of a listing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comp: str | None
    employment_type: Literal["permanent", "contract", "unclear"]
    work_mode: Literal["remote", "hybrid", "onsite", "unclear"]
    location: str
    germany_eligible: Literal["yes", "no", "unclear"]
    seniority: str
    language: Literal["de", "en", "other"]


class Verdict(BaseModel):
    """The scorer's judgement of one listing against the rubric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: int
    tier: Literal[1, 2] | None
    category: Literal["sfcc", "composable", "crm_mislabel", "other"]
    reason: str
    extracted: Extracted
