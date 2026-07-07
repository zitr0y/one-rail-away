"""GTFS feed loading: service-day resolution, long-distance route filtering, time parsing.

Behavior notes:
- Times are minutes since midnight of the service day and may exceed 1440
  ("26:15:00" -> 1575); no modulo is ever applied.
- stop_times rows with BOTH arrival_time and departure_time empty are skipped
  with a logged warning naming the trip and stop (GTFS allows untimed
  intermediate stops; downstream reachability math needs concrete times).
- Stops missing coordinates are skipped with a logged warning.
"""

import csv
import io
import logging
import re
import zipfile
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
    lat: float
    lon: float


def next_tuesday(today: date) -> date:
    """Next Tuesday strictly after `today` (a Tuesday input returns next week's Tuesday)."""
    days_ahead = (1 - today.weekday()) % 7  # Tuesday == 1
    return today + timedelta(days=days_ahead or 7)


def _minutes(hms: str) -> int:
    """Parse "HH:MM:SS" to minutes since midnight; hours may exceed 23 (no wraparound)."""
    h, m, _s = hms.strip().split(":")
    return int(h) * 60 + int(m)


def _rows(zf: zipfile.ZipFile, name: str) -> list[dict]:
    if name not in zf.namelist():
        return []
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


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
    with zipfile.ZipFile(zip_path) as zf:
        routes: dict[str, str] = {}
        for r in _rows(zf, "routes.txt"):
            name = r.get("route_short_name") or r.get("route_long_name") or ""
            if any(p.search(name) for p in allow):
                routes[r["route_id"]] = name

        active = _active_services(zf, sample_date)
        trip_train = {
            t["trip_id"]: routes[t["route_id"]]
            for t in _rows(zf, "trips.txt")
            if t["route_id"] in routes and t["service_id"] in active
        }

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
            # it as a placeholder for foreign stops they don't carry real coordinates
            # for (seen in practice: ovapi/NS stubs for German stations reached by
            # cross-border trains). Treat it the same as a missing coordinate.
            if not (lat and lon) or (float(lat) == 0.0 and float(lon) == 0.0):
                logger.warning(
                    "skipping stop without real coordinates: %s (%s) in %s",
                    s["stop_id"], s.get("stop_name", ""), zip_path.name,
                )
                continue
            stops.append(RawStop(s["stop_id"], s["stop_name"], float(lat), float(lon)))
    return stops, trips
