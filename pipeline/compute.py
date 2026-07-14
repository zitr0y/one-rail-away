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
from pipeline.cities import load_cities
from pipeline.coverage import build_coverage, covered_from_feeds
from pipeline.models import Destination, Frequency, Journey, ReachFile, Station, Trip
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


MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _frequency(
    requested_dates: list[str],
    covered_dates: list[str],
    reaches: dict[str, list[Journey]],
    directs: dict[str, int],
) -> Frequency:
    """Summarize finite sampling evidence without turning it into calendar truth."""
    active_dates = [day for day in covered_dates if day in reaches]
    direct_dates = [day for day in covered_dates if directs.get(day, 0)]
    direct_trips = sum(directs.values())
    months = list(dict.fromkeys(MONTH_NAMES[int(day[5:7]) - 1] for day in active_dates))
    direct_per_active_day = round(direct_trips / len(direct_dates), 1) if direct_dates else None
    # One sampled week cannot prove a timetable.  This is intentionally a rounded
    # rate for the UI's "about N/week" wording, not an asserted service count.
    weekly = (
        round(direct_trips * 7 / len(covered_dates)) if direct_trips and covered_dates else None
    )
    # Too few in-horizon probes to say anything about frequency; otherwise,
    # honest observed presence across the sampled week -- reachable every
    # covered date is "year_round", reachable on only some is "limited". This
    # is deliberately NOT a seasonality classification: a calendar's published
    # span says nothing about whether a service is actually part-year (see
    # backlog AF for real, hand-curated seasonal data).
    availability = (
        "coverage_limited"
        if len(covered_dates) < 3
        else "year_round"
        if len(active_dates) == len(covered_dates)
        else "limited"
    )
    return Frequency(
        requested_sample_days=len(requested_dates),
        sample_days=len(covered_dates),
        available_days=len(active_dates),
        direct_days=len(direct_dates),
        direct_trips=direct_trips,
        direct_per_active_day=direct_per_active_day,
        weekly_direct_estimate=weekly,
        availability=availability,
        active_months=months,
    )


def _aggregate_reach(
    trips_by_date: dict[str, list[Trip]],
    station_id: str,
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] | None = None,
    extra_trips: list[Trip] | None = None,
) -> list[Destination]:
    """Keep each date's routes independent, then select the best tier per dest."""
    sample_dates = list(trips_by_date)
    evidence: dict[str, dict[str, list[Journey]]] = {}
    directs: dict[str, dict[str, int]] = {}
    for day, trips in trips_by_date.items():
        for dest, journeys in compute_reachability(trips, station_id).items():
            evidence.setdefault(dest, {})[day] = journeys
        for dest, n in _direct_counts(trips, station_id).items():
            directs.setdefault(dest, {})[day] = n
    # `extra_trips` is the one extra probe loaded for services absent from
    # every sampled date (see services_absent_from_week / build.py), purely so
    # a destination reached only by them still shows up here. Keyed under a
    # pseudo-date outside `sample_dates` so it never counts as sampled-week
    # evidence: such a destination naturally lands in "coverage_limited" or
    # "limited" below, not a fabricated year-round claim.
    extra_evidence = compute_reachability(extra_trips or [], station_id)
    for dest, journeys in extra_evidence.items():
        evidence.setdefault(dest, {})["extra"] = journeys

    destinations: list[Destination] = []
    for dest in sorted(evidence):
        best_by_trains: dict[int, Journey] = {}
        for journeys in evidence[dest].values():
            for journey in journeys:
                current = best_by_trains.get(journey.trains)
                if current is None or journey.duration_min < current.duration_min:
                    best_by_trains[journey.trains] = journey
        tiers: list[Journey] = []
        for trains in sorted(best_by_trains):
            journey = best_by_trains[trains]
            if not tiers or journey.duration_min < tiers[-1].duration_min:
                tiers.append(journey)
        # A destination can have alternatives that use different feeds.  A date
        # is valid evidence when at least one observed route's complete feed set
        # is inside that feed's selected, published service week. ``covered``
        # distinguishes expired GTFS from no service; ``sampled`` prevents a
        # different feed's week inflating this feed's frequency denominator.
        feed_sets = {
            frozenset(feed for leg in journey.legs for feed in leg.feeds)
            for journeys in evidence[dest].values()
            for journey in journeys
        }
        covered_dates = (
            [
                day
                for day in sample_dates
                if any(
                    all(
                        feed_validity_by_date.get(day, {}).get(feed, {}).get("covered", True)
                        is not False
                        and feed_validity_by_date.get(day, {}).get(feed, {}).get("sampled", True)
                        is not False
                        for feed in feed_set
                    )
                    for feed_set in feed_sets
                )
            ]
            if feed_validity_by_date is not None and feed_sets
            else sample_dates
        )
        freq = _frequency(sample_dates, covered_dates, evidence[dest], directs.get(dest, {}))
        # Legacy field remains present.  On a multi-day run it is the rounded
        # average on observed direct days; consumers should prefer frequency.
        direct_per_day = round(freq.direct_per_active_day or 0)
        destinations.append(
            Destination(
                id=dest,
                direct_per_day=direct_per_day,
                journeys=tiers,
                frequency=freq,
            )
        )
    return destinations


