from __future__ import annotations

from datetime import UTC, datetime

from jobradar.mdutil import md_escape, md_url
from jobradar.store import TrackedListing

_SECTION_ORDER = ("offer", "interviewing", "applied", "ghosted", "rejected")
_SECTION_TITLES = {
    "offer": "Offer 🎉",
    "interviewing": "Interviewing",
    "applied": "Applied",
    "ghosted": "Ghosted",
    "rejected": "Rejected",
}


def render_tracking(items: list[TrackedListing]) -> str:
    lines = [
        "# Application tracking",
        "",
        f"_Updated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC — "
        f"managed by `jobradar track`, don't edit by hand._",
        "",
    ]
    for status in _SECTION_ORDER:
        section = [item for item in items if item.app_status == status]
        if not section:
            continue
        lines.append(f"## {_SECTION_TITLES[status]} ({len(section)})")
        lines.append("")
        for item in section:
            note = f" — {md_escape(item.app_note)}" if item.app_note else ""
            draft = f" · [draft]({md_url(item.draft_path)})" if item.draft_path else ""
            lines.append(
                f"- [{md_escape(item.title)} — {md_escape(item.company)}]({md_url(item.url)})"
                f" · score {item.score} · {item.app_updated[:10]}{draft}{note}"
            )
        lines.append("")
    if len(lines) == 4:
        lines.append(
            "Nothing tracked yet — `jobradar track <url> applied` after your first application."
        )
        lines.append("")
    return "\n".join(lines)
