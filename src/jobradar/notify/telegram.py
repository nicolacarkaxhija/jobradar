from __future__ import annotations

import html
import logging
import os

import requests

from jobradar.config import TelegramConfig
from jobradar.models import Listing, Verdict
from jobradar.store import StoredListing

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"
_MESSAGE_LIMIT = 3500  # Telegram caps at 4096; leave headroom for tags


class Telegram:
    """Instant pushes for top matches, one digest message per digest run."""

    def __init__(self, cfg: TelegramConfig) -> None:
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = cfg.enabled and bool(self._token and self._chat_id)
        if cfg.enabled and not self.enabled:
            logger.warning("telegram enabled in config but TELEGRAM_BOT_TOKEN/CHAT_ID missing")

    def push(self, listing: Listing, verdict: Verdict) -> None:
        comp = verdict.extracted.comp
        lines = [
            f"<b>{verdict.score} · {html.escape(listing.title)}</b>",
            f"{html.escape(listing.company)} — {html.escape(listing.location)}",
            html.escape(verdict.reason),
        ]
        if comp:
            lines.append(f"💶 {html.escape(comp)}")
        lines.append(html.escape(listing.url))
        self._send("\n".join(lines))

    def digest(self, items: list[StoredListing]) -> None:
        header = f"<b>jobradar digest — {len(items)} match(es)</b>"
        lines: list[str] = []
        for item in items:
            marker = "⚡ " if item.status == "pushed" else ""
            lines.append(
                f"{marker}<b>{item.score}</b> · "
                f'<a href="{html.escape(item.url, quote=True)}">{html.escape(item.title)}</a>'
                f" · {html.escape(item.company)} · {html.escape(item.location)}\n"
                f"    {html.escape(item.reason or '')}"
            )
        chunk = header
        for line in lines:
            if len(chunk) + len(line) + 2 > _MESSAGE_LIMIT:
                self._send(chunk)
                chunk = line
            else:
                chunk = f"{chunk}\n\n{line}"
        self._send(chunk)

    def _send(self, text: str) -> None:
        response = requests.post(
            _API.format(token=self._token),
            json={
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not response.ok:
            logger.error("telegram send failed: %s %s", response.status_code, response.text)