def _write_reach(
    trips_by_date: dict[str, list[Trip]],
    station_id: str,
    out_dir: Path,
    sample_date: str,
    now: str,
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] | None = None,
    extra_trips: list[Trip] | None = None,
) -> int:
    """Compute one origin's reachability and write its reach file.

    Returns the destination count (0 = nothing reachable, no file written)."""
    destinations = _aggregate_reach(
        trips_by_date, station_id, feed_validity_by_date, extra_trips
    )
    if not destinations:
        return 0
    rf = ReachFile(
        origin=station_id,
        computed_at=now,
        sample_date=sample_date,
        destinations=destinations,
    )
    (out_dir / f"reach_{station_id}.json").write_text(rf.model_dump_json(by_alias=True))
    return len(destinations)


# Worker-process state: each worker parses trips.json once in _worker_init
# instead of the parent pickling the whole trip list for every origin.
_worker_trips_by_date: dict[str, list[Trip]] = {}
_worker_feed_validity_by_date: dict[str, dict[str, dict[str, object]]] = {}
_worker_extra_trips: list[Trip] = []


def _worker_init(graph_dir_str: str) -> None:
    global _worker_trips_by_date, _worker_feed_validity_by_date, _worker_extra_trips
    raw = json.loads((Path(graph_dir_str) / "trips.json").read_text())
    by_date = raw.get("trips_by_date") or {"legacy": raw["trips"]}
    _worker_trips_by_date = {day: [Trip(**t) for t in trips] for day, trips in by_date.items()}
    _worker_feed_validity_by_date = raw.get("feed_validity_by_date", {})
    _worker_extra_trips = [Trip(**trip) for trip in raw.get("extra_trips", [])]


def _compute_one(args: tuple[str, str, str, str]) -> tuple[str, int]:
    station_id, out_dir_str, sample_date, now = args
    return station_id, _write_reach(
        _worker_trips_by_date,
        station_id,
        Path(out_dir_str),
        sample_date,
        now,
        _worker_feed_validity_by_date,
        _worker_extra_trips,
    )


def route_counts(trips_path: Path) -> dict[str, int]:
    """Distinct train routes (unordered endpoint pair) calling at each station.

    Counts lines meeting at a station rather than stops made or stations
    reachable, so long stopping trains (PKP TLK) don't inflate hub size the way
    n_dest does. Used for dot sizing on the map.
    """
    payload = json.loads(trips_path.read_text())
    raw = [
        trip for trips in payload.get("trips_by_date", {}).values() for trip in trips
    ] or payload["trips"]
    routes: dict[str, set[frozenset[str]]] = {}
    for t in raw:
        stops = [st["station"] for st in t["stops"]]
        key = frozenset((stops[0], stops[-1]))
        for sid in stops:
            routes.setdefault(sid, set()).add(key)
    return {sid: len(keys) for sid, keys in routes.items()}


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
        raw_trips = json.loads((graph_dir / "trips.json").read_text())
        by_date = raw_trips.get("trips_by_date") or {"legacy": raw_trips["trips"]}
        trips_by_date = {day: [Trip(**t) for t in trips] for day, trips in by_date.items()}
        feed_validity_by_date = raw_trips.get("feed_validity_by_date", {})
        extra_trips = [Trip(**trip) for trip in raw_trips.get("extra_trips", [])]
        for station in stations:
            results[station.id] = _write_reach(
                trips_by_date, station.id, out_dir, sample_date, now, feed_validity_by_date,
                extra_trips,
            )
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_worker_init, initargs=(str(graph_dir),)
        ) as pool:
            tasks = [(s.id, str(out_dir), sample_date, now) for s in stations]
            for station_id, n in pool.map(_compute_one, tasks, chunksize=8):
                results[station_id] = n

    capital_ids, cap_warnings = load_capitals(Path("capitals.toml"), stations)
    for w in cap_warnings:
        print(w)

    city_groups, city_warnings = load_cities(Path("cities.toml"), stations)
    for w in city_warnings:
        print(w)

    n_routes = route_counts(graph_dir / "trips.json")
    written: set[str] = set()
    for station in stations:
        n = results[station.id]
        station.n_dest = n
        station.n_routes = n_routes.get(station.id, 0)
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

    (out_dir / "cities.json").write_text(json.dumps(city_groups, ensure_ascii=False))

    fetch_meta_path = Path("data/raw/fetch_meta.json")
    feeds_meta = json.loads(fetch_meta_path.read_text()) if fetch_meta_path.exists() else {}
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "computed_at": now,
                "sample_date": sample_date,
                "sample_dates": graph.get("sample_dates", [sample_date]),
                "feeds": feeds_meta,
            }
        )
    )

    covered = covered_from_feeds(feeds_path) if feeds_path.exists() else set()
    reachable = {s.country for s in stations} - covered
    (out_dir / "coverage.json").write_text(
        json.dumps(build_coverage(covered, reachable), ensure_ascii=False)
    )
