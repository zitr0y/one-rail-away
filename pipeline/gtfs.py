"""GTFS feed loading: service-day resolution, long-distance route filtering, time parsing.

Behavior notes:
- Times are minutes since midnight of the service day and may exceed 1440
  ("26:15:00" -> 1575); no modulo is ever applied.
- stop_times rows with BOTH arrival_time and departure_time empty are skipped
  with a logged warning naming the trip and stop (GTFS allows untimed
  intermediate stops; downstream reachability math needs concrete times).
- Stops missing coordinates (or at the (0,0) placeholder) are kept as
  coordinate-less stubs (lat/lon None), not dropped; merge_stations resolves
  them by name or drops them there.

Performance notes (backlog AT, 2026-07-15 efficiency audit):
- Calendar files (calendar.txt / calendar_dates.txt) are parsed into a plain
  `_Calendar` exactly once per feed (`load_calendar`); every date-window /
  active-service-set computation afterwards is pure in-memory set logic over
  that struct (`calendar_window`, `calendar_active_services`,
  `calendar_absent_from_week`) with zero further zip reads.
- routes.txt/trips.txt/stop_times.txt/stops.txt are parsed exactly once per
  feed regardless of how many sample dates are requested: `_parse_feed_once`
  builds day-INDEPENDENT structures (route/trip-allow/stop_id-allow/brand
  decisions, parent-station resolution, sorted per-trip stop lists) once, and
  `_derive_day` cheaply re-derives one day's `(stops, trips)` by filtering the
  day-independent structures on that day's active-service-id set. Row
  encounter order in stop_times.txt is preserved end to end (dict insertion
  order), so per-day trip order / stop order / name pools are bit-identical
  to independently re-parsing the zip per day.
- `_row_reader` replaces a DictReader-based `_rows` (one dict built + a second
  dict built by stripping every cell) with `csv.reader` + header-resolved
  column indices: rows are plain string lists, the hot stop_times.txt loop
  filters on trip_id BEFORE any `.strip()` runs, and only cells actually read
  get stripped.
- CRITICAL: every `Trip`/`StopTime` returned to a caller (from `load_feed` or
  `load_feed_days`) is a FRESH pydantic instance built from immutable cached
  primitives (str/int tuples). Nothing pydantic is ever shared or reused
  across two dates: `pipeline.build.remap_trips` mutates `StopTime.station`
  in place and `build.py` sets `trip.feeds` per day, so sharing objects
  across dates would silently corrupt one date's data with another's.
"""

import csv
import io
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import FeedConfig
from pipeline.models import StopTime, Trip

logger = logging.getLogger(__name__)

WEEKDAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class RawStop:
    stop_id: str
    name: str
    lat: float | None  # None == coordinate-less stub (see load_feed / merge_stations)
    lon: float | None


def next_tuesday(today: date) -> date:
    """Next Tuesday strictly after `today` (a Tuesday input returns next week's Tuesday)."""
    days_ahead = (1 - today.weekday()) % 7  # Tuesday == 1
    return today + timedelta(days=days_ahead or 7)


def _minutes(hms: str) -> int:
    """Parse "HH:MM:SS" to minutes since midnight; hours may exceed 23 (no wraparound)."""
    h, m, _s = hms.strip().split(":")
    return int(h) * 60 + int(m)


def _rows_from_open_reader(f: zipfile.ZipExtFile, reader: "csv._reader") -> Iterator[list[str]]:
    """Yield the remaining rows of `reader`, closing `f` when exhausted or GC'd.

    Mirrors the old `_rows`' pattern of opening the zip member inside a `with`
    block that spans the whole generator body (the file stays open exactly as
    long as the caller keeps consuming rows).
    """
    with f:
        yield from reader


