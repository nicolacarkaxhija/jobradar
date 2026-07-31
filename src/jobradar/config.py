from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Unknown keys are load errors — a typo in config.yaml fails fast, not silently."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileConfig(StrictModel):
    languages: tuple[str, ...] = ("de", "en")


class RelevanceConfig(StrictModel):
    tier1_signals: tuple[str, ...]
    tier2_signals: tuple[str, ...] = ()
    hard_negatives: tuple[str, ...] = ()
    seniority_exclude: tuple[str, ...] = ()


class GeographyConfig(StrictModel):
    office_ok: tuple[str, ...] = ()


class CompensationConfig(StrictModel):
    anchor_permanent_eur: int = 80_000
    anchor_day_rate_eur: int = 650


class PrefilterConfig(StrictModel):
    drop_if_no_signal: bool = True
    drop_if_negative_only: bool = True
    fuzzy_dedupe_threshold: float = 0.85


class ScoringConfig(StrictModel):
    model: str = "claude-haiku-4-5"
    push_threshold: int = 80
    digest_min: int = 50
    tier2_cap: int = 75
    max_description_chars: int = 8000


class ArbeitnowConfig(StrictModel):
    enabled: bool = False
    pages: int = 3
    max_runs_per_day: int | None = None


class RemotiveConfig(StrictModel):
    enabled: bool = False
    search: str = "commerce"
    # Remotive asks for at most 4 polls/day; listings appear with a 24h delay anyway.
    max_runs_per_day: int | None = 4


class WeWorkRemotelyConfig(StrictModel):
    enabled: bool = False
    feeds: tuple[str, ...] = ()
    max_runs_per_day: int | None = None


class AdzunaConfig(StrictModel):
    enabled: bool = False
    countries: tuple[str, ...] = ("de",)
    queries: tuple[str, ...] = ()
    results_per_page: int = 50
    max_runs_per_day: int | None = None


class JoobleConfig(StrictModel):
    enabled: bool = False
    queries: tuple[str, ...] = ()
    location: str = ""
    max_runs_per_day: int | None = None


class JobspyIndeedConfig(StrictModel):
    enabled: bool = False
    country: str = "germany"
    queries: tuple[str, ...] = ()
    results_per_query: int = 40
    hours_old: int = 72
    max_runs_per_day: int | None = None


class EmailAlertsConfig(StrictModel):
    enabled: bool = False
    folder: str = "INBOX"
    max_messages_per_run: int = 25
    max_runs_per_day: int | None = None
    # Anyone who learns the alerts address can mail it; only these sender domains
    # (and their subdomains) are ingested. Empty list = source refuses to run.
    allowed_sender_domains: tuple[str, ...] = ()


class JSearchConfig(StrictModel):
    enabled: bool = False
    queries: tuple[str, ...] = ()
    # Free tier is 200 requests/month — one run per day keeps it inside quota.
    max_runs_per_day: int | None = 1


class LlmSweepConfig(StrictModel):
    """Weekly coverage backstop: an LLM with server-side web search hunts listings
    the aggregator APIs miss (employer career pages, niche boards)."""

    enabled: bool = False
    model: str = "claude-opus-5"  # must support the web_search_20260209 server tool
    every_days: int = 7
    max_searches: int = 8


class SourcesConfig(StrictModel):
    arbeitnow: ArbeitnowConfig = ArbeitnowConfig()
    remotive: RemotiveConfig = RemotiveConfig()
    weworkremotely: WeWorkRemotelyConfig = WeWorkRemotelyConfig()
    adzuna: AdzunaConfig = AdzunaConfig()
    jooble: JoobleConfig = JoobleConfig()
    jobspy_indeed: JobspyIndeedConfig = JobspyIndeedConfig()
    email_alerts: EmailAlertsConfig = EmailAlertsConfig()
    jsearch: JSearchConfig = JSearchConfig()
    llm_sweep: LlmSweepConfig = LlmSweepConfig()


class StorageConfig(StrictModel):
    db_path: str = "data/jobradar.db"
    archive_dir: str = "archive"
    tracking_path: str = "TRACKING.md"


class DraftsConfig(StrictModel):
    """v2: tailored application drafts for pushed matches — review-and-send, never auto-submit."""

    enabled: bool = False
    model: str = "claude-opus-5"
    cv_path: str = "private/cv.md"
    output_dir: str = "drafts"
    max_per_run: int = 5


class TelegramConfig(StrictModel):
    enabled: bool = True


class EmailDeliveryConfig(StrictModel):
    """SMTP digest copy. Credentials via SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD,
    recipient via DIGEST_EMAIL_TO (defaults to SMTP_USER)."""

    enabled: bool = False


class MarkdownArchiveConfig(StrictModel):
    enabled: bool = True


class DeliveryConfig(StrictModel):
    telegram: TelegramConfig = TelegramConfig()
    email: EmailDeliveryConfig = EmailDeliveryConfig()
    markdown_archive: MarkdownArchiveConfig = MarkdownArchiveConfig()


class JobRadarConfig(StrictModel):
    profile: ProfileConfig = ProfileConfig()
    relevance: RelevanceConfig
    geography: GeographyConfig = GeographyConfig()
    compensation: CompensationConfig = CompensationConfig()
    prefilter: PrefilterConfig = PrefilterConfig()
    scoring: ScoringConfig = ScoringConfig()
    sources: SourcesConfig = SourcesConfig()
    storage: StorageConfig = StorageConfig()
    drafts: DraftsConfig = DraftsConfig()
    delivery: DeliveryConfig = DeliveryConfig()

    @classmethod
    def load(cls, path: str | Path) -> JobRadarConfig:
        import yaml

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)
