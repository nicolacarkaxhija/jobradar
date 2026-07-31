from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_MD_ESCAPE_RE = re.compile(r"([\\`*_\[\]()<>])")


def md_escape(text: str | None) -> str:
    """Untrusted text (listing titles, companies, LLM output) into Markdown-safe inline text."""
    collapsed = _WS_RE.sub(" ", text or "").strip()
    return _MD_ESCAPE_RE.sub(r"\\\1", collapsed)


def md_url(url: str | None) -> str:
    """Untrusted URL into an angle-bracketed Markdown link target that cannot break out."""
    cleaned = _WS_RE.sub("", url or "")
    for char, encoded in (("<", "%3C"), (">", "%3E"), ("(", "%28"), (")", "%29")):
        cleaned = cleaned.replace(char, encoded)
    return f"<{cleaned}>"