def _row_reader(
    zf: zipfile.ZipFile, name: str
) -> tuple[dict[str, int] | None, Iterator[list[str]]]:
    """Open one GTFS text file; return (column-name -> index, raw row iterator).

    Replaces a DictReader-per-row `_rows`: `csv.reader` yields plain string
    lists (no per-row dict), and callers resolve columns by index, filter
    BEFORE stripping, and strip only the cells they actually read -- the hot
    stop_times.txt loop discards the vast majority of rows before any
    `.strip()` runs.

    Tolerates a subdirectory prefix (some feeds, e.g. OEBB, nest every file
    under one directory) by matching on basename. Returns (None, empty
    iterator) when the member is absent -- same "tolerate a missing file"
    contract the old `_rows` had.

    Some exports (Renfe 2026-07) right-pad EVERY line -- headers included --
    to a fixed ~350-byte width with trailing spaces. Unstripped, the last
    fieldname would carry ~300 spaces and column lookups would miss; strip
    fieldnames once, same as before.
    """
    member = next((n for n in zf.namelist() if n == name or n.endswith(f"/{name}")), None)
    if member is None:
        return None, iter(())
    f = zf.open(member)
    reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8-sig"))
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration:
        f.close()
        return None, iter(())
    col = {h: i for i, h in enumerate(header)}
    return col, _rows_from_open_reader(f, reader)


def _get(row: list[str], col: dict[str, int], name: str) -> str:
    """Optional-cell fetch: "" if the column is absent or the row is short a
    trailing cell, else the stripped value. Mirrors the old `(row.get(name) or
    "").strip()` call-site pattern."""
    i = col.get(name)
    if i is None or i >= len(row):
        return ""
    return row[i].strip()


def _require(row: list[str], col: dict[str, int], name: str) -> str:
    """Required-cell fetch: KeyError if the column is absent from this file's
    header, matching the old `row["name"]` behavior on a DictReader dict
    missing that key."""
    return row[col[name]].strip()


# --- calendar: parsed once per feed, everything else is pure set logic -------


@dataclass
class _Calendar:
    # (service_id, start_date, end_date, [monday..sunday flags]) per calendar.txt row
    calendar_rows: list[tuple[str, str, str, list[str]]] = field(default_factory=list)
    # (service_id, date, exception_type) per calendar_dates.txt row, in file order
    exception_rows: list[tuple[str, str, str]] = field(default_factory=list)


def _parse_calendar(zf: zipfile.ZipFile) -> _Calendar:
    """Parse calendar.txt + calendar_dates.txt from an already-open zip, once."""
    calendar_rows: list[tuple[str, str, str, list[str]]] = []
    col, rows = _row_reader(zf, "calendar.txt")
    if col is not None:
        for row in rows:
            calendar_rows.append(
                (
                    _require(row, col, "service_id"),
                    _require(row, col, "start_date"),
                    _require(row, col, "end_date"),
                    [_require(row, col, day_col) for day_col in WEEKDAY_COLS],
                )
            )
    exception_rows: list[tuple[str, str, str]] = []
    col, rows = _row_reader(zf, "calendar_dates.txt")
    if col is not None:
        for row in rows:
            exception_rows.append(
                (
                    _require(row, col, "service_id"),
                    _require(row, col, "date"),
                    _require(row, col, "exception_type"),
                )
            )
    return _Calendar(calendar_rows, exception_rows)


def load_calendar(zip_path: Path) -> _Calendar:
    """Parse one feed's calendar files ONCE; reuse across every window / active-set
    / absent-from-week computation the caller needs (see module docstring)."""
    with zipfile.ZipFile(zip_path) as zf:
        return _parse_calendar(zf)


def calendar_active_services(cal: _Calendar, day: date) -> set[str]:
    """Service ids active on `day`: calendar.txt weekday+range, then calendar_dates
    overrides -- pure set logic over an already-parsed `_Calendar`."""
    ymd = day.strftime("%Y%m%d")
    active: set[str] = set()
    for service_id, start, end, flags in cal.calendar_rows:
        if start <= ymd <= end and flags[day.weekday()] == "1":
            active.add(service_id)
    for service_id, exc_date, exception_type in cal.exception_rows:
        if exc_date == ymd:
            if exception_type == "1":
                active.add(service_id)
            else:
                active.discard(service_id)
    return active


