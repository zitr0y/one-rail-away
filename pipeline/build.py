"""Graph assembly: load every feed, merge stations across feeds, remap trip stop
ids to canonical station ids, validate, and write the graph JSON files consumed
by the rest of the pipeline (`data/graph/stations.json`, `data/graph/trips.json`).
"""

import json
import tomllib
from datetime import date
from pathlib import Path

from pipeline.config import load_feeds
from pipeline.gtfs import load_feed
from pipeline.merge import _dist_m, _norm, merge_stations
from pipeline.models import Station, Trip


def validate(stations: list[Station], trips: list[Trip]) -> list[str]:
    """Human-readable sanity checks over the assembled graph.

    Flags: a station sitting at (0,0) (missing-coordinate default, not a real
    place); a trip whose stop times are non-increasing (arrival before the
    previous departure); two stations within 500m of each other with the same
    normalized name (a merge that should have happened but didn't).
    """
    problems: list[str] = []
    for s in stations:
        if abs(s.lat) < 0.01 and abs(s.lon) < 0.01:
            problems.append(f"station {s.id} ({s.name}) sits at 0,0")
    for t in trips:
        for a, b in zip(t.stops, t.stops[1:]):
            if b.arr < a.dep:
                problems.append(f"trip {t.trip_id} ({t.train}) has non-increasing times")
                break
    for i, a in enumerate(stations):
        for b in stations[i + 1 :]:
            if _norm(a.name) == _norm(b.name) and _dist_m(a.lat, a.lon, b.lat, b.lon) < 500:
                problems.append(f"unmerged duplicate: {a.id} / {b.id} ({a.name})")
    return problems


def build(
    raw_dir: Path,
    graph_dir: Path,
    feeds_path: Path,
    aliases_path: Path | None,
    sample_date: date,
) -> None:
    """Assemble the station/trip graph for `sample_date` from every `<name>.zip`
    present in `raw_dir`, and write it to `graph_dir`.

    Missing zips are skipped with a printed notice (a feed that failed to fetch
    should not abort the whole build). Trips left with fewer than 2 stops after
    remapping (e.g. all-but-one stop dropped by an earlier stage) are dropped.
    Raises SystemExit(1) if `validate` finds any problems in the assembled graph.
    """
    feeds = load_feeds(feeds_path)
    aliases: dict[str, str] = {}
    if aliases_path and aliases_path.exists():
        aliases = tomllib.loads(aliases_path.read_text()).get("aliases", {})

    per_feed = {}
    feed_trips: dict[str, list[Trip]] = {}
    for name, cfg in feeds.items():
        zip_path = raw_dir / f"{name}.zip"
        if not zip_path.exists():
            print(f"skipping {name}: no zip in {raw_dir}")
            continue
        stops, trips = load_feed(zip_path, cfg, sample_date)
        per_feed[name] = (stops, cfg)
        feed_trips[name] = trips
        print(f"{name}: {len(stops)} stops, {len(trips)} long-distance trips")

    stations, mapping = merge_stations(per_feed, aliases)

    all_trips: list[Trip] = []
    for name, trips in feed_trips.items():
        for t in trips:
            for s in t.stops:
                s.station = mapping[(name, s.station)]
            if len(t.stops) >= 2:
                all_trips.append(t)

    problems = validate(stations, all_trips)
    if problems:
        for p in problems:
            print(f"VALIDATION: {p}")
        raise SystemExit(1)

    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "stations.json").write_text(
        json.dumps(
            {
                "sample_date": sample_date.isoformat(),
                "stations": [s.model_dump() for s in stations],
            },
            ensure_ascii=False,
        )
    )
    (graph_dir / "trips.json").write_text(
        json.dumps({"trips": [t.model_dump() for t in all_trips]}, ensure_ascii=False)
    )
    print(f"graph: {len(stations)} stations, {len(all_trips)} trips -> {graph_dir}")
