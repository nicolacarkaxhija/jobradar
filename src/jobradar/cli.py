from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import cast

from jobradar.calibration import CalibrationSuite, report, run_calibration
from jobradar.config import JobRadarConfig
from jobradar.drafts import DraftWriter
from jobradar.models import APP_STATUSES, AppStatus
from jobradar.pipeline import run
from jobradar.store import Store
from jobradar.tracking import render_tracking


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobradar", description="Job discovery pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="fetch, score and deliver listings")
    run_parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    run_parser.add_argument(
        "--digest", action="store_true", help="also send the digest for everything pending"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="in-memory DB, no notifications, read-only sources, no paid scoring "
        "unless --score-limit is given",
    )
    run_parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="NAME",
        help="run only the named source(s); repeatable",
    )
    run_parser.add_argument(
        "--score-limit", type=int, default=None, help="cap LLM-scored listings this run"
    )

    calibrate_parser = subparsers.add_parser(
        "calibrate", help="score a fixture suite to check the rubric before trusting it"
    )
    calibrate_parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    calibrate_parser.add_argument(
        "--suite", default=None, help="path to a calibration YAML (defaults to the built-in suite)"
    )

    draft_parser = subparsers.add_parser(
        "draft", help="write an application draft for any listing already in the DB"
    )
    draft_parser.add_argument("term", help="listing URL, or an id prefix of at least 8 chars")
    draft_parser.add_argument("--config", default="config.yaml", help="path to config.yaml")

    track_parser = subparsers.add_parser("track", help="record application progress")
    track_parser.add_argument("term", help="listing URL, or an id prefix of at least 8 chars")
    track_parser.add_argument("status", choices=list(APP_STATUSES))
    track_parser.add_argument("--note", default="", help="optional note (interviewer, date, ...)")
    track_parser.add_argument("--config", default="config.yaml", help="path to config.yaml")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if args.command == "track":
        return _track(args)
    if args.command == "calibrate":
        return _calibrate(args)
    if args.command == "draft":
        return _draft(args)

    stats = run(
        config_path=args.config,
        digest=args.digest,
        dry_run=args.dry_run,
        only=frozenset(args.sources) if args.sources else None,
        score_limit=args.score_limit,
    )
    print(stats.summary())
    # any persistently failing source must turn the scheduled workflow red
    return 1 if stats.source_errors else 0


def _calibrate(args: argparse.Namespace) -> int:
    cfg = JobRadarConfig.load(args.config)
    suite = CalibrationSuite.load(args.suite)
    try:
        results = run_calibration(cfg, suite)
    except RuntimeError as exc:  # missing credentials is the expected failure here
        print(exc)
        return 2
    print()
    print(report(results))
    return 0 if all(r.passed for r in results) else 1


def _draft(args: argparse.Namespace) -> int:
    """Drafts are written automatically only for pushed matches; this covers the
    digest-tier listing you decided to apply for anyway."""
    cfg = JobRadarConfig.load(args.config)
    writer = DraftWriter(cfg)
    if not writer.available:
        print(
            "drafts unavailable — check drafts.enabled, the CV at "
            f"{cfg.drafts.cv_path}, and ANTHROPIC_API_KEY"
        )
        return 2
    with Store(cfg.storage.db_path) as store:
        found = store.find(args.term)
        if found is None:
            print(f"no listing matches {args.term!r} (use the URL or an id prefix >= 8 chars)")
            return 2
        listing, verdict = found
        if verdict is None:
            print(f"{listing.title} has no verdict yet — nothing to tailor a draft against")
            return 2
        path = writer.write(listing, verdict, force=True)
        if path is None:
            print("draft generation failed — see the log above")
            return 1
        store.set_draft_path(listing.id, path.as_posix())
    print(f"draft written: {path}")
    return 0


def _track(args: argparse.Namespace) -> int:
    cfg = JobRadarConfig.load(args.config)
    with Store(cfg.storage.db_path) as store:
        item = store.track(args.term, cast(AppStatus, args.status), args.note)
        if item is None:
            print(f"no listing matches {args.term!r} (use the URL or an id prefix >= 8 chars)")
            return 2
        tracked = store.tracked()
    Path(cfg.storage.tracking_path).write_text(render_tracking(tracked), encoding="utf-8")
    print(f"{item.title} @ {item.company} -> {item.app_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
