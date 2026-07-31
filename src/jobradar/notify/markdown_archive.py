from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jobradar.config import MarkdownArchiveConfig, StorageConfig
from jobradar.mdutil import md_escape, md_url
from jobradar.store import StoredListing


class MarkdownArchive:
    """Greppable, versioned digest history — one Markdown file per day,
    committed to the private data repo by the workflow."""

    def __init__(self, cfg: MarkdownArchiveConfig, storage: StorageConfig) -> None:
        self.enabled = cfg.enabled
        self._dir = Path(storage.archive_dir)

    def write(self, items: list[StoredListing]) -> Path:
        now = datetime.now(UTC)
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{now:%Y-%m-%d}.md"
        lines = [f"## Digest {now:%Y-%m-%d %H:%M} UTC", ""]
        for item in items:
            # every field is untrusted (public internet / LLM output) and lands in a
            # GitHub-rendered file — escape so nothing breaks out of the link syntax
            comp = f" · {md_escape(item.reason)}" if item.reason else ""
            lines.append(
                f"- **{item.score}** [{md_escape(item.title)} — {md_escape(item.company)}]"
                f"({md_url(item.url)})"
                f" · {md_escape(item.location)} · `{item.source.replace('`', '')}`{comp}"
            )
        lines.append("")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
