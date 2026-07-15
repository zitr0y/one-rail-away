"""Minimal reader for the Trenitalia Italian-profile NeTEx L1 publication.

This deliberately supports only the elements emitted by the registration-free
Trenitalia National Access Point asset: StopPlace/ScheduledStopPoint,
ServiceJourneyPattern, ServiceJourney and UIC operating-day bitmaps.  It is
not a general NeTEx-to-GTFS converter.

Performance note (backlog AT): the gzipped XML publication is parsed and every
static lookup table (lines, operating periods, day-type assignments, places,
patterns, per-journey stop lists) is built exactly ONCE per feed
(`_parse_feed_once`), regardless of how many sample dates are requested --
only the per-`ServiceJourney` day-bitmap check (`_runs`) varies by date.
`load_feed_days` derives each requested date's `(stops, trips)` from that
shared, day-independent parse. As with `pipeline.gtfs`, every `Trip`/
`StopTime` handed to a caller is a FRESH instance built from cached
primitives -- never shared across dates (see `pipeline.gtfs`'s module
docstring for why that matters: `remap_trips`/`build.py` mutate them in
place per date).
"""

import gzip
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop, _minutes
from pipeline.models import StopTime, Trip

NS = {"n": "http://www.netex.org.uk/netex"}

# Upstream defect verified 2026-07-14: the NAP publishes Napoli Afragola as
# (10.1, 40.1), transposing neither Italy nor any plausible station location.
# The replacement is the geotagged station location recorded by Wikimedia/OSM.
COORDINATE_FIXES = {
    "IT::ScheduledStopPoint:otherTRENITALIA:830009988": (40.931758, 14.331131),
}


def _text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    child = element.find(f"n:{name}", NS)
    return (child.text or "").strip() if child is not None else ""


