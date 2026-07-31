from __future__ import annotations

import email
import email.policy
import imaplib
import logging
import os
from email.message import EmailMessage

import anthropic

from jobradar.config import EmailAlertsConfig, ScoringConfig
from jobradar.models import ExtractedListings, Listing
from jobradar.sources.base import Source, html_to_text

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = (
    "This is a job-alert email from a job board, sent to a dedicated alerts inbox. "
    "Extract every distinct job listing it announces. Ignore navigation, footers, "
    "account links, unsubscribe links and 'similar jobs you may like' padding when "
    "it has no title/company. Use the listing's own URL, not tracking-wrapped "
    "unsubscribe or settings URLs, when both are present (tracking-wrapped job "
    "links are fine — they are all we get)."
)


class EmailAlerts(Source):
    """Recycles the job boards' own alert emails (LinkedIn, StepStone, Xing,
    freelancermap Projektalarm, GULP, ...) from a dedicated IMAP inbox.

    Layout-proof by design: instead of one brittle HTML parser per board, a cheap
    LLM call extracts the listings from the email text. This is the ToS-safe path
    for boards that offer no API or RSS and block scraping.
    """

    name = "email_alerts"

    def __init__(self, cfg: EmailAlertsConfig, scoring: ScoringConfig) -> None:
        super().__init__(cfg.max_runs_per_day)
        self._cfg = cfg
        self._model = scoring.model
        self._host = os.environ.get("IMAP_HOST", "")
        self._user = os.environ.get("IMAP_USER", "")
        self._password = os.environ.get("IMAP_PASSWORD", "")

    def fetch(self) -> list[Listing]:
        if not (self._host and self._user and self._password):
            raise RuntimeError("IMAP_HOST / IMAP_USER / IMAP_PASSWORD not set")
        client = anthropic.Anthropic()

        listings: list[Listing] = []
        with imaplib.IMAP4_SSL(self._host) as imap:
            imap.login(self._user, self._password)
            imap.select(self._cfg.folder)
            _, data = imap.search(None, "UNSEEN")
            message_ids = data[0].split()[: self._cfg.max_messages_per_run]
            for message_id in message_ids:
                # Plain RFC822 fetch marks the message \Seen, so it is processed once.
                _, parts = imap.fetch(message_id, "(RFC822)")
                if not parts or not isinstance(parts[0], tuple):
                    continue
                message = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                assert isinstance(message, EmailMessage)
                listings.extend(self._extract(client, message))
        return listings

    def _extract(self, client: anthropic.Anthropic, message: EmailMessage) -> list[Listing]:
        sender = str(message.get("From", ""))
        domain = sender.rsplit("@", 1)[-1].strip("> ").lower() if "@" in sender else "unknown"
        body = _best_body(message)
        if not body:
            return []
        try:
            response = client.messages.parse(
                model=self._model,
                max_tokens=2048,
                system=_EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": f"From: {sender}\n\n{body[:12000]}"}],
                output_format=ExtractedListings,
            )
        except anthropic.APIError as exc:
            logger.error("email extraction failed (%s): %s", domain, exc)
            return []
        parsed = response.parsed_output
        if parsed is None:
            return []
        return [
            Listing(
                source=f"email:{domain}",
                title=item.title,
                company=item.company,
                location=item.location,
                url=item.url,
                description=item.snippet,
            )
            for item in parsed.listings
        ]


def _best_body(message: EmailMessage) -> str:
    plain = message.get_body(preferencelist=("plain",))
    if plain is not None:
        return str(plain.get_content())
    html = message.get_body(preferencelist=("html",))
    if html is not None:
        return html_to_text(str(html.get_content()))
    return ""
