"""`ose` command-line entry point: fetch / build / compute pipeline stages."""

import argparse
import logging
from datetime import date
from pathlib import Path

from pipeline import netex
from pipeline.gtfs import feed_validity_window, next_tuesday
from pipeline.sampling import service_week_dates

RAW, GRAPH, OUT = Path("data/raw"), Path("data/graph"), Path("data/out")

STAGES = ["fetch", "build", "compute", "paths"]


def stages_from(start: str) -> list[str]:
    """Stages to run when starting the pipeline at `start`, in canonical order."""
    if start not in STAGES:
        raise ValueError(f"unknown stage: {start}")
    return STAGES[STAGES.index(start):]


def _add_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", type=date.fromisoformat, default=next_tuesday(date.today()),
                        help="anchor date for each feed's deterministic service week")
    parser.add_argument("--single-date", action="store_true",
                        help="build only --date (useful for focused debugging)")


def _add_workers_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workers", type=int, default=None,
                        help="process count (default: one per CPU)")


def _add_paths_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force-download", action="store_true",
                        help="re-download cached OSM extracts")


def _run_fetch(args: argparse.Namespace) -> None:
    from pipeline.config import load_feeds
    from pipeline.fetch import fetch_all

    fetch_all(load_feeds(Path("feeds.toml")), RAW)


def _run_build(args: argparse.Namespace) -> None:
    from pipeline.build import build

    if args.single_date:
        sample_dates = [args.date]
        feed_sample_dates = None
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
        feed_sample_dates=feed_sample_dates,
        workers=args.workers,
    )


def _run_compute(args: argparse.Namespace) -> None:
    from pipeline.compute import compute_all

    compute_all(GRAPH, OUT, args.workers)


def _run_paths(args: argparse.Namespace) -> None:
    from pipeline.railpaths import build_rail_paths

    build_rail_paths(OUT, Path("data/osm"), force_download=args.force_download)


_RUNNERS = {"fetch": _run_fetch, "build": _run_build, "compute": _run_compute, "paths": _run_paths}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ose", description="onestopeurope data pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    _add_build_args(b)
    _add_workers_arg(b)
    c = sub.add_parser("compute")
    _add_workers_arg(c)
    p = sub.add_parser("paths", help="derive real rail geometry for reach-line hops")
    _add_paths_args(p)
    a = sub.add_parser("all", help="run pipeline stages in order, optionally starting mid-pipeline")
    a.add_argument("--from", dest="start", choices=STAGES, default="fetch",
                   help="first stage to run; later stages always follow (default: fetch)")
    _add_build_args(a)
    _add_workers_arg(a)
    _add_paths_args(a)
    args = parser.parse_args()

    if args.cmd == "all":
        for stage in stages_from(args.start):
            logging.info("=== %s ===", stage)
            _RUNNERS[stage](args)
    else:
        _RUNNERS[args.cmd](args)
