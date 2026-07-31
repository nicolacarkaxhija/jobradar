from __future__ import annotations

import re
from dataclasses import dataclass

from jobradar.config import PrefilterConfig, RelevanceConfig
from jobradar.models import Listing


@dataclass(frozen=True, slots=True)
class PrefilterResult:
    keep: bool
    reason: str = ""


def _matches(text: str, needles: tuple[str, ...]) -> list[str]:
    return [n for n in needles if n.lower() in text]


class Prefilter:
    """Free rule-based gate before any LLM call.

    Rules only kill the obvious junk; the semantic SFCC-vs-CRM call is the scorer's job.
    """

    def __init__(self, relevance: RelevanceConfig, rules: PrefilterConfig) -> None:
        self._relevance = relevance
        self._rules = rules
        # word-boundary match: "intern" must not kill "International Team" titles
        self._seniority_patterns = [
            (word, re.compile(rf"\b{re.escape(word.lower())}\b"))
            for word in relevance.seniority_exclude
        ]

    def check(self, listing: Listing) -> PrefilterResult:
        text = listing.text.lower()
        tier1 = _matches(text, self._relevance.tier1_signals)
        tier2 = _matches(text, self._relevance.tier2_signals)
        negatives = _matches(text, self._relevance.hard_negatives)

        if self._rules.drop_if_no_signal and not tier1 and not tier2:
            return PrefilterResult(keep=False, reason="no relevance signal")
        if self._rules.drop_if_negative_only and negatives and not tier1:
            # e.g. a Marketing Cloud listing that only matched "commercetools-adjacent" noise
            return PrefilterResult(
                keep=False, reason=f"negative signals without tier1: {negatives}"
            )

        title = listing.title.lower()
        excluded = [word for word, pattern in self._seniority_patterns if pattern.search(title)]
        if excluded:
            return PrefilterResult(keep=False, reason=f"excluded seniority: {excluded}")

        return PrefilterResult(keep=True)
