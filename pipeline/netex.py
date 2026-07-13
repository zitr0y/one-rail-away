"""Minimal reader for the Trenitalia Italian-profile NeTEx L1 publication.

This deliberately supports only the elements emitted by the registration-free
Trenitalia National Access Point asset: StopPlace/ScheduledStopPoint,
ServiceJourneyPattern, ServiceJourney and UIC operating-day bitmaps.  It is
not a general NeTEx-to-GTFS converter.
"""

import gzip
import re
import xml.etree.ElementTree as ET
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


def load_feed(path: Path, cfg: FeedConfig, sample_date: date) -> tuple[list[RawStop], list[Trip]]:
    """Read active, allowlisted Trenitalia journeys for ``sample_date``."""
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

    def runs(daytype: str) -> bool:
        period = periods.get(daytype_period.get(daytype, ""))
        if period is None:
            return False
        start, bits = period
        offset = (sample_date - start).days
        return 0 <= offset < len(bits) and bits[offset] == "1"

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

    used_stops: dict[str, RawStop] = {}
    trips: list[Trip] = []
    for journey in root.findall(".//n:ServiceJourney", NS):
        daytypes = [item.get("ref", "") for item in journey.findall(".//n:DayTypeRef", NS)]
        if not any(runs(daytype) for daytype in daytypes):
            continue
        line_id, point_to_stop = patterns.get(_ref(journey, "ServiceJourneyPatternRef"), ("", {}))
        if line_id not in selected_lines:
            continue
        short, _long = lines[line_id]
        stop_times: list[StopTime] = []
        for passing in journey.findall(".//n:TimetabledPassingTime", NS):
            stop_id = point_to_stop.get(_ref(passing, "StopPointInJourneyPatternRef"), "")
            if not stop_id or stop_id not in places:
                continue
            arrival, departure = _text(passing, "ArrivalTime"), _text(passing, "DepartureTime")
            if not (arrival or departure):
                continue
            arrival_day_offset = int(_text(passing, "ArrivalDayOffset") or "0") * 1440
            departure_day_offset = int(_text(passing, "DepartureDayOffset") or "0") * 1440
            stop_times.append(
                StopTime(
                    station=stop_id,
                    arr=_minutes(arrival or departure) + arrival_day_offset,
                    dep=_minutes(departure or arrival) + departure_day_offset,
                )
            )
            used_stops[stop_id] = places[stop_id]
        if len(stop_times) >= 2:
            name = _text(journey, "Name")
            trips.append(
                Trip(
                    trip_id=journey.get("id", ""),
                    train=f"{short} {name}".strip(),
                    stops=stop_times,
                )
            )
    return list(used_stops.values()), trips
