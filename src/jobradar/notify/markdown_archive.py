from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jobradar.config import MarkdownArchiveConfig, StorageConfig
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
            comp = f" · {item.reason}" if item.reason else ""
            lines.append(
                f"- **{item.score}** [{item.title} — {item.company}]({item.url})"
                f" · {item.location} · `{item.source}`{comp}"
            )
        lines.append("")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
