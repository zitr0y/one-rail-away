"""Graph assembly: load every feed, merge stations across feeds, remap trip stop
ids to canonical station ids, join border-split through-services, validate, and
write the graph JSON files consumed by the rest of the pipeline
(`data/graph/stations.json`, `data/graph/trips.json`).
"""

import json
import logging
import os
import tomllib
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from pipeline import netex
from pipeline.config import FeedConfig, load_feeds
from pipeline.geo import ASSET, assign_countries, load_countries
from pipeline.gtfs import feed_validity_window, load_feed
from pipeline.merge import _dist_m, _norm, merge_stations
from pipeline.models import CountryOverride, Station, Trip
from pipeline.through import join_through_services

logger = logging.getLogger(__name__)


def _load_feed_samples(
    task: tuple[str, Path, FeedConfig, list[date]],
) -> tuple[str, dict[str, tuple[list, list[Trip]]]]:
    """Load all in-coverage probes for one feed in an isolated process.

    One task owns one zip, so workers never share mutable GTFS objects or write
    output.  The parent merges the returned data in feed/date order, which
    keeps graph JSON and console output deterministic.
    """
    name, zip_path, cfg, days = task
    loader = netex.load_feed if cfg.format == "netex" else load_feed
    return name, {
        day.isoformat(): loader(zip_path, cfg, day)
        for day in days
    }


def remap_trips(
    feed_trips: dict[str, list[Trip]], mapping: dict[tuple[str, str], str]
) -> list[Trip]:
    """Remap each trip's feed-local stop ids to canonical station ids.

    A stop whose (feed, stop_id) is absent from `mapping` is an unresolved stub
    the merge stage dropped (a coordinate-less foreign stop that could not be
    matched onto a real station); it is STRIPPED from the trip with a warning.
    Trips left with fewer than 2 stops afterwards are dropped with a warning.
    """
    kept: list[Trip] = []
    for feed, trips in feed_trips.items():
        for t in trips:
            remapped = []
            for s in t.stops:
                canonical = mapping.get((feed, s.station))
                if canonical is None:
                    logger.warning(
                        "stripping unresolved stub stop %s from trip %s (%s) in %s",
                        s.station,
                        t.trip_id,
                        t.train,
                        feed,
                    )
                    continue
                s.station = canonical
                remapped.append(s)
            t.stops = remapped
            if len(t.stops) >= 2:
                kept.append(t)
            else:
                logger.warning(
                    "dropping trip %s (%s) in %s: fewer than 2 stops after stub strip",
                    t.trip_id,
                    t.train,
                    feed,
                )
    return kept


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
    # Preserve the original station-order report order, but only compare pairs
    # that can possibly match.  The former all-pairs loop dominated the serial
    # tail after feed sampling on the production graph.
    stations_by_norm: dict[str, list[Station]] = {}
    for station in stations:
        stations_by_norm.setdefault(_norm(station.name), []).append(station)
    seen_by_norm: dict[str, int] = {}
    for a in stations:
        norm = _norm(a.name)
        peers = stations_by_norm[norm]
        start = seen_by_norm.get(norm, 0) + 1
        for b in peers[start:]:
            if _dist_m(a.lat, a.lon, b.lat, b.lon) < 500:
                problems.append(f"unmerged duplicate: {a.id} / {b.id} ({a.name})")
        seen_by_norm[norm] = start
    return problems


