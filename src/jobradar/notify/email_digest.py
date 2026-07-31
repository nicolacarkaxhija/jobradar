from __future__ import annotations

import logging
import os
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from jobradar.config import EmailDeliveryConfig
from jobradar.store import StoredListing

logger = logging.getLogger(__name__)


class EmailDigest:
    """Plain-text digest copy over SMTP — same items as the Telegram digest,
    but greppable in an inbox and archivable by mail rules."""

    def __init__(self, cfg: EmailDeliveryConfig) -> None:
        self._host = os.environ.get("SMTP_HOST", "")
        self._port = int(os.environ.get("SMTP_PORT", "465"))
        self._user = os.environ.get("SMTP_USER", "")
        self._password = os.environ.get("SMTP_PASSWORD", "")
        self._to = os.environ.get("DIGEST_EMAIL_TO", "") or self._user
        self.enabled = cfg.enabled and bool(self._host and self._user and self._password)
        if cfg.enabled and not self.enabled:
            logger.warning("email digest enabled in config but SMTP_HOST/USER/PASSWORD missing")

    def digest(self, items: list[StoredListing]) -> bool:
        now = datetime.now(UTC)
        message = EmailMessage()
        message["Subject"] = f"jobradar digest — {len(items)} match(es), {now:%Y-%m-%d}"
        message["From"] = self._user
        message["To"] = self._to

        lines: list[str] = []
        for item in items:
            marker = "[pushed] " if item.status == "pushed" else ""
            lines.append(f"{marker}{item.score} · {item.title} — {item.company} · {item.location}")
            if item.reason:
                lines.append(f"    {item.reason}")
            if item.draft_path:
                lines.append(f"    draft: {item.draft_path}")
            lines.append(f"    {item.url}")
            lines.append("")
        message.set_content("\n".join(lines) or "No matches above threshold.")

        try:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=30) as smtp:
                smtp.login(self._user, self._password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("email digest failed: %s", exc)
            return False
        return True
