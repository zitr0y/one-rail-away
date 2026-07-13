"""`ose` command-line entry point: fetch / build / compute pipeline stages."""

import argparse
import logging
from datetime import date
from pathlib import Path

from pipeline.gtfs import next_tuesday
from pipeline.sampling import service_year_sample_dates

RAW, GRAPH, OUT = Path("data/raw"), Path("data/graph"), Path("data/out")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ose", description="onestopeurope data pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    b.add_argument("--date", type=date.fromisoformat, default=next_tuesday(date.today()),
                   help="anchor year for the deterministic seasonal sample set")
    b.add_argument("--single-date", action="store_true",
                   help="build only --date (useful for focused debugging)")
    c = sub.add_parser("compute")
    c.add_argument("--workers", type=int, default=None, help="process count (default: one per CPU)")
    args = parser.parse_args()

    if args.cmd == "fetch":
        from pipeline.config import load_feeds
        from pipeline.fetch import fetch_all

        fetch_all(load_feeds(Path("feeds.toml")), RAW)
    elif args.cmd == "build":
        from pipeline.build import build

        sample_dates = [args.date] if args.single_date else service_year_sample_dates(args.date)
        build(RAW, GRAPH, Path("feeds.toml"), Path("station_aliases.toml"), args.date,
              sample_dates=sample_dates)
    elif args.cmd == "compute":
        from pipeline.compute import compute_all

        compute_all(GRAPH, OUT, args.workers)