def calendar_window(cal: _Calendar) -> tuple[str, str] | None:
    """Published GTFS calendar horizon, if the feed exposes one (see
    `feed_validity_window` for the semantics)."""
    bounds: list[str] = []
    for _service_id, start, end, _flags in cal.calendar_rows:
        bounds.extend((start, end))
    for _service_id, exc_date, _exception_type in cal.exception_rows:
        bounds.append(exc_date)
    return (min(bounds), max(bounds)) if bounds else None


def calendar_absent_from_week(cal: _Calendar, sample_dates: list[date]) -> set[str]:
    """Service ids with no active day among `sample_dates` (see
    `services_absent_from_week` for the semantics)."""
    window = calendar_window(cal)
    if window is None:
        return set()
    all_ids: set[str] = set()
    for service_id, _start, _end, _flags in cal.calendar_rows:
        all_ids.add(service_id)
    for service_id, _exc_date, _exception_type in cal.exception_rows:
        all_ids.add(service_id)
    active_in_week: set[str] = set()
    for day in sample_dates:
        active_in_week.update(calendar_active_services(cal, day))
    return all_ids - active_in_week


def _active_services(zf: zipfile.ZipFile, day: date) -> set[str]:
    """Service ids active on `day`, parsing calendar files from `zf` directly
    (single-date `load_feed`'s own path; see `calendar_active_services` for the
    shared-parse multi-date path)."""
    return calendar_active_services(_parse_calendar(zf), day)


def feed_validity_window(zip_path: Path) -> tuple[str, str] | None:
    """Return the published GTFS calendar horizon, if the feed exposes one.

    A date outside this window is not negative service evidence: the snapshot
    simply cannot speak to it. A feed without calendar dates has an unknown
    horizon, which remains eligible rather than being guessed unavailable.
    """
    return calendar_window(load_calendar(zip_path))


def services_absent_from_week(zip_path: Path, sample_dates: list[date]) -> set[str]:
    """Return GTFS service ids not active on any of `sample_dates`.

    An out-of-week service is real coverage, not a classification: a
    destination reached only by a trip whose service days fall outside the
    sampled week must still appear on the map, so `build.py` loads one extra
    probe using these ids. This is NOT seasonality evidence -- an ordinary
    service can be "absent from week" merely because the sampled week landed
    on days it doesn't run.
    """
    return calendar_absent_from_week(load_calendar(zip_path), sample_dates)


def _brand_label(
    stop_ids: Iterable[str],
    brand_patterns: list[tuple[re.Pattern[str], str]],
    headsign: str,
) -> str | None:
    """Brand+number label ("TGV INOUI 9704"), or None to keep the route label.

    The brand comes from the first stop id (stop-sequence order) that matches
    any brand pattern, patterns checked in config table order. An empty
    headsign yields None: "TGV INOUI " would be worse than the opaque code.
    """
    if not headsign:
        return None
    for sid in stop_ids:
        for pattern, brand in brand_patterns:
            if pattern.search(sid):
                return f"{brand} {headsign}"
    return None


# --- feed body (routes/trips/stop_times/stops): parsed once, derived per day -


@dataclass
class _ParsedFeed:
    stop_recs: dict[str, tuple[str, str, str, str]]  # stop_id -> (name, lat, lon, parent)
    trip_order: list[str]  # trip ids, stop_times.txt first-appearance order
    trip_service: dict[str, str]  # trip id -> service_id
    trip_label: dict[str, str]  # trip id -> final display label
    trip_ok: set[str]  # passed the stop_id_allow filter (if configured)
    # trip id -> [(raw_stop_id, resolved_station_id, arr, dep), ...]. The raw id
    # is kept (not just the resolved one) so `_derive_day` can rebuild the
    # per-day name pool from exactly the raw stop-id variants referenced by
    # THAT day's trips -- see `_derive_day` for why this must stay per-day.
    resolved_stops: dict[str, list[tuple[str, str, int, int]]]


