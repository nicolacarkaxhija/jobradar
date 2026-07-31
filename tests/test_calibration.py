from jobradar.calibration import CalibrationSuite, CaseResult, report
from jobradar.models import Extracted, Verdict


def verdict(score: int, category: str = "sfcc") -> Verdict:
    return Verdict(
        score=score,
        tier=1,
        category=category,  # type: ignore[arg-type]
        reason="test",
        extracted=Extracted(
            comp=None,
            employment_type="permanent",
            work_mode="remote",
            location="Remote",
            germany_eligible="yes",
            seniority="senior",
            language="en",
        ),
    )


def test_builtin_suite_loads_and_is_coherent() -> None:
    suite = CalibrationSuite.load()
    assert len(suite.cases) >= 10
    names = [case.name for case in suite.cases]
    assert len(names) == len(set(names)), "case names must be unique"
    for case in suite.cases:
        assert 0 <= case.min_score < case.max_score <= 100, case.name
        assert case.why, f"{case.name} must document what it guards"
        assert case.description.strip(), case.name


def test_suite_covers_the_decisive_scenarios() -> None:
    names = {case.name for case in CalibrationSuite.load().cases}
    # the failures that would actually hurt: CRM noise getting through, and
    # untrusted listing text steering the grader
    assert "crm-mislabel-apex" in names
    assert "prompt-injection" in names
    assert "composable-tier2-capped" in names


def test_case_passes_inside_band_and_category() -> None:
    case = CalibrationSuite.load().cases[0]
    result = CaseResult(case=case, verdict=verdict(case.min_score))
    assert result.score_ok and result.category_ok and result.passed


def test_case_fails_outside_band() -> None:
    case = CalibrationSuite.load().cases[0]
    result = CaseResult(case=case, verdict=verdict(case.min_score - 1))
    assert not result.score_ok and not result.passed
    assert "FAIL" in result.summary()


def test_case_fails_on_wrong_category() -> None:
    case = next(c for c in CalibrationSuite.load().cases if c.categories)
    result = CaseResult(case=case, verdict=verdict(case.min_score, category="crm_mislabel"))
    assert result.score_ok and not result.category_ok and not result.passed


def test_missing_verdict_is_a_failure() -> None:
    case = CalibrationSuite.load().cases[0]
    result = CaseResult(case=case, verdict=None)
    assert not result.passed
    assert "ERROR" in result.summary()


def test_report_lists_failures_with_rationale() -> None:
    cases = CalibrationSuite.load().cases[:2]
    results = [
        CaseResult(case=cases[0], verdict=verdict(cases[0].min_score)),
        CaseResult(case=cases[1], verdict=verdict(101)),
    ]
    text = report(results)
    assert "1/2 cases within their expected band" in text
    assert cases[1].why in text
