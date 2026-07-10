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
"""

import csv
import io
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
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


def _rows(zf: zipfile.ZipFile, name: str) -> Iterator[dict]:
    """Stream a GTFS text file as dict rows, tolerating a subdirectory prefix.

    Some feeds nest every file under one directory (OEBB uses
    "GTFS_Fahrplan_2026/stops.txt"); match by basename so a bare name like
    "stops.txt" still resolves.

    Yields lazily: real stop_times.txt files run to tens of millions of rows
    (ovapi/NS), and materializing them as a list of dicts costs gigabytes of
    RSS. Every caller consumes the rows in a single pass.
    """
    member = next((n for n in zf.namelist() if n == name or n.endswith(f"/{name}")), None)
    if member is None:
        return
    with zf.open(member) as f:
        # Some exports (Renfe 2026-07) right-pad EVERY line -- headers included --
        # to a fixed ~350-byte width with trailing spaces. Unstripped, the last
        # fieldname becomes "end_date" + ~300 spaces, so row["end_date"] raises
        # KeyError before any row is usable; padded cell values would likewise
        # poison stop_ids/names downstream. Strip fieldnames once and every
        # string cell per row.
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        if reader.fieldnames:
            reader.fieldnames = [fn.strip() for fn in reader.fieldnames]
        for row in reader:
            yield {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}


def _active_services(zf: zipfile.ZipFile, day: date) -> set[str]:
    """Service ids active on `day`: calendar.txt weekday+range, then calendar_dates overrides."""
    ymd = day.strftime("%Y%m%d")
    active: set[str] = set()
    for row in _rows(zf, "calendar.txt"):
        if (
            row["start_date"] <= ymd <= row["end_date"]
            and row[WEEKDAY_COLS[day.weekday()]] == "1"
        ):
            active.add(row["service_id"])
    for row in _rows(zf, "calendar_dates.txt"):
        if row["date"] == ymd:
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            else:
                active.discard(row["service_id"])
    return active


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


def load_feed(
    zip_path: Path, cfg: FeedConfig, sample_date: date
) -> tuple[list[RawStop], list[Trip]]:
    """Load one GTFS zip: keep trips active on sample_date on allowlisted routes.

    Returns (stops actually used by kept trips, trips). Stop ids are feed-local
    (canonicalization to UIC happens later).
    """
    allow = [re.compile(p) for p in cfg.route_allow]
    trip_allow = [re.compile(p) for p in cfg.trip_allow] if cfg.trip_allow else None
    brand_patterns = (
        [(re.compile(p), b) for p, b in cfg.stop_id_brand.items()]
        if cfg.stop_id_brand
        else None
    )
    if cfg.stop_id_allow:
        stop_id_allow = [re.compile(p) for p in cfg.stop_id_allow]
    elif brand_patterns:
        # stop_id_brand doubles as the stop-id trip filter (config forbids both).
        stop_id_allow = [p for p, _ in brand_patterns]
    else:
        stop_id_allow = None
    with zipfile.ZipFile(zip_path) as zf:
        routes: dict[str, str] = {}
        for r in _rows(zf, "routes.txt"):
            short = (r.get("route_short_name") or "").strip()
            long = (r.get("route_long_name") or "").strip()
            # Match patterns against BOTH names: some feeds put the brand only in
            # route_long_name even when short_name is populated (SNCF short_name is
            # an opaque code like "001G"; the brand is a trailing word in long_name,
            # e.g. "Lille - Alpes TGV"). The DISPLAY name still prefers short_name.
            if any(p.search(short) or p.search(long) for p in allow):
                routes[r["route_id"]] = short or long

        active = _active_services(zf, sample_date)
        trip_train: dict[str, str] = {}
        trip_headsign: dict[str, str] = {}
        for t in _rows(zf, "trips.txt"):
            if t["route_id"] not in routes or t["service_id"] not in active:
                continue
            if trip_allow is not None:
                # Trip-level filter: keep only trips whose trip_short_name matches,
                # and use that name as the label (see FeedConfig.trip_allow).
                short = (t.get("trip_short_name") or "").strip()
                if not any(p.search(short) for p in trip_allow):
                    continue
                trip_train[t["trip_id"]] = short
            else:
                trip_train[t["trip_id"]] = routes[t["route_id"]]
            if brand_patterns is not None and t["trip_id"] in trip_train:
                trip_headsign[t["trip_id"]] = (t.get("trip_headsign") or "").strip()

        stop_times: dict[str, list[tuple[int, StopTime]]] = {}
        for st in _rows(zf, "stop_times.txt"):
            tid = st["trip_id"]
            if tid not in trip_train:
                continue
            arrival = (st.get("arrival_time") or "").strip()
            departure = (st.get("departure_time") or "").strip()
            arr, dep = arrival or departure, departure or arrival
            if not arr:  # both empty: untimed intermediate stop, unusable downstream
                logger.warning(
                    "skipping untimed stop_times row: trip %s stop %s (seq %s) in %s",
                    tid, st["stop_id"], st.get("stop_sequence"), zip_path.name,
                )
                continue
            entry = (
                int(st["stop_sequence"]),
                StopTime(station=st["stop_id"], arr=_minutes(arr), dep=_minutes(dep)),
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
        stop_recs: dict[str, tuple[str, str, str, str]] = {
            s["stop_id"]: (
                s["stop_name"],
                s.get("stop_lat") or "",
                s.get("stop_lon") or "",
                s.get("parent_station") or "",
            )
            for s in _rows(zf, "stops.txt")
        }

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

        trips = []
        used_stops: set[str] = set()  # resolved stop ids used by KEPT trips only
        resolved: dict[str, str] = {}
        for tid, entries in stop_times.items():
            entries.sort(key=lambda e: e[0])
            kept = [e[1] for e in entries]
            # stop_id_allow patterns are written against the RAW feed ids (the
            # brand-carrying StopPoints), so filter before parent resolution.
            if stop_id_allow is not None and not any(_stop_id_passes(s.station) for s in kept):
                continue
            if brand_patterns is not None:
                # Brand also lives in the RAW ids: label before parent resolution.
                label = _brand_label(
                    (s.station for s in kept), brand_patterns, trip_headsign.get(tid, "")
                )
                if label is not None:
                    trip_train[tid] = label
            for s in kept:
                if s.station not in resolved:
                    known = s.station in stop_recs
                    resolved[s.station] = _resolve(s.station) if known else s.station
                s.station = resolved[s.station]
            used_stops.update(s.station for s in kept)
            trips.append(Trip(trip_id=tid, train=trip_train[tid], stops=kept))

        # Display name per resolved stop: the SHORTEST of the parent's own name
        # and the used children's names (deterministic tie-break: lexicographic).
        # db_fern parent rows sometimes carry context-free names ("Hauptbahnhof
        # (oben)" over the child "Stuttgart Hbf"), while OEBB children carry
        # platform-suffixed names ("Linz/Donau Hauptbahnhof 8" under the parent
        # "Linz/Donau Hauptbahnhof"); the shortest name is the right one in both.
        name_pool: dict[str, set[str]] = {}
        for orig, res in resolved.items():
            if orig in stop_recs and res in used_stops:
                name_pool.setdefault(res, set()).add(stop_recs[orig][0])

        stops: list[RawStop] = []
        # Iterate stop_recs (stops.txt file order), not used_stops: set order is
        # hash-randomized and merge_stations treats first-registered as winner.
        # A used id absent from stops.txt yields no RawStop; merge then strips it.
        for sid, (own_name, lat, lon, _parent) in stop_recs.items():
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