def _parse_feed_once(
    zf: zipfile.ZipFile, zip_path: Path, cfg: FeedConfig, relevant_service_ids: set[str]
) -> _ParsedFeed:
    """Parse routes/trips/stop_times/stops ONCE, bounded to trips whose
    service_id is in `relevant_service_ids` (the union of every date the
    caller will derive -- a day-independent superset, never a per-day filter:
    `_derive_day` re-checks each trip's actual service_id against that day's
    own active set). Every other decision made here (route/trip_allow
    eligibility, stop_id_allow / brand-label outcome, parent-station
    resolution, per-trip sorted stop list) depends only on trip/stop
    properties, never on which date is being asked for, so it is safe and
    correct to compute once and reuse for every requested date.
    """
    allow = [re.compile(p) for p in cfg.route_allow]
    trip_allow = [re.compile(p) for p in cfg.trip_allow] if cfg.trip_allow else None
    brand_patterns = (
        [(re.compile(p), b) for p, b in cfg.stop_id_brand.items()] if cfg.stop_id_brand else None
    )
    if cfg.stop_id_allow:
        stop_id_allow = [re.compile(p) for p in cfg.stop_id_allow]
    elif brand_patterns:
        # stop_id_brand doubles as the stop-id trip filter (config forbids both).
        stop_id_allow = [p for p, _ in brand_patterns]
    else:
        stop_id_allow = None

    routes: dict[str, str] = {}
    col, rows = _row_reader(zf, "routes.txt")
    if col is not None:
        for row in rows:
            short = _get(row, col, "route_short_name")
            long = _get(row, col, "route_long_name")
            # Match patterns against BOTH names: some feeds put the brand only in
            # route_long_name even when short_name is populated (SNCF short_name is
            # an opaque code like "001G"; the brand is a trailing word in long_name,
            # e.g. "Lille - Alpes TGV"). The DISPLAY name still prefers short_name.
            if any(p.search(short) or p.search(long) for p in allow):
                routes[_require(row, col, "route_id")] = short or long

    trip_train: dict[str, str] = {}
    trip_service: dict[str, str] = {}
    trip_headsign: dict[str, str] = {}
    col, rows = _row_reader(zf, "trips.txt")
    if col is not None:
        for row in rows:
            route_id = _require(row, col, "route_id")
            service_id = _require(row, col, "service_id")
            if route_id not in routes or service_id not in relevant_service_ids:
                continue
            tid = _require(row, col, "trip_id")
            if trip_allow is not None:
                # Trip-level filter: keep only trips whose trip_short_name matches,
                # and use that name as the label (see FeedConfig.trip_allow).
                short = _get(row, col, "trip_short_name")
                if not any(p.search(short) for p in trip_allow):
                    continue
                trip_train[tid] = short
            else:
                trip_train[tid] = routes[route_id]
            trip_service[tid] = service_id
            if brand_patterns is not None and tid in trip_train:
                trip_headsign[tid] = _get(row, col, "trip_headsign")

    stop_times: dict[str, list[tuple[int, str, int, int]]] = {}
    col, rows = _row_reader(zf, "stop_times.txt")
    if col is not None:
        for row in rows:
            tid = _require(row, col, "trip_id")
            if tid not in trip_train:
                continue
            arrival = _get(row, col, "arrival_time")
            departure = _get(row, col, "departure_time")
            arr, dep = arrival or departure, departure or arrival
            if not arr:  # both empty: untimed intermediate stop, unusable downstream
                logger.warning(
                    "skipping untimed stop_times row: trip %s stop %s (seq %s) in %s",
                    tid,
                    _get(row, col, "stop_id"),
                    _get(row, col, "stop_sequence"),
                    zip_path.name,
                )
                continue
            entry = (
                int(_require(row, col, "stop_sequence")),
                _require(row, col, "stop_id"),
                _minutes(arr),
                _minutes(dep),
            )
            stop_times.setdefault(tid, []).append(entry)

    # Stop-id-level trip filter (see FeedConfig.stop_id_allow): keep a trip only
    # if at least one of its stop ids matches. Verdicts are cached per stop_id --
    # stop_times runs to millions of rows but only thousands of distinct stops.
    id_ok: dict[str, bool] = {}

    def _stop_id_passes(stop_id: str) -> bool:
        if stop_id not in id_ok:
            id_ok[stop_id] = any(p.search(stop_id) for p in stop_id_allow)
        return id_ok[stop_id]

    # stop_id -> (name, lat, lon, parent_station); station-registry scale, small.
    stop_recs: dict[str, tuple[str, str, str, str]] = {}
    col, rows = _row_reader(zf, "stops.txt")
    if col is not None:
        for row in rows:
            stop_recs[_require(row, col, "stop_id")] = (
                _require(row, col, "stop_name"),
                _get(row, col, "stop_lat"),
                _get(row, col, "stop_lon"),
                _get(row, col, "parent_station"),
            )

    def _resolve(stop_id: str) -> str:
        """Topmost ancestor of stop_id that has a stops.txt row (cycle-guarded).

        Feeds reference per-platform stops in stop_times ("Linz/Donau
        Hauptbahnhof 8"); left unresolved, each platform becomes its own
        station and the router can never transfer there. A dangling parent
        reference (no row) keeps the child.
        """
        seen = {stop_id}
        while True:
            parent = stop_recs[stop_id][3]
            if not parent or parent not in stop_recs or parent in seen:
                return stop_id
            seen.add(parent)
            stop_id = parent

    trip_order = list(stop_times.keys())
    trip_label: dict[str, str] = dict(trip_train)
    trip_ok: set[str] = set()
    resolved: dict[str, str] = {}
    resolved_stops: dict[str, list[tuple[str, str, int, int]]] = {}

    for tid in trip_order:
        entries = stop_times[tid]
        entries.sort(key=lambda e: e[0])
        kept = [(raw_stop, arr, dep) for (_seq, raw_stop, arr, dep) in entries]
        # stop_id_allow patterns are written against the RAW feed ids (the
        # brand-carrying StopPoints), so filter before parent resolution.
        if stop_id_allow is not None and not any(
            _stop_id_passes(raw_stop) for raw_stop, _arr, _dep in kept
        ):
            continue
        trip_ok.add(tid)
        if brand_patterns is not None:
            # Brand also lives in the RAW ids: label before parent resolution.
            label = _brand_label(
                (raw_stop for raw_stop, _arr, _dep in kept),
                brand_patterns,
                trip_headsign.get(tid, ""),
            )
            if label is not None:
                trip_label[tid] = label
        out: list[tuple[str, str, int, int]] = []
        for raw_stop, arr, dep in kept:
            if raw_stop not in resolved:
                known = raw_stop in stop_recs
                resolved[raw_stop] = _resolve(raw_stop) if known else raw_stop
            out.append((raw_stop, resolved[raw_stop], arr, dep))
        resolved_stops[tid] = out

    return _ParsedFeed(
        stop_recs=stop_recs,
        trip_order=trip_order,
        trip_service=trip_service,
        trip_label=trip_label,
        trip_ok=trip_ok,
        resolved_stops=resolved_stops,
    )


