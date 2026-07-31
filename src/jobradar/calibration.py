from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from jobradar.config import JobRadarConfig
from jobradar.models import Listing, Verdict
from jobradar.scoring import Scorer

logger = logging.getLogger(__name__)


class CalibrationCase(BaseModel):
    """One listing with the score band the rubric is expected to place it in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    why: str
    min_score: int
    max_score: int
    title: str
    company: str
    location: str
    description: str
    categories: tuple[str, ...] = ()
    language_hint: str = "en"

    def as_listing(self) -> Listing:
        return Listing(
            source="calibration",
            title=self.title,
            company=self.company,
            location=self.location,
            url=f"https://calibration.invalid/{self.name}",
            description=self.description,
        )


class CalibrationSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: tuple[CalibrationCase, ...]

    @classmethod
    def load(cls, path: str | Path | None = None) -> CalibrationSuite:
        import yaml

        if path is None:
            text = (
                resources.files("jobradar.fixtures").joinpath("calibration.yaml").read_text("utf-8")
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        return cls.model_validate(yaml.safe_load(text))


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: CalibrationCase
    verdict: Verdict | None

    @property
    def score_ok(self) -> bool:
        if self.verdict is None:
            return False
        return self.case.min_score <= self.verdict.score <= self.case.max_score

    @property
    def category_ok(self) -> bool:
        if self.verdict is None:
            return False
        return not self.case.categories or self.verdict.category in self.case.categories

    @property
    def passed(self) -> bool:
        return self.score_ok and self.category_ok

    def summary(self) -> str:
        if self.verdict is None:
            return f"ERROR  {self.case.name}: no verdict (scoring failed)"
        mark = "ok  " if self.passed else "FAIL"
        band = f"[{self.case.min_score}-{self.case.max_score}]"
        expected = f" expected {'|'.join(self.case.categories)}" if self.case.categories else ""
        flag = "" if self.category_ok else expected
        return (
            f"{mark} {self.case.name:<32} {self.verdict.score:>3} {band:<9} "
            f"{self.verdict.category:<14}{flag}  {self.verdict.reason}"
        )


def run_calibration(cfg: JobRadarConfig, suite: CalibrationSuite) -> list[CaseResult]:
    scorer = Scorer(cfg)
    if not scorer.available:
        raise RuntimeError("calibration needs ANTHROPIC_API_KEY (or an ant auth profile)")
    results: list[CaseResult] = []
    for case in suite.cases:
        verdict = scorer.score(case.as_listing())
        result = CaseResult(case=case, verdict=verdict)
        logger.info("%s", result.summary())
        results.append(result)
    return results


def report(results: list[CaseResult]) -> str:
    lines = [r.summary() for r in results]
    failures = [r for r in results if not r.passed]
    lines.append("")
    lines.append(f"{len(results) - len(failures)}/{len(results)} cases within their expected band")
    if failures:
        lines.append("")
        lines.append("Out of band — adjust the rubric, the config signals, or the band itself:")
        for failure in failures:
            lines.append(f"  - {failure.case.name}: {failure.case.why}")
    return "\n".join(lines)
