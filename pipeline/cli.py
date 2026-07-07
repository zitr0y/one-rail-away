"""`ose` command-line entry point: fetch / build / compute pipeline stages."""

import argparse
from datetime import date
from pathlib import Path

from pipeline.gtfs import next_tuesday

RAW, GRAPH, OUT = Path("data/raw"), Path("data/graph"), Path("data/out")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ose", description="onestopeurope data pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    b.add_argument("--date", type=date.fromisoformat, default=next_tuesday(date.today()))
    sub.add_parser("compute")
    args = parser.parse_args()

    if args.cmd == "fetch":
        from pipeline.config import load_feeds
        from pipeline.fetch import fetch_all

        fetch_all(load_feeds(Path("feeds.toml")), RAW)
    elif args.cmd == "build":
        from pipeline.build import build

        build(RAW, GRAPH, Path("feeds.toml"), Path("station_aliases.toml"), args.date)
    elif args.cmd == "compute":
        from pipeline.compute import compute_all

        compute_all(GRAPH, OUT)