def _derive_day(parsed: _ParsedFeed, active: set[str]) -> tuple[list[RawStop], list[Trip]]:
    """Build one day's (stops, trips) from a shared `_ParsedFeed`, filtering to
    trips whose service_id is active THAT day. Every `StopTime`/`Trip` here is a
    brand-new instance -- see the fresh-instance note in the module docstring.

    The per-day name pool must be built ONLY from the raw stop-id variants
    referenced by trips running on THIS day (not the full-week superset
    `_parse_feed_once` scanned): a raw child id whose only trip doesn't run
    today must not be able to influence today's chosen display name.
    """
    trips: list[Trip] = []
    used_stops: set[str] = set()
    name_pool: dict[str, set[str]] = {}
    for tid in parsed.trip_order:
        if tid not in parsed.trip_ok or parsed.trip_service[tid] not in active:
            continue
        stops_data = parsed.resolved_stops[tid]
        stops = [
            StopTime(station=resolved, arr=arr, dep=dep)
            for _raw, resolved, arr, dep in stops_data
        ]
        for raw, resolved, _arr, _dep in stops_data:
            used_stops.add(resolved)
            if raw in parsed.stop_recs:
                name_pool.setdefault(resolved, set()).add(parsed.stop_recs[raw][0])
        trips.append(Trip(trip_id=tid, train=parsed.trip_label[tid], stops=stops))

    # Display name per resolved stop: the SHORTEST of the parent's own name
    # and the used children's names (deterministic tie-break: lexicographic).
    # db_fern parent rows sometimes carry context-free names ("Hauptbahnhof
    # (oben)" over the child "Stuttgart Hbf"), while OEBB children carry
    # platform-suffixed names ("Linz/Donau Hauptbahnhof 8" under the parent
    # "Linz/Donau Hauptbahnhof"); the shortest name is the right one in both.
    stops: list[RawStop] = []
    # Iterate stop_recs (stops.txt file order), not used_stops: set order is
    # hash-randomized and merge_stations treats first-registered as winner.
    # A used id absent from stops.txt yields no RawStop; merge then strips it.
    for sid, (own_name, lat, lon, _parent) in parsed.stop_recs.items():
        if sid not in used_stops:
            continue
        name = min(name_pool.get(sid, set()) | {own_name}, key=lambda n: (len(n), n))
        # (0, 0) is mid-Atlantic, never a real European station -- some feeds use
        # it as a placeholder for a foreign stop they carry no real coordinate for
        # (seen in practice: ovapi/NS stubs for German stations reached by
        # cross-border trains). Treat it the same as a missing coordinate: keep the
        # stop as a coordinate-less STUB (lat/lon None) rather than dropping it. It
        # is the foreign half of a real cross-border trip; merge_stations resolves
        # it by name onto the real canonical station, or drops it there.
        if not (lat and lon) or (float(lat) == 0.0 and float(lon) == 0.0):
            stops.append(RawStop(sid, name, None, None))
        else:
            stops.append(RawStop(sid, name, float(lat), float(lon)))
    return stops, trips


