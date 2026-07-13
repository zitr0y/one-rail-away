"""`ose` command-line entry point: fetch / build / compute pipeline stages."""

import argparse
import logging
from datetime import date
from pathlib import Path

from pipeline import netex
from pipeline.gtfs import feed_validity_window, next_tuesday
from pipeline.sampling import service_week_dates

RAW, GRAPH, OUT = Path("data/raw"), Path("data/graph"), Path("data/out")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ose", description="onestopeurope data pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    b.add_argument("--date", type=date.fromisoformat, default=next_tuesday(date.today()),
                   help="anchor date for each feed's deterministic service week")
    b.add_argument("--single-date", action="store_true",
                   help="build only --date (useful for focused debugging)")
    b.add_argument("--workers", type=int, default=None,
                   help="feed-loading process count (default: one per CPU)")
    c = sub.add_parser("compute")
    c.add_argument("--workers", type=int, default=None, help="process count (default: one per CPU)")
    args = parser.parse_args()

    if args.cmd == "fetch":
        from pipeline.config import load_feeds
        from pipeline.fetch import fetch_all

        fetch_all(load_feeds(Path("feeds.toml")), RAW)
    elif args.cmd == "build":
        from pipeline.build import build

        if args.single_date:
            sample_dates = [args.date]
        else:
            from pipeline.config import load_feeds

            feeds = load_feeds(Path("feeds.toml"))
            feed_sample_dates = {}
            for name, cfg in feeds.items():
                path = RAW / f"{name}.zip"
                if not path.exists():
                    continue
                validity = (
                    netex.feed_validity_window
                    if cfg.format == "netex"
                    else feed_validity_window
                )
                feed_sample_dates[name] = service_week_dates(args.date, validity(path))
            sample_dates = sorted({day for days in feed_sample_dates.values() for day in days})
        build(
            RAW, GRAPH, Path("feeds.toml"), Path("station_aliases.toml"), args.date,
            sample_dates=sample_dates,
            feed_sample_dates=feed_sample_dates if not args.single_date else None,
            workers=args.workers,
        )
    elif args.cmd == "compute":
        from pipeline.compute import compute_all

        compute_all(GRAPH, OUT, args.workers)
