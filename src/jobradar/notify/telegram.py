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
_LINE_LIMIT = 3000  # one pathological line (kilometric tracking URL) must not sink a chunk


class Telegram:
    """Instant pushes for top matches, one digest message per digest run."""

    def __init__(self, cfg: TelegramConfig) -> None:
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = cfg.enabled and bool(self._token and self._chat_id)
        if cfg.enabled and not self.enabled:
            logger.warning("telegram enabled in config but TELEGRAM_BOT_TOKEN/CHAT_ID missing")

    def push(self, listing: Listing, verdict: Verdict, draft_path: str | None = None) -> bool:
        comp = verdict.extracted.comp
        lines = [
            f"<b>{verdict.score} · {html.escape(listing.title)}</b>",
            f"{html.escape(listing.company)} — {html.escape(listing.location)}",
            html.escape(verdict.reason),
        ]
        if comp:
            lines.append(f"💶 {html.escape(comp)}")
        if draft_path:
            lines.append(f"📝 draft ready: {html.escape(draft_path)}")
        lines.append(html.escape(listing.url))
        return self._send("\n".join(lines))

    def digest(self, items: list[StoredListing]) -> bool:
        header = f"<b>jobradar digest — {len(items)} match(es)</b>"
        lines: list[str] = []
        for item in items:
            marker = "⚡ " if item.status == "pushed" else ""
            draft = f"\n    📝 {html.escape(item.draft_path)}" if item.draft_path else ""
            line = (
                f"{marker}<b>{item.score}</b> · "
                f'<a href="{html.escape(item.url, quote=True)}">{html.escape(item.title)}</a>'
                f" · {html.escape(item.company)} · {html.escape(item.location)}\n"
                f"    {html.escape(item.reason or '')}{draft}"
            )
            lines.append(line[:_LINE_LIMIT])

        delivered = True
        chunk = header
        for line in lines:
            if len(chunk) + len(line) + 2 > _MESSAGE_LIMIT:
                delivered = self._send(chunk) and delivered
                chunk = line
            else:
                chunk = f"{chunk}\n\n{line}"
        return self._send(chunk) and delivered

    def _send(self, text: str) -> bool:
        try:
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
        except requests.RequestException as exc:
            # exception text may embed the tokened URL — log the class only
            logger.error("telegram send failed: %s", type(exc).__name__)
            return False
        if not response.ok:
            logger.error("telegram send failed: %s %s", response.status_code, response.text[:200])
            return False
        return True