def load_feed(
    zip_path: Path, cfg: FeedConfig, sample_date: date,
    *, service_ids: set[str] | None = None,
) -> tuple[list[RawStop], list[Trip]]:
    """Load one GTFS zip: keep trips active on sample_date on allowlisted routes.

    Returns (stops actually used by kept trips, trips). Stop ids are feed-local
    (canonicalization to UIC happens later).
    """
    with zipfile.ZipFile(zip_path) as zf:
        active = service_ids if service_ids is not None else _active_services(zf, sample_date)
        parsed = _parse_feed_once(zf, zip_path, cfg, active)
        return _derive_day(parsed, active)


def load_feed_days(
    zip_path: Path, cfg: FeedConfig, day_service_ids: dict[str, set[str]],
) -> dict[str, tuple[list[RawStop], list[Trip]]]:
    """Load one GTFS zip ONCE, deriving one `(stops, trips)` result per key of
    `day_service_ids` (each value is that key's active-service-id set -- an
    ordinary calendar day's set from `calendar_active_services`, or the
    "services absent from the sampled week" probe set build.py loads once per
    feed). See the module docstring for why this is provably byte-identical
    to calling `load_feed` once per key.
    """
    if not day_service_ids:
        return {}
    relevant = set().union(*day_service_ids.values())
    with zipfile.ZipFile(zip_path) as zf:
        parsed = _parse_feed_once(zf, zip_path, cfg, relevant)
        return {key: _derive_day(parsed, active) for key, active in day_service_ids.items()}