def build(
    raw_dir: Path,
    graph_dir: Path,
    feeds_path: Path,
    aliases_path: Path | None,
    sample_date: date,
    *,
    sample_dates: list[date] | None = None,
    station_names_path: Path | None = None,
    station_countries_path: Path | None = None,
    workers: int | None = None,
) -> None:
    """Assemble station/trip graphs for one or more service dates.

    ``sample_dates=None`` preserves the original one-date API.  Multi-date
    builds share one canonical station registry and serialize independent
    timetable graphs by date; routes must never transfer between dates.

    Missing zips are skipped with a printed notice (a feed that failed to fetch
    should not abort the whole build). Trips left with fewer than 2 stops after
    remapping (e.g. all-but-one stop dropped by an earlier stage) are dropped.
    Raises SystemExit(1) if `validate` finds any problems in the assembled graph.
    """
    feeds = load_feeds(feeds_path)
    aliases: dict[str, str] = {}
    if aliases_path and aliases_path.exists():
        aliases = tomllib.loads(aliases_path.read_text()).get("aliases", {})

    # --- override files: intentionally next to the code, not feeds_path.parent
    # --- deriving from feeds_path.parent silently loaded no overrides at all (2026-07-09).
    if station_countries_path is None:
        station_countries_path = Path(__file__).parent / "station_countries.toml"
    country_overrides: list[CountryOverride] = []
    if station_countries_path.exists():
        raw_country_overrides = tomllib.loads(station_countries_path.read_text()).get(
            "override", []
        )
        country_overrides = [CountryOverride.model_validate(item) for item in raw_country_overrides]

    if station_names_path is None:
        station_names_path = Path(__file__).parent / "station_names.toml"
    name_overrides: dict[str, str] = {}
    if station_names_path.exists():
        name_overrides = tomllib.loads(station_names_path.read_text()).get("names", {})

    dates = sample_dates or [sample_date]
    dates = list(dict.fromkeys(dates))
    primary_day = sample_date if sample_date in dates else dates[0]
    per_feed: dict[str, tuple[list, object]] = {}
    feed_trips_by_date: dict[str, dict[str, list[Trip]]] = {}
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] = {}
    feed_windows = {
        name: (netex.feed_validity_window if cfg.format == "netex" else feed_validity_window)(
            raw_dir / f"{name}.zip"
        )
        for name, cfg in feeds.items()
        if (raw_dir / f"{name}.zip").exists()
    }

    # Filter before calling load_feed: an out-of-horizon date is not a zero
    # service day, and parsing its often very large stop_times.txt just to find
    # that out is both misleading and needlessly expensive.
    feed_days: dict[str, list[date]] = {}
    for name in feeds:
        window = feed_windows.get(name)
        if window is None:
            feed_days[name] = list(dates)
            continue
        usable = [day for day in dates if window[0] <= day.strftime("%Y%m%d") <= window[1]]
        feed_days[name] = usable
        skipped = [day for day in dates if day not in usable]
        if skipped:
            logger.warning(
                "feed %s: skipping %d/%d probes outside published GTFS coverage %s..%s (%s)",
                name,
                len(skipped),
                len(dates),
                window[0],
                window[1],
                ", ".join(day.isoformat() for day in skipped),
            )

    tasks = [
        (name, raw_dir / f"{name}.zip", cfg, feed_days[name])
        for name, cfg in feeds.items()
        if (raw_dir / f"{name}.zip").exists() and feed_days[name]
    ]
    loaded_by_feed: dict[str, dict[str, tuple[list, list[Trip]]]] = {}
    max_workers = min(workers or os.process_cpu_count() or 1, len(tasks))
    if max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            # executor.map preserves task order; the following date loop also
            # makes the final serialized graph independent of worker timing.
            for name, loaded in pool.map(_load_feed_samples, tasks):
                loaded_by_feed[name] = loaded
    else:
        for task in tasks:
            name, loaded = _load_feed_samples(task)
            loaded_by_feed[name] = loaded

    for day in dates:
        feed_trips: dict[str, list[Trip]] = {}
        validity: dict[str, dict[str, object]] = {}
        for name, cfg in feeds.items():
            zip_path = raw_dir / f"{name}.zip"
            if not zip_path.exists():
                if day == dates[0]:
                    print(f"skipping {name}: no zip in {raw_dir}")
                continue
            window = feed_windows[name]
            ymd = day.strftime("%Y%m%d")
            validity[name] = {
                "covered": window is None or window[0] <= ymd <= window[1],
                "start_date": window[0] if window else None,
                "end_date": window[1] if window else None,
            }
            loaded = loaded_by_feed.get(name, {}).get(day.isoformat())
            if loaded is None:
                # This sample is outside this feed's published coverage.  It
                # remains in metadata for downstream frequency denominators,
                # but deliberately contributes no zero-service graph.
                continue
            stops, trips = loaded
            for trip in trips:
                trip.feeds = [name]
            # merge_stations wants each feed's stops once; union all sampled
            # stops by feed-local id so a seasonal-only stop is retained.
            if name not in per_feed:
                per_feed[name] = ([], cfg)
            known = {s.stop_id for s in per_feed[name][0]}
            per_feed[name][0].extend(s for s in stops if s.stop_id not in known)
            feed_trips[name] = trips
            print(f"{day.isoformat()} {name}: {len(stops)} stops, {len(trips)} long-distance trips")
        feed_trips_by_date[day.isoformat()] = feed_trips
        feed_validity_by_date[day.isoformat()] = validity

    stations, mapping = merge_stations(per_feed, aliases)
    for line in assign_countries(stations, load_countries(ASSET), country_overrides):
        print(f"country: {line}")
    trips_by_date = {
        day: join_through_services(remap_trips(feed_trips, mapping))
        for day, feed_trips in feed_trips_by_date.items()
    }
    all_trips = [trip for trips in trips_by_date.values() for trip in trips]

    # Country overrides are coordinate-keyed; unmatched entries already warn in
    # assign_countries. Display-name overrides remain id-keyed and stale ids abort.
    station_ids = {s.id for s in stations}
    stale = [
        f"station_names.toml: stale key {sid!r}" for sid in name_overrides if sid not in station_ids
    ]
    if stale:
        for msg in stale:
            print(f"OVERRIDE STALE: {msg}")
        raise SystemExit(1)

    # Apply display-name overrides (after merge + country, before serialization).
    for s in stations:
        if s.id in name_overrides:
            print(f"name: {s.id} ({s.name}) -> {name_overrides[s.id]}")
            s.name = name_overrides[s.id]

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
                "sample_dates": [day.isoformat() for day in dates],
                "stations": [s.model_dump() for s in stations],
            },
            ensure_ascii=False,
        )
    )
    (graph_dir / "trips.json").write_text(
        json.dumps(
            {
                # Retained for one-date tools and older compute consumers.
                "trips": [t.model_dump() for t in trips_by_date[primary_day.isoformat()]],
                "trips_by_date": {
                    day: [t.model_dump() for t in trips] for day, trips in trips_by_date.items()
                },
                "feed_validity_by_date": feed_validity_by_date,
            },
            ensure_ascii=False,
        )
    )
    print(f"graph: {len(stations)} stations, {len(all_trips)} trips -> {graph_dir}")