def _ref(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    child = element.find(f".//n:{name}", NS)
    return child.get("ref", "") if child is not None else ""


def _root(path: Path) -> ET.Element:
    with gzip.open(path, "rb") as source:
        return ET.parse(source).getroot()


def feed_validity_window(path: Path) -> tuple[str, str] | None:
    """Return the min/max UIC operating-period dates in this publication."""
    bounds: list[str] = []
    for period in _root(path).findall(".//n:UicOperatingPeriod", NS):
        bounds.extend((_text(period, "FromDate")[:10], _text(period, "ToDate")[:10]))
    if not bounds:
        return None
    normalized = [value.replace("-", "") for value in bounds]
    return min(normalized), max(normalized)


@dataclass
class _ParsedJourney:
    trip_id: str
    train: str  # final display label, "<line short name> <journey name>"
    daytypes: list[str]  # DayTypeRef ids; a journey runs iff any resolves to a "1" bit
    stops: list[tuple[str, int, int]]  # (stop_id, arr_minutes, dep_minutes), passing-time order


@dataclass
class _ParsedFeed:
    places: dict[str, RawStop]
    periods: dict[str, tuple[date, str]]
    daytype_period: dict[str, str]
    journeys: list[_ParsedJourney]  # document order; already line/stop-count filtered


def _runs(periods: dict[str, tuple[date, str]], daytype_period: dict[str, str],
          daytype: str, sample_date: date) -> bool:
    period = periods.get(daytype_period.get(daytype, ""))
    if period is None:
        return False
    start, bits = period
    offset = (sample_date - start).days
    return 0 <= offset < len(bits) and bits[offset] == "1"


def _parse_feed_once(path: Path, cfg: FeedConfig) -> _ParsedFeed:
    """Parse the gzipped XML publication and every static lookup table ONCE.

    Everything here (line selection, operating-period bitmaps, stop places,
    per-journey stop lists) is day-independent -- only whether a given
    journey's day-type bitmap has a "1" bit at a given date's offset varies,
    which `_derive_day` checks per requested date against the cached
    `_ParsedFeed.journeys` (already filtered to line-allowed, >=2-stop
    journeys, in document order).
    """
    root = _root(path)
    allow = [re.compile(pattern) for pattern in cfg.route_allow]
    lines = {
        line.get("id", ""): (_text(line, "ShortName"), _text(line, "Name"))
        for line in root.findall(".//n:Line", NS)
    }
    selected_lines = {
        line_id for line_id, (short, long) in lines.items()
        if any(pattern.search(short) or pattern.search(long) for pattern in allow)
    }
    periods: dict[str, tuple[date, str]] = {}
    for period in root.findall(".//n:UicOperatingPeriod", NS):
        periods[period.get("id", "")] = (
            date.fromisoformat(_text(period, "FromDate")[:10]), _text(period, "ValidDayBits")
        )
    daytype_period = {
        _ref(assignment, "DayTypeRef"): _ref(assignment, "OperatingPeriodRef")
        for assignment in root.findall(".//n:DayTypeAssignment", NS)
    }

    places: dict[str, RawStop] = {}
    for place in root.findall(".//n:StopPlace", NS):
        location = place.find("n:Centroid/n:Location", NS)
        lat, lon = _text(location, "Latitude"), _text(location, "Longitude")
        places[place.get("id", "")] = RawStop(
            stop_id=place.get("id", ""), name=_text(place, "Name"),
            lat=float(lat) if lat else None, lon=float(lon) if lon else None,
        )
    # The inspected Trenitalia export puts the station name and coordinates
    # directly on ScheduledStopPoint and does not emit StopPlaceRef.  Retain
    # StopPlaceRef support for the compact hierarchy used by profile variants.
    scheduled_to_place: dict[str, str] = {}
    for point in root.findall(".//n:ScheduledStopPoint", NS):
        stop_id = point.get("id", "")
        place_id = _ref(point, "StopPlaceRef")
        if place_id:
            scheduled_to_place[stop_id] = place_id
            continue
        location = point.find("n:Location", NS)
        lat, lon = _text(location, "Latitude"), _text(location, "Longitude")
        coordinates = COORDINATE_FIXES.get(stop_id)
        places[stop_id] = RawStop(
            stop_id=stop_id, name=_text(point, "Name"),
            lat=coordinates[0] if coordinates else (float(lat) if lat else None),
            lon=coordinates[1] if coordinates else (float(lon) if lon else None),
        )
        scheduled_to_place[stop_id] = stop_id
    patterns: dict[str, tuple[str, dict[str, str]]] = {}
    for pattern in root.findall(".//n:ServiceJourneyPattern", NS):
        point_to_stop = {
            point.get("id", ""): scheduled_to_place.get(_ref(point, "ScheduledStopPointRef"), "")
            for point in pattern.findall(".//n:StopPointInJourneyPattern", NS)
        }
        patterns[pattern.get("id", "")] = (_ref(pattern, "LineRef"), point_to_stop)

    journeys: list[_ParsedJourney] = []
    for journey in root.findall(".//n:ServiceJourney", NS):
        daytypes = [item.get("ref", "") for item in journey.findall(".//n:DayTypeRef", NS)]
        line_id, point_to_stop = patterns.get(_ref(journey, "ServiceJourneyPatternRef"), ("", {}))
        if line_id not in selected_lines:
            continue
        short, _long = lines[line_id]
        stop_times: list[tuple[str, int, int]] = []
        for passing in journey.findall(".//n:TimetabledPassingTime", NS):
            stop_id = point_to_stop.get(_ref(passing, "StopPointInJourneyPatternRef"), "")
            if not stop_id or stop_id not in places:
                continue
            arrival, departure = _text(passing, "ArrivalTime"), _text(passing, "DepartureTime")
            if not (arrival or departure):
                continue
            arrival_day_offset = int(_text(passing, "ArrivalDayOffset") or "0") * 1440
            departure_day_offset = int(_text(passing, "DepartureDayOffset") or "0") * 1440
            stop_times.append((
                stop_id,
                _minutes(arrival or departure) + arrival_day_offset,
                _minutes(departure or arrival) + departure_day_offset,
            ))
        if len(stop_times) < 2:
            continue
        name = _text(journey, "Name")
        journeys.append(_ParsedJourney(
            trip_id=journey.get("id", ""),
            train=f"{short} {name}".strip(),
            daytypes=daytypes,
            stops=stop_times,
        ))
    return _ParsedFeed(
        places=places, periods=periods, daytype_period=daytype_period, journeys=journeys
    )


def _derive_day(parsed: _ParsedFeed, sample_date: date) -> tuple[list[RawStop], list[Trip]]:
    """Build one date's (stops, trips) from a shared `_ParsedFeed`. Every
    `StopTime`/`Trip` here is a brand-new instance (see module docstring)."""
    used_stops: dict[str, RawStop] = {}
    trips: list[Trip] = []
    for j in parsed.journeys:
        if not any(
            _runs(parsed.periods, parsed.daytype_period, dt, sample_date) for dt in j.daytypes
        ):
            continue
        stops = [StopTime(station=stop_id, arr=arr, dep=dep) for stop_id, arr, dep in j.stops]
        for stop_id, _arr, _dep in j.stops:
            used_stops[stop_id] = parsed.places[stop_id]
        trips.append(Trip(trip_id=j.trip_id, train=j.train, stops=stops))
    return list(used_stops.values()), trips


def load_feed(path: Path, cfg: FeedConfig, sample_date: date) -> tuple[list[RawStop], list[Trip]]:
    """Read active, allowlisted Trenitalia journeys for ``sample_date``."""
    return _derive_day(_parse_feed_once(path, cfg), sample_date)


def load_feed_days(
    path: Path, cfg: FeedConfig, days: list[date]
) -> dict[str, tuple[list[RawStop], list[Trip]]]:
    """Parse the publication ONCE; derive one `(stops, trips)` result per
    requested date. See module docstring for why this is provably
    byte-identical to calling `load_feed` once per date."""
    parsed = _parse_feed_once(path, cfg)
    return {day.isoformat(): _derive_day(parsed, day) for day in days}
