from datetime import UTC, datetime
from pathlib import Path

from jobradar.config import JobRadarConfig, RelevanceConfig
from jobradar.drafts import DraftWriter, draft_filename, render_draft, slugify
from jobradar.models import Extracted, Listing, Verdict


def make_config(**drafts: object) -> JobRadarConfig:
    return JobRadarConfig.model_validate(
        {
            "relevance": RelevanceConfig(tier1_signals=("SFCC",)).model_dump(),
            "drafts": drafts,
        }
    )


def listing() -> Listing:
    return Listing(
        source="test",
        title="Senior SFCC Developer (m/w/d)",
        company="Käse & Söhne GmbH",
        location="Berlin",
        url="https://example.com/1",
    )


def verdict() -> Verdict:
    return Verdict(
        score=90,
        tier=1,
        category="sfcc",
        reason="strong match",
        extracted=Extracted(
            comp=None,
            employment_type="permanent",
            work_mode="remote",
            location="Berlin",
            germany_eligible="yes",
            seniority="senior",
            language="de",
        ),
    )


def test_slugify_strips_non_ascii_noise() -> None:
    assert slugify("Käse & Söhne GmbH") == "k-se-s-hne-gmbh"
    assert slugify("///") == "untitled"
    assert len(slugify("x" * 200)) <= 40


def test_draft_filename_is_date_company_title() -> None:
    when = datetime(2026, 7, 31, tzinfo=UTC)
    name = draft_filename(listing(), when)
    assert name.startswith("2026-07-31-k-se-s-hne-gmbh-senior-sfcc")
    assert name.endswith(".md")


def test_render_draft_has_frontmatter_and_body() -> None:
    text = render_draft("Dear team,\nhello.", listing(), verdict(), "claude-opus-5")
    assert text.startswith("---\n")
    assert "score: 90" in text
    assert "url: https://example.com/1" in text
    assert text.rstrip().endswith("hello.")


def test_writer_unavailable_when_disabled() -> None:
    writer = DraftWriter(make_config(enabled=False))
    assert not writer.available
    assert writer.write(listing(), verdict()) is None


def test_writer_unavailable_without_cv(tmp_path: Path) -> None:
    writer = DraftWriter(make_config(enabled=True, cv_path=str(tmp_path / "missing.md")))
    assert not writer.available
