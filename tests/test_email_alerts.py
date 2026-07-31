from jobradar.sources.email_alerts import domain_allowed, sender_domain


def test_sender_domain_parses_display_name_form() -> None:
    assert sender_domain('"LinkedIn Job Alerts" <jobalerts-noreply@linkedin.com>') == "linkedin.com"
    assert sender_domain("bounce@news.stepstone.de") == "news.stepstone.de"
    assert sender_domain("no-at-sign") == ""


def test_domain_allowlist_covers_subdomains_only() -> None:
    allowed = ("linkedin.com", "stepstone.de")
    assert domain_allowed("linkedin.com", allowed)
    assert domain_allowed("news.stepstone.de", allowed)
    assert not domain_allowed("evillinkedin.com", allowed)  # suffix-spoof must fail
    assert not domain_allowed("linkedin.com.attacker.io", allowed)
    assert not domain_allowed("", allowed)
