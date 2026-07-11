"""`ose compute`: run reachability from every station and write the per-station
reach files, the station registry (with `has_reach` flags), and run metadata
consumed by the server.

Per-origin work is independent, so it runs on a process pool by default
(workers=1 forces the serial in-process path). Reach files left over from
previous runs are pruned afterwards: the server derives `has_reach` from files
on disk, so a stale file for a renamed canonical id (Konstanz alias,
2026-07-09) would resurrect a dead station in search.
"""

import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from pipeline.capitals import load_capitals
from pipeline.coverage import build_coverage, covered_from_feeds
from pipeline.models import Destination, ReachFile, Station, Trip
from pipeline.raptor import compute_reachability


def _direct_counts(trips: list[Trip], origin: str) -> Counter:
    """Count, per destination, the number of distinct trips that serve `origin`
    and then later serve that destination in stop order (mid-route boarding
    counts; boarding must strictly precede the destination stop)."""
    counts: Counter = Counter()
    for t in trips:
        seen_origin = False
        for s in t.stops:
            if seen_origin:
                counts[s.station] += 1
            if s.station == origin:
                seen_origin = True
    return counts


def _write_reach(
    trips: list[Trip], station_id: str, out_dir: Path, sample_date: str, now: str
) -> int:
    """Compute one origin's reachability and write its reach file.

    Returns the destination count (0 = nothing reachable, no file written)."""
    reach = compute_reachability(trips, station_id)
    if not reach:
        return 0
    directs = _direct_counts(trips, station_id)
    rf = ReachFile(
        origin=station_id,
        computed_at=now,
        sample_date=sample_date,
        destinations=[
            Destination(id=dest, direct_per_day=directs.get(dest, 0), journeys=js)
            for dest, js in sorted(reach.items())
        ],
    )
    (out_dir / f"reach_{station_id}.json").write_text(rf.model_dump_json(by_alias=True))
    return len(reach)


# Worker-process state: each worker parses trips.json once in _worker_init
# instead of the parent pickling the whole trip list for every origin.
_worker_trips: list[Trip] = []


def _worker_init(graph_dir_str: str) -> None:
    global _worker_trips
    raw = json.loads((Path(graph_dir_str) / "trips.json").read_text())
    _worker_trips = [Trip(**t) for t in raw["trips"]]


def _compute_one(args: tuple[str, str, str, str]) -> tuple[str, int]:
    station_id, out_dir_str, sample_date, now = args
    return station_id, _write_reach(_worker_trips, station_id, Path(out_dir_str), sample_date, now)


def compute_all(
    graph_dir: Path,
    out_dir: Path,
    workers: int | None = None,
    feeds_path: Path = Path("feeds.toml"),
) -> None:
    """For each station in the graph, compute reachability and, if any
    destination is reached, write `out_dir/reach_<id>.json`. Always writes
    `out_dir/stations.json` (registry with `has_reach` flags) and
    `out_dir/meta.json` (run metadata, including upstream feed metadata when
    available). Stale reach files from previous runs are deleted.

    `workers` defaults to one per CPU; 1 runs serially in-process."""
    graph = json.loads((graph_dir / "stations.json").read_text())
    sample_date = graph["sample_date"]
    stations = [Station(**s) for s in graph["stations"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    workers = workers or os.process_cpu_count() or 1

    results: dict[str, int] = {}
    if workers == 1:
        trips = [Trip(**t) for t in json.loads((graph_dir / "trips.json").read_text())["trips"]]
        for station in stations:
            results[station.id] = _write_reach(trips, station.id, out_dir, sample_date, now)
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_worker_init, initargs=(str(graph_dir),)
        ) as pool:
            tasks = [(s.id, str(out_dir), sample_date, now) for s in stations]
            for station_id, n in pool.map(_compute_one, tasks, chunksize=8):
                results[station_id] = n

    capital_ids, cap_warnings = load_capitals(
        Path("capitals.toml"), stations
    )
    for w in cap_warnings:
        print(w)

    written: set[str] = set()
    for station in stations:
        n = results[station.id]
        station.n_dest = n
        if n:
            station.has_reach = True
            written.add(f"reach_{station.id}.json")
            print(f"reach_{station.id}.json: {n} destinations")
        if station.id in capital_ids:
            station.is_capital = True

    for path in out_dir.glob("reach_*.json"):
        if path.name not in written:
            path.unlink()
            print(f"pruned stale {path.name}")

    (out_dir / "stations.json").write_text(
        json.dumps({"stations": [s.model_dump() for s in stations]}, ensure_ascii=False)
    )

    fetch_meta_path = Path("data/raw/fetch_meta.json")
    feeds_meta = json.loads(fetch_meta_path.read_text()) if fetch_meta_path.exists() else {}
    (out_dir / "meta.json").write_text(
        json.dumps({"computed_at": now, "sample_date": sample_date, "feeds": feeds_meta})
    )

    covered = covered_from_feeds(feeds_path) if feeds_path.exists() else set()
    reachable = {s.country for s in stations} - covered
    (out_dir / "coverage.json").write_text(
        json.dumps(build_coverage(covered, reachable), ensure_ascii=False)
    )
