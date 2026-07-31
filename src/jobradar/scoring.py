from __future__ import annotations

import logging
import os

import anthropic

from jobradar.config import JobRadarConfig
from jobradar.models import Listing, Verdict

logger = logging.getLogger(__name__)

_RUBRIC_TEMPLATE = """\
You score job listings for a Salesforce Commerce Cloud (B2C) developer based in
Germany. Score 0-100. Be strict: a wrong high score costs the user attention,
which is the resource this system exists to protect.

## Step 1 — The guillotine (before anything else)

Decide what the role is actually about:

- SFCC B2C Commerce ({tier1}) -> proceed, tier = 1.
- Composable/headless commerce ({tier2}) with no SFCC -> proceed, tier = 2.
  Final score is capped at {tier2_cap}.
- Salesforce PLATFORM work ({negatives}) -> score 0-10, category "crm_mislabel".
  This is the user's #1 noise source. "Salesforce Commerce Cloud" in a keyword
  list next to Marketing Cloud and Service Cloud on a consultancy's
  everything-listing does NOT make it an SFCC role. The question is what the
  person will do all day.
- Mixed roles: score what the majority of the work is; mention the split.
- Anything else -> category "other", score below 30.

## Step 2 — Seniority gate

Junior / intern / Werkstudent / trainee -> score <= 15.
Mid, senior, lead, principal, architect -> no penalty at either end.

## Step 3 — Geography and work mode

- Remote from Germany possible (DE/EU employer, or global employer that hires
  in Germany) -> no penalty. If the listing is global-remote but silent on
  Germany eligibility, subtract 10-15 and set germany_eligible to "unclear".
- Office/hybrid in {office_ok} -> no penalty.
- Office/hybrid anywhere else -> relocation logic:
  - Stated comp meaningfully above the anchors (EUR {anchor_perm} permanent /
    EUR {anchor_day} day rate), adjusted for local cost of living
    (Lisbon != Zuerich != Warsaw) -> mild penalty only (-5 to -15).
  - Comp unstated or at/below anchor -> heavy penalty (-30 to -40). Relocation
    without a stated upside is not interesting.

## Step 4 — Employment type

Permanent and contract/freelance are both in scope. For contract roles, a day
rate below the anchor -> -10 to -20. Never zero out on comp alone.

## Step 5 — Quality signals (small adjustments, +/-10 total)

- Named end client or product company: plus. Vague bodyshop "exciting
  opportunity for our client": minus.
- Listings in German and English are equally fine.

## Output

Fill every field of the schema. "reason" is one sentence shown in a Telegram
digest — make it carry the decision. "comp" is verbatim from the listing or
null if unstated."""


def build_rubric(cfg: JobRadarConfig) -> str:
    return _RUBRIC_TEMPLATE.format(
        tier1=", ".join(cfg.relevance.tier1_signals),
        tier2=", ".join(cfg.relevance.tier2_signals),
        negatives=", ".join(cfg.relevance.hard_negatives),
        tier2_cap=cfg.scoring.tier2_cap,
        office_ok=", ".join(cfg.geography.office_ok),
        anchor_perm=cfg.compensation.anchor_permanent_eur,
        anchor_day=cfg.compensation.anchor_day_rate_eur,
    )


class Scorer:
    """Scores listings against the rubric with a cheap model and strict JSON output."""

    def __init__(self, cfg: JobRadarConfig) -> None:
        self._cfg = cfg
        self._system = build_rubric(cfg)
        self._client: anthropic.Anthropic | None = None
        self.available = bool(
            os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )
        if not self.available:
            logger.warning("no Anthropic credentials found — listings will not be scored")

    def score(self, listing: Listing) -> Verdict | None:
        if not self.available:
            return None
        if self._client is None:
            self._client = anthropic.Anthropic()

        description = listing.description[: self._cfg.scoring.max_description_chars]
        payload = (
            f"Source: {listing.source}\n"
            f"Title: {listing.title}\n"
            f"Company: {listing.company}\n"
            f"Location: {listing.location}\n"
            f"Posted: {listing.posted_at}\n\n"
            f"{description}"
        )
        try:
            response = self._client.messages.parse(
                model=self._cfg.scoring.model,
                max_tokens=1024,
                system=self._system,
                messages=[{"role": "user", "content": payload}],
                output_format=Verdict,
            )
        except anthropic.APIError as exc:
            logger.error("scoring failed for %s: %s", listing.url, exc)
            return None

        verdict = response.parsed_output
        if verdict is None:
            logger.error("unparseable verdict for %s", listing.url)
            return None
        if verdict.tier == 2 and verdict.score > self._cfg.scoring.tier2_cap:
            verdict = verdict.model_copy(update={"score": self._cfg.scoring.tier2_cap})
        return verdict
