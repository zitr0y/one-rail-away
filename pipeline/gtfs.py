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
from collections.abc import Iterator
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
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


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


def load_feed(
    zip_path: Path, cfg: FeedConfig, sample_date: date
) -> tuple[list[RawStop], list[Trip]]:
    """Load one GTFS zip: keep trips active on sample_date on allowlisted routes.

    Returns (stops actually used by kept trips, trips). Stop ids are feed-local
    (canonicalization to UIC happens later).
    """
    allow = [re.compile(p) for p in cfg.route_allow]
    trip_allow = [re.compile(p) for p in cfg.trip_allow] if cfg.trip_allow else None
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

        stop_times: dict[str, list[tuple[int, StopTime]]] = {}
        used_stops: set[str] = set()
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
            used_stops.add(st["stop_id"])

        trips = []
        for tid, entries in stop_times.items():
            entries.sort(key=lambda e: e[0])
            trips.append(Trip(trip_id=tid, train=trip_train[tid], stops=[e[1] for e in entries]))

        stops: list[RawStop] = []
        for s in _rows(zf, "stops.txt"):
            if s["stop_id"] not in used_stops:
                continue
            lat, lon = s.get("stop_lat"), s.get("stop_lon")
            # (0, 0) is mid-Atlantic, never a real European station -- some feeds use
            # it as a placeholder for a foreign stop they carry no real coordinate for
            # (seen in practice: ovapi/NS stubs for German stations reached by
            # cross-border trains). Treat it the same as a missing coordinate: keep the
            # stop as a coordinate-less STUB (lat/lon None) rather than dropping it. It
            # is the foreign half of a real cross-border trip; merge_stations resolves
            # it by name onto the real canonical station, or drops it there.
            if not (lat and lon) or (float(lat) == 0.0 and float(lon) == 0.0):
                stops.append(RawStop(s["stop_id"], s["stop_name"], None, None))
            else:
                stops.append(RawStop(s["stop_id"], s["stop_name"], float(lat), float(lon)))
    return stops, trips
