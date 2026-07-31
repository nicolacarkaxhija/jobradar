from __future__ import annotations

from jobradar.config import JobRadarConfig
from jobradar.sources.base import Source


def build_sources(cfg: JobRadarConfig, only: frozenset[str] | None = None) -> list[Source]:
    """Instantiate every enabled source. Imports stay lazy so optional or
    credentialed sources cost nothing when disabled."""
    sources: list[Source] = []
    src = cfg.sources

    if src.arbeitnow.enabled:
        from jobradar.sources.arbeitnow import Arbeitnow

        sources.append(Arbeitnow(src.arbeitnow))
    if src.remotive.enabled:
        from jobradar.sources.remotive import Remotive

        sources.append(Remotive(src.remotive))
    if src.weworkremotely.enabled:
        from jobradar.sources.weworkremotely import WeWorkRemotely

        sources.append(WeWorkRemotely(src.weworkremotely))
    if src.adzuna.enabled:
        from jobradar.sources.adzuna import Adzuna

        sources.append(Adzuna(src.adzuna))
    if src.jooble.enabled:
        from jobradar.sources.jooble import Jooble

        sources.append(Jooble(src.jooble))
    if src.jobspy_indeed.enabled:
        from jobradar.sources.jobspy_indeed import JobspyIndeed

        sources.append(JobspyIndeed(src.jobspy_indeed))
    if src.email_alerts.enabled:
        from jobradar.sources.email_alerts import EmailAlerts

        sources.append(EmailAlerts(src.email_alerts, cfg.scoring))
    if src.jsearch.enabled:
        from jobradar.sources.jsearch import JSearch

        sources.append(JSearch(src.jsearch))
    if src.llm_sweep.enabled:
        from jobradar.sources.llm_sweep import LlmSweep

        sources.append(LlmSweep(src.llm_sweep, cfg.relevance, cfg.scoring))

    if only is not None:
        sources = [s for s in sources if s.name in only]
    return sources
