"""Graph assembly: load every feed, merge stations across feeds, remap trip stop
ids to canonical station ids, join border-split through-services, validate, and
write the graph JSON files consumed by the rest of the pipeline
(`data/graph/stations.json`, `data/graph/trips.json`).
"""

import itertools
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
from pipeline.gtfs import (
    calendar_absent_from_week,
    calendar_active_services,
    calendar_window,
    load_calendar,
    load_feed_days,
)
from pipeline.merge import _dist_m, _norm, merge_stations
from pipeline.models import CountryOverride, Station, StopTime, Trip
from pipeline.through import join_through_services

logger = logging.getLogger(__name__)

# Sentinel key for the "services absent from the sampled week" extra probe (see
# `services_absent_from_week`): a destination reached only by such a service
# must still appear on the map, so one extra sample is loaded alongside the
# regular per-day ones. Never a real `date.isoformat()` value.
_ABSENT_PROBE = "_absent_probe"


def _load_feed_samples(
    task: tuple[str, Path, FeedConfig, list[date], dict[str, set[str]]],
) -> tuple[str, dict[str, tuple[list, list[Trip]]], tuple[list, list[Trip]] | None]:
    """Load all in-coverage probes for one feed in an isolated process.

    One task owns one zip, so workers never share mutable GTFS objects or write
    output.  The parent merges the returned data in feed/date order, which
    keeps graph JSON and console output deterministic.

    GTFS feeds are parsed exactly ONCE here regardless of how many dates are
    requested (backlog AT): the parent process already parsed each feed's
    calendar once and precomputed every requested day's (and the absent-probe's)
    active-service-id set into `day_service_ids`, so `load_feed_days` never
    re-reads calendar.txt/calendar_dates.txt and only opens the zip once for
    routes/trips/stop_times/stops.txt too. NeTEx feeds have no per-day
    active-service-id concept (day-bitmap checks are evaluated per journey
    instead), so they use `days` directly via `netex.load_feed_days`.
    """
    name, zip_path, cfg, days, day_service_ids = task
    if cfg.format == "netex":
        return name, netex.load_feed_days(zip_path, cfg, days), None
    loaded = load_feed_days(zip_path, cfg, day_service_ids)
    extra = loaded.pop(_ABSENT_PROBE, None)
    return name, loaded, extra


