# jobradar

Config-driven job discovery: aggregates listings from job APIs, RSS and the boards' own
alert emails (IMAP), prefilters with free keyword rules, dedupes cross-board, scores
survivors against a personal rubric with a cheap LLM (strict schema-validated JSON), and
delivers via Telegram push, daily digest and a Markdown archive. The engine (this repo) is
public and generic; personal config, SQLite state and workflows live in the private
`jobradar-data` repo (two-repo setup, see README).

## Run

```
pip install -e ".[dev]"      # add ,jobspy inside the brackets for Indeed via python-jobspy
jobradar run --config templates/data-repo/config.yaml --dry-run --source arbeitnow --source remotive
jobradar calibrate --config config.yaml    # rubric regression test, costs a few cents
```

## Test

```
pytest
ruff format --check src tests
ruff check src tests
mypy src                     # strict
```

## Conventions

- Python >= 3.11 (pyproject; CI pins 3.11). src layout, strict mypy, ruff line-length 100.

## Gotchas

- `ANTHROPIC_API_KEY` is needed for scoring; `--score-limit 5` caps spend while testing.
- Config is strictly validated — unknown keys fail at load.
