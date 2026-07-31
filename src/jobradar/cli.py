from __future__ import annotations

import argparse
import logging
import sys

from jobradar.pipeline import run


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
        help="in-memory DB, no notifications — for local testing",
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
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    stats = run(
        config_path=args.config,
        digest=args.digest,
        dry_run=args.dry_run,
        only=frozenset(args.sources) if args.sources else None,
        score_limit=args.score_limit,
    )
    print(stats.summary())
    return 1 if stats.source_errors and stats.fetched == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
