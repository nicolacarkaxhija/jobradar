from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import anthropic

from jobradar.config import LlmSweepConfig, RelevanceConfig, ScoringConfig
from jobradar.models import ExtractedListings, Listing
from jobradar.sources.base import Source

if TYPE_CHECKING:
    from anthropic.types import MessageParam, ToolUnionParam

logger = logging.getLogger(__name__)

_MAX_CONTINUATIONS = 5

_EXTRACT_PROMPT = (
    "These are research notes about job listings found on the web. Extract every "
    "distinct listing that has at least a title and a company or a direct URL. "
    "Use the listing's direct URL when noted. Skip anything the notes flag as "
    "stale, duplicate, or not actually a job listing."
)


class LlmSweep(Source):
    """Coverage backstop: server-side web search hunts listings the APIs miss —
    employer career pages, ATS boards, niche commerce communities. Runs weekly;
    two calls total (one search-capable model turn, one cheap extraction)."""

    name = "llm_sweep"

    def __init__(
        self, cfg: LlmSweepConfig, relevance: RelevanceConfig, scoring: ScoringConfig
    ) -> None:
        super().__init__(max_runs_per_day=1, every_days=cfg.every_days)
        self._cfg = cfg
        self._relevance = relevance
        self._scoring = scoring

    def _sweep_prompt(self) -> str:
        tier1 = ", ".join(self._relevance.tier1_signals)
        tier2 = ", ".join(self._relevance.tier2_signals)
        return (
            f"Find job listings posted within the last {self._cfg.every_days} days that the "
            f"big job boards tend to miss: employer career pages, ATS-hosted postings "
            f"(Greenhouse, Lever, Personio, SmartRecruiters), hiring.cafe, and niche "
            f"commerce/dev communities.\n\n"
            f"Target roles: {tier1} (also acceptable: {tier2}).\n"
            f"Locations: remote positions hireable from Germany/EU, or on-site/hybrid "
            f"anywhere in Europe.\n\n"
            f"For every listing you find, note on its own block: exact title, company, "
            f"location/work mode, the direct posting URL, and 1-2 sentences on "
            f"requirements and stated compensation. Plain notes only, no commentary. "
            f"If you find nothing, reply exactly: NOTHING FOUND"
        )

    def fetch(self) -> list[Listing]:
        client = anthropic.Anthropic()
        tools = cast(
            "list[ToolUnionParam]",
            [
                {
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": self._cfg.max_searches,
                }
            ],
        )
        messages = cast("list[MessageParam]", [{"role": "user", "content": self._sweep_prompt()}])

        response = client.messages.create(
            model=self._cfg.model, max_tokens=16000, tools=tools, messages=messages
        )
        # The server-side search loop can pause after its iteration limit; re-send to resume.
        continuations = 0
        while response.stop_reason == "pause_turn" and continuations < _MAX_CONTINUATIONS:
            messages.append({"role": "assistant", "content": response.content})
            response = client.messages.create(
                model=self._cfg.model, max_tokens=16000, tools=tools, messages=messages
            )
            continuations += 1

        notes = "\n".join(block.text for block in response.content if block.type == "text")
        if not notes.strip() or "NOTHING FOUND" in notes:
            logger.info("llm_sweep: nothing found")
            return []

        extraction = client.messages.parse(
            model=self._scoring.model,
            max_tokens=2048,
            system=_EXTRACT_PROMPT,
            messages=[{"role": "user", "content": notes[:24000]}],
            output_format=ExtractedListings,
        )
        parsed = extraction.parsed_output
        if parsed is None:
            logger.error("llm_sweep: unparseable extraction")
            return []
        return [
            Listing(
                source=self.name,
                title=item.title,
                company=item.company,
                location=item.location,
                url=item.url,
                description=item.snippet,
            )
            for item in parsed.listings
        ]