def remap_trips(
    feed_trips: dict[str, list[Trip]], mapping: dict[tuple[str, str], str]
) -> list[Trip]:
    """Remap each trip's feed-local stop ids to canonical station ids.

    A stop whose (feed, stop_id) is absent from `mapping` is an unresolved stub
    the merge stage dropped (a coordinate-less foreign stop that could not be
    matched onto a real station); it is STRIPPED from the trip with a warning.
    Trips left with fewer than 2 stops afterwards are dropped with a warning.
    Inputs are never mutated: remapping the same Trip object twice (e.g. one
    shared across per-day lists) must not re-remap already-canonical ids.
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
                remapped.append(StopTime(station=canonical, arr=s.arr, dep=s.dep))
            if len(remapped) >= 2:
                kept.append(
                    Trip(trip_id=t.trip_id, train=t.train, stops=remapped, feeds=list(t.feeds))
                )
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
        for a, b in itertools.pairwise(t.stops):
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


def _union_feed_stops(
    per_feed: dict[str, tuple[list, object]], name: str, cfg: object, stops: list
) -> None:
    """merge_stations wants each feed's stops once; union all sampled stops by
    feed-local id so an out-of-week-only stop is retained."""
    if name not in per_feed:
        per_feed[name] = ([], cfg)
    known = {s.stop_id for s in per_feed[name][0]}
    per_feed[name][0].extend(s for s in stops if s.stop_id not in known)


def build(
    raw_dir: Path,
    graph_dir: Path,
    feeds_path: Path,
    aliases_path: Path | None,
    sample_date: date,
    *,
    sample_dates: list[date] | None = None,
    feed_sample_dates: dict[str, list[date]] | None = None,
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

    # ``sample_dates`` remains an escape hatch for focused tests/debugging.
    # Normal CLI builds pass the union of each feed's own selected week.
    dates = list(dict.fromkeys(sample_dates or [sample_date]))
    primary_day = sample_date if sample_date in dates else dates[0]
    per_feed: dict[str, tuple[list, object]] = {}
    feed_trips_by_date: dict[str, dict[str, list[Trip]]] = {}
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] = {}

    # Calendar files are parsed exactly ONCE per GTFS feed here (backlog AT):
    # `cal` is reused for the coverage window, the "absent from week" probe,
    # and every requested day's active-service-id set, with zero further
    # calendar.txt/calendar_dates.txt reads. NeTEx feeds have no GTFS calendar;
    # their window comes from the UIC operating periods instead and they get no
    # absent-service probe (unsupported for that format today).
    #
    # One feed's calendar is resident at a time: `cal` is rebound (freed) each
    # iteration. Holding every feed's parsed calendar simultaneously OOM-killed
    # the production build (2026-07-15) -- all-transit feeds carry millions of
    # calendar_dates rows each.
    #
    # The coverage filter keeps explicit debug dates in check: an out-of-horizon
    # date is not zero-service evidence and should not trigger a large
    # stop_times parse. Per-day active-service-id sets are precomputed here so
    # worker processes never touch calendar files at all -- see
    # `_load_feed_samples`.
    feed_windows: dict[str, tuple[str, str] | None] = {}
    feed_days: dict[str, list[date]] = {}
    absent_services: dict[str, set[str]] = {}
    day_service_ids: dict[str, dict[str, set[str]]] = {}
    for name, cfg in feeds.items():
        zip_path = raw_dir / f"{name}.zip"
        cal = None
        if zip_path.exists():
            if cfg.format == "netex":
                feed_windows[name] = netex.feed_validity_window(zip_path)
            else:
                cal = load_calendar(zip_path)
                feed_windows[name] = calendar_window(cal)
        window = feed_windows.get(name)
        requested = (feed_sample_dates or {}).get(name, dates)
        if window is None:
            feed_days[name] = list(requested)
        else:
            usable = [
                day for day in requested if window[0] <= day.strftime("%Y%m%d") <= window[1]
            ]
            feed_days[name] = usable
            skipped = [day for day in requested if day not in usable]
            if skipped:
                logger.warning(
                    "feed %s: skipping %d/%d probes outside published GTFS coverage %s..%s (%s)",
                    name,
                    len(skipped),
                    len(requested),
                    window[0],
                    window[1],
                    ", ".join(day.isoformat() for day in skipped),
                )
        if cal is not None and feed_days[name]:
            absent = calendar_absent_from_week(cal, feed_days[name])
            per_day = {
                day.isoformat(): calendar_active_services(cal, day) for day in feed_days[name]
            }
            if absent:
                absent_services[name] = absent
                per_day[_ABSENT_PROBE] = absent
            day_service_ids[name] = per_day

    tasks = [
        (
            name, raw_dir / f"{name}.zip", cfg, feed_days[name],
            day_service_ids.get(name, {}),
        )
        for name, cfg in feeds.items()
        if (raw_dir / f"{name}.zip").exists() and feed_days[name]
    ]
    loaded_by_feed: dict[str, dict[str, tuple[list, list[Trip]]]] = {}
    # Extra sample per feed: trips active on a day outside the selected week,
    # loaded only for services absent from every sampled date (see
    # services_absent_from_week) so destinations they alone serve still appear.
    extra_by_feed: dict[str, tuple[list, list[Trip]]] = {}
    max_workers = min(workers or os.process_cpu_count() or 1, len(tasks))
    if max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            # executor.map preserves task order; the following date loop also
            # makes the final serialized graph independent of worker timing.
            for name, loaded, extra in pool.map(_load_feed_samples, tasks):
                loaded_by_feed[name] = loaded
                if extra is not None:
                    extra_by_feed[name] = extra
    else:
        for task in tasks:
            name, loaded, extra = _load_feed_samples(task)
            loaded_by_feed[name] = loaded
            if extra is not None:
                extra_by_feed[name] = extra

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
                "sampled": day in feed_days[name],
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
            _union_feed_stops(per_feed, name, cfg, stops)
            feed_trips[name] = trips
            print(f"{day.isoformat()} {name}: {len(stops)} stops, {len(trips)} long-distance trips")
        feed_trips_by_date[day.isoformat()] = feed_trips
        feed_validity_by_date[day.isoformat()] = validity

    # A trip whose service is absent from the selected week can introduce
    # stops not used by the selected week.  Retain them in the shared station
    # registry too.
    for name, (stops, _trips) in extra_by_feed.items():
        for trip in _trips:
            trip.feeds = [name]
        _union_feed_stops(per_feed, name, feeds[name], stops)

    stations, mapping = merge_stations(per_feed, aliases)
    for line in assign_countries(stations, load_countries(ASSET), country_overrides):
        print(f"country: {line}")
    trips_by_date = {
        day: join_through_services(remap_trips(feed_trips, mapping))
        for day, feed_trips in feed_trips_by_date.items()
    }
    extra_trips = join_through_services(remap_trips(
        {
            name: trips
            for name, (_stops, trips) in extra_by_feed.items()
        },
        mapping,
    ))
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
                "extra_trips": [t.model_dump() for t in extra_trips],
                "feed_validity_by_date": feed_validity_by_date,
            },
            ensure_ascii=False,
        )
    )
    print(f"graph: {len(stations)} stations, {len(all_trips)} trips -> {graph_dir}")
