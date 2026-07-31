# Setup

End-to-end walkthrough from zero to a running pipeline. Everything here happens once.

## 1. Repos

1. Publish this engine repo (public): `jobradar`.
2. Create a **private** data repo, e.g. `jobradar-data`, containing:
   - `config.yaml` — copy from [templates/data-repo/config.yaml](../templates/data-repo/config.yaml) and adjust signals/thresholds
   - `.github/workflows/jobradar.yml` — copy from [templates/data-repo/workflow.yml](../templates/data-repo/workflow.yml)
   - empty `data/` and `archive/` directories (add a `.gitkeep`)

## 2. Dedicated alerts inbox

Create a fresh email address used **only** for job-board alerts (e.g. Gmail).

1. Enable IMAP; create an app password (Gmail: Account → Security → 2FA → App passwords).
2. Subscribe to alerts from that address, **deliberately broad** — the pipeline does the filtering, so "Salesforce Developer" beats "SFCC SFRA Developer":
   - LinkedIn job alerts (broad: "Salesforce Commerce", "Salesforce Developer", "E-Commerce Developer")
   - StepStone daily alerts
   - Xing job alerts
   - freelancermap Projektalarm
   - GULP project alerts
3. Set the `IMAP_*` secrets (step 4). The pipeline reads UNSEEN messages and marks them processed.

## 3. Free API keys

| Service  | Where                                                        | Notes                              |
| -------- | ------------------------------------------------------------ | ---------------------------------- |
| Anthropic | [platform.claude.com](https://platform.claude.com)          | scoring + email extraction, few €/month |
| Adzuna   | [developer.adzuna.com](https://developer.adzuna.com)         | instant, free                      |
| Jooble   | [jooble.org/api/about](https://jooble.org/api/about)         | short request form, free           |
| JSearch  | [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | optional — 200 req/month free, off by default |

## 4. Telegram bot

1. Talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Message your new bot once (bots can't start conversations).
3. Get your chat id: `https://api.telegram.org/bot<TOKEN>/getUpdates` → `message.chat.id`.

## 5. Secrets

In the **private data repo** → Settings → Secrets and variables → Actions:

```
ANTHROPIC_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
IMAP_HOST          (e.g. imap.gmail.com)
IMAP_USER
IMAP_PASSWORD      (the app password)
ADZUNA_APP_ID
ADZUNA_APP_KEY
JOOBLE_API_KEY
JSEARCH_API_KEY    (only if you enable jsearch)
```

## 6. First run

Actions → jobradar → **Run workflow** (tick `digest` to get an immediate summary). Check:

- the run log shows per-source listing counts
- `data/jobradar.db` and (after a digest) `archive/YYYY-MM-DD.md` were committed
- top matches arrive in Telegram

## Tuning

- Too noisy → raise `scoring.push_threshold`, tighten `tier1_signals`.
- Too quiet → lower `digest_min`, broaden alert emails, add tier2 signals.
- Comp anchors, office cities, seniority band: all in `config.yaml`, no code changes.

## Supplements worth keeping open

- [hiring.cafe](https://hiring.cafe) — free, indexes employer career pages directly; strong for direct-employer roles the boards miss. No API, so it stays a manual weekly check.
- Vetted freelance networks (Toptal, A.Team, …) are one-time applications, not feeds — outside the pipeline by design.
