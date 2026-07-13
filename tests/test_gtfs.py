"""Tests for pipeline.gtfs: feed loading, service-day logic, and long-distance filtering."""
# ruff: noqa: E501  # compact XML fixture below is clearer as literal NeTEx.

import gzip
import io
import logging
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import FeedConfig
from pipeline.gtfs import _brand_label, load_feed, next_tuesday
from pipeline.netex import COORDINATE_FIXES
from pipeline.netex import feed_validity_window as netex_validity_window
from pipeline.netex import load_feed as load_netex
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)  # a Tuesday

CFG = FeedConfig(url="u", country="XX", license="t", route_allow=["^IC\\b"])

CAL_ALL_DAYS = (
    "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
    "S1,1,1,1,1,1,1,1,20260101,20261231\n"
)

_DEFAULT_FILES = {
    "stops.txt": ("stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,50.0,8.0\nB,Beta,50.0,9.0\n"),
    "routes.txt": "route_id,route_short_name,route_type\nR1,IC 9,2\n",
    "trips.txt": "route_id,service_id,trip_id\nR1,S1,T1\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,08:00:00,08:00:00,A,1\n"
        "T1,09:00:00,09:00:00,B,2\n"
    ),
    "calendar.txt": CAL_ALL_DAYS,
}


def _make_feed(dir: Path, **overrides: str | None) -> Path:
    """Write a minimal single-trip feed zip; override or drop (None) individual files."""
    files = dict(_DEFAULT_FILES)
    for name, content in overrides.items():
        key = name.replace("_txt", ".txt")
        if content is None:
            files.pop(key, None)
        else:
            files[key] = content
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)
    path = dir / "mini.zip"
    path.write_bytes(buf.getvalue())
    return path


# --- Brief tests -------------------------------------------------------------


def test_load_feed_filters_regional_and_parses_times(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    stops, trips = load_feed(tmp_path / "landia.zip", cfgs["landia"], SAMPLE)
    names = {t.train for t in trips}
    assert names == {"IC 100", "IC 101", "IC 300"}  # RB 1 filtered out
    t100 = next(t for t in trips if t.train == "IC 100")
    assert [s.station for s in t100.stops] == ["st:1111111", "st:2222222", "st:3333333"]
    assert t100.stops[0].dep == 8 * 60 and t100.stops[2].arr == 10 * 60
    assert {s.stop_id for s in stops} == {"st:1111111", "st:2222222", "st:3333333"}


def test_load_feed_respects_calendar(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    _, trips = load_feed(tmp_path / "landia.zip", cfgs["landia"], date(2027, 1, 1))
    assert trips == []  # outside service range


def test_next_tuesday():
    assert next_tuesday(date(2026, 7, 7)) == date(2026, 7, 14)  # Tue -> next Tue
    assert next_tuesday(date(2026, 7, 8)) == date(2026, 7, 14)  # Wed -> coming Tue


def test_load_trenitalia_netex_profile_filters_products_and_days(tmp_path):
    """The narrow NeTEx reader handles the actual NAP element relationships."""
    xml = """<PublicationDelivery xmlns="http://www.netex.org.uk/netex"><dataObjects>
    <SiteFrame><stopPlaces>
      <StopPlace id="A"><Name>ALPHA</Name><Centroid><Location><Latitude>45</Latitude><Longitude>9</Longitude></Location></Centroid></StopPlace>
      <StopPlace id="B"><Name>BETA</Name><Centroid><Location><Latitude>46</Latitude><Longitude>10</Longitude></Location></Centroid></StopPlace>
    </stopPlaces><scheduledStopPoints>
      <ScheduledStopPoint id="SA"><Name>ALPHA</Name><Location><Latitude>45</Latitude><Longitude>9</Longitude></Location></ScheduledStopPoint><ScheduledStopPoint id="SB"><Name>BETA</Name><Location><Latitude>46</Latitude><Longitude>10</Longitude></Location></ScheduledStopPoint>
    </scheduledStopPoints></SiteFrame>
    <ServiceFrame><lines><Line id="FR"><ShortName>FR</ShortName><Name>Frecciarossa</Name></Line><Line id="REG"><ShortName>REG</ShortName></Line></lines>
    <journeyPatterns><ServiceJourneyPattern id="P"><RouteView><LineRef ref="FR"/></RouteView><pointsInSequence>
      <StopPointInJourneyPattern id="PA"><ScheduledStopPointRef ref="SA"/></StopPointInJourneyPattern><StopPointInJourneyPattern id="PB"><ScheduledStopPointRef ref="SB"/></StopPointInJourneyPattern>
    </pointsInSequence></ServiceJourneyPattern></journeyPatterns>
    <vehicleJourneys><ServiceJourney id="J"><Name>9500</Name><dayTypes><DayTypeRef ref="D"/></dayTypes><ServiceJourneyPatternRef ref="P"/><passingTimes>
      <TimetabledPassingTime><StopPointInJourneyPatternRef ref="PA"/><DepartureTime>23:55:00</DepartureTime><DepartureDayOffset>0</DepartureDayOffset></TimetabledPassingTime>
      <TimetabledPassingTime><StopPointInJourneyPatternRef ref="PB"/><ArrivalTime>00:15:00</ArrivalTime><ArrivalDayOffset>1</ArrivalDayOffset></TimetabledPassingTime>
    </passingTimes></ServiceJourney></vehicleJourneys></ServiceFrame>
    <ServiceCalendarFrame><operatingPeriods><UicOperatingPeriod id="O"><FromDate>2026-07-13</FromDate><ToDate>2026-07-15</ToDate><ValidDayBits>010</ValidDayBits></UicOperatingPeriod></operatingPeriods>
    <dayTypeAssignments><DayTypeAssignment><OperatingPeriodRef ref="O"/><DayTypeRef ref="D"/></DayTypeAssignment></dayTypeAssignments></ServiceCalendarFrame>
    </dataObjects></PublicationDelivery>"""
    path = tmp_path / "trenitalia.zip"
    with gzip.open(path, "wb") as out:
        out.write(xml.encode())
    cfg = FeedConfig(url="u", country="IT", license="t", format="netex", route_allow=["^FR$"])
    stops, trips = load_netex(path, cfg, SAMPLE)
    assert netex_validity_window(path) == ("20260713", "20260715")
    assert [stop.stop_id for stop in stops] == ["SA", "SB"]
    assert [(trip.train, trip.stops[-1].arr) for trip in trips] == [("FR 9500", 24 * 60 + 15)]
    assert load_netex(path, cfg, date(2026, 7, 15))[1] == []


def test_trenitalia_napoli_afragola_upstream_coordinate_is_corrected():
    assert COORDINATE_FIXES["IT::ScheduledStopPoint:otherTRENITALIA:830009988"] == (
        40.931758,
        14.331131,
    )


# --- next_tuesday: every weekday ---------------------------------------------


def test_next_tuesday_every_weekday():
    # 2026-07-06 is a Monday; walk one full week.
    for offset in range(7):
        today = date(2026, 7, 6) + timedelta(days=offset)
        result = next_tuesday(today)
        assert result.weekday() == 1
        assert result > today  # never today, even on a Tuesday
        assert (result - today).days <= 7


# --- calendar_dates.txt exceptions -------------------------------------------


def test_calendar_dates_type1_adds_service_missing_from_calendar(tmp_path):
    # Service S1 has no calendar.txt row at all; a type-1 exception alone activates it.
    zip_path = _make_feed(
        tmp_path,
        calendar_txt=None,
        calendar_dates_txt="service_id,date,exception_type\nS1,20260714,1\n",
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    assert [t.trip_id for t in trips] == ["T1"]


def test_calendar_dates_type1_overrides_calendar_weekday_zero(tmp_path):
    # calendar.txt says "never runs on Tuesday", but a type-1 exception adds the date.
    cal = (
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "S1,1,0,1,1,1,1,1,20260101,20261231\n"
    )
    zip_path = _make_feed(
        tmp_path,
        calendar_txt=cal,
        calendar_dates_txt="service_id,date,exception_type\nS1,20260714,1\n",
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    assert [t.trip_id for t in trips] == ["T1"]


def test_calendar_dates_type2_removes_service(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        calendar_dates_txt="service_id,date,exception_type\nS1,20260714,2\n",
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    assert trips == []


def test_calendar_dates_other_date_is_ignored(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        calendar_dates_txt="service_id,date,exception_type\nS1,20260715,2\n",
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    assert [t.trip_id for t in trips] == ["T1"]


# --- time parsing ------------------------------------------------------------


def test_post_midnight_times_not_wrapped(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,23:50:00,23:55:00,A,1\n"
            "T1,26:15:00,26:15:00,B,2\n"
        ),
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert trip.stops[0].dep == 23 * 60 + 55
    assert trip.stops[1].arr == 26 * 60 + 15  # 1575, no modulo 1440


def test_empty_arrival_or_departure_falls_back(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,,08:00:00,A,1\n"
            "T1,09:00:00,,B,2\n"
        ),
    )
    _, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert trip.stops[0].arr == 8 * 60 and trip.stops[0].dep == 8 * 60
    assert trip.stops[1].arr == 9 * 60 and trip.stops[1].dep == 9 * 60


def test_row_with_both_times_empty_is_skipped_with_warning(tmp_path, caplog):
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Alpha,50.0,8.0\n"
            "M,Mid,50.0,8.5\n"
            "B,Beta,50.0,9.0\n"
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A,1\n"
            "T1,,,M,2\n"
            "T1,09:00:00,09:00:00,B,3\n"
        ),
    )
    with caplog.at_level(logging.WARNING, logger="pipeline.gtfs"):
        stops, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert [s.station for s in trip.stops] == ["A", "B"]  # untimed row dropped
    assert {s.stop_id for s in stops} == {"A", "B"}
    assert any("T1" in rec.message and "M" in rec.message for rec in caplog.records)


def test_stop_at_zero_zero_is_kept_as_coordinateless_stub(tmp_path):
    """(0, 0) is a placeholder some feeds use for a foreign station they carry no
    real coordinate for (observed: ovapi/NS stubs for German stations reached by
    cross-border trains). These are NOT dropped at load -- they are the foreign
    half of a real cross-border trip. They are kept as coordinate-less stubs
    (lat/lon None), and the merge stage resolves them by name onto the real
    canonical station (or drops them there if unresolvable)."""
    zip_path = _make_feed(
        tmp_path,
        stops_txt=("stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,50.0,8.0\nB,Beta,0,0\n"),
    )
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    by_id = {s.stop_id: s for s in stops}
    assert by_id["A"].lat == 50.0 and by_id["A"].lon == 8.0
    assert by_id["B"].lat is None and by_id["B"].lon is None
    (trip,) = trips
    assert [s.station for s in trip.stops] == ["A", "B"]  # stub still in the trip


def test_stop_with_missing_coordinates_is_kept_as_stub(tmp_path):
    """An empty stop_lat/stop_lon is treated the same as (0,0): a coordinate-less
    stub, kept rather than dropped."""
    zip_path = _make_feed(
        tmp_path,
        stops_txt=("stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,50.0,8.0\nB,Beta,,\n"),
    )
    stops, _ = load_feed(zip_path, CFG, SAMPLE)
    by_id = {s.stop_id: s for s in stops}
    assert by_id["B"].lat is None and by_id["B"].lon is None


# --- filtering must not leak into stops --------------------------------------


def test_filtered_route_stops_do_not_leak(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Alpha,50.0,8.0\n"
            "B,Beta,50.0,9.0\n"
            "Z,RegionalOnly,51.0,9.0\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,IC 9,2\nR2,RB 7,2\n",
        trips_txt="route_id,service_id,trip_id\nR1,S1,T1\nR2,S1,T2\n",
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
            "T2,07:00:00,07:00:00,A,1\n"
            "T2,07:30:00,07:30:00,Z,2\n"
        ),
    )
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    assert {t.trip_id for t in trips} == {"T1"}
    assert {s.stop_id for s in stops} == {"A", "B"}  # Z used only by filtered RB 7


# --- route naming fallback ----------------------------------------------------


def test_route_long_name_used_when_short_name_empty(tmp_path):
    # Real feeds (NS "^Intercity", SNCF "^EUROSTAR") often only populate
    # route_long_name. The loader falls back to it when short_name is empty.
    cfg = FeedConfig(url="u", country="XX", license="t", route_allow=["^Intercity"])
    zip_path = _make_feed(
        tmp_path,
        routes_txt=(
            "route_id,route_short_name,route_long_name,route_type\nR1,,Intercity Direct,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips
    assert trip.train == "Intercity Direct"


def test_route_allow_matches_against_long_name_even_when_short_name_present(tmp_path):
    # SNCF: route_short_name is an opaque code ("001G"), the brand lives as a
    # trailing word in route_long_name ("Lille - Alpes TGV"). A pattern must be
    # able to match the long name even though short_name is non-empty. The
    # DISPLAY name still prefers short_name when present.
    cfg = FeedConfig(url="u", country="XX", license="t", route_allow=["\\bTGV\\b"])
    zip_path = _make_feed(
        tmp_path,
        routes_txt=(
            "route_id,route_short_name,route_long_name,route_type\nR1,001G,Lille - Alpes TGV,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips
    assert trip.train == "001G"  # display name still the short code


# --- trip-level filtering (OEBB) ---------------------------------------------


def test_trip_allow_filters_by_trip_short_name_and_relabels(tmp_path):
    # OEBB: route names are corridor codes carrying no category. route_allow lets
    # every route through; trip_allow selects long-distance trips by their
    # trip_short_name ("RJ 658") and that becomes the train label.
    cfg = FeedConfig(
        url="u",
        country="XX",
        license="t",
        route_allow=["."],
        trip_allow=["^RJ\\b", "^ICE\\b"],
    )
    zip_path = _make_feed(
        tmp_path,
        routes_txt="route_id,route_short_name,route_type\nR1,A10-1,2\n",
        trips_txt=(
            "route_id,service_id,trip_id,trip_short_name\n"
            "R1,S1,T1,RJ 658\n"
            "R1,S1,T2,REX 5\n"  # regional, filtered out
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
            "T2,07:00:00,07:00:00,A,1\n"
            "T2,07:30:00,07:30:00,B,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips
    assert trip.trip_id == "T1"
    assert trip.train == "RJ 658"  # relabeled from trip_short_name


def test_no_trip_allow_keeps_route_label(tmp_path):
    # Without trip_allow, behavior is unchanged: the route name is the label and
    # no trip_short_name filtering happens.
    _, trips = load_feed(_make_feed(tmp_path), CFG, SAMPLE)
    (trip,) = trips
    assert trip.train == "IC 9"


# --- stop-id-level filtering (SNCF) -------------------------------------------


def test_stop_id_allow_keeps_only_trips_on_matching_stop_ids(tmp_path):
    # SNCF's combined feed (TGV+Intercites+TER) marks the commercial brand ONLY
    # in the per-brand StopPoint ids ("StopPoint:OCETGV INOUI-87686006"); route
    # names carry no brand for OUIGO/Lyria/Intercites trips. stop_id_allow keeps
    # a trip only if its stop ids match one of the patterns.
    cfg = FeedConfig(
        url="u",
        country="XX",
        license="t",
        route_allow=["."],
        stop_id_allow=["^SP:OCETGV\\b", "^SP:OCEOUIGO-"],
    )
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "SP:OCETGV-1,Alpha,50.0,8.0\n"
            "SP:OCETGV-2,Beta,50.0,9.0\n"
            "SP:OCETER-1,Alpha,50.0,8.0\n"
            "SP:OCETER-3,Gamma,50.1,8.1\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,001G,2\nR2,C30,2\n",
        trips_txt="route_id,service_id,trip_id\nR1,S1,T1\nR2,S1,T2\n",
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,SP:OCETGV-1,1\n"
            "T1,09:00:00,09:00:00,SP:OCETGV-2,2\n"
            "T2,07:00:00,07:00:00,SP:OCETER-1,1\n"
            "T2,07:30:00,07:30:00,SP:OCETER-3,2\n"
        ),
    )
    stops, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips  # TER trip filtered out
    assert trip.trip_id == "T1"
    assert {s.stop_id for s in stops} == {"SP:OCETGV-1", "SP:OCETGV-2"}


# --- nested archive layout ---------------------------------------------------


def test_feed_files_nested_in_subdirectory_are_found(tmp_path):
    # OEBB ships its GTFS files under a "GTFS_Fahrplan_2026/" prefix inside the
    # zip. The loader must find e.g. "GTFS_Fahrplan_2026/stops.txt" when it looks
    # up "stops.txt".
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for fname, content in _DEFAULT_FILES.items():
            zf.writestr(f"GTFS_Fahrplan_2026/{fname}", content)
    path = tmp_path / "nested.zip"
    path.write_bytes(buf.getvalue())
    stops, trips = load_feed(path, CFG, SAMPLE)
    assert {s.stop_id for s in stops} == {"A", "B"}
    assert len(trips) == 1


# --- parent_station resolution -------------------------------------------------


def test_platform_stops_resolve_to_parent_station(tmp_path):
    # OEBB (and NS/SBB/SNCF) reference per-platform stops in stop_times
    # ("Linz/Donau Hauptbahnhof 8", parent "Pat:44:41164" = the station). Trips
    # boarding at different platforms of one station must land on ONE stop, or
    # the router can never transfer there. Resolve every used stop to its
    # topmost parent that has a stops.txt row, using the parent's id/name/coords.
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "P1,Linz Hauptbahnhof,48.2907,14.2912,1,\n"
            "A1,Linz Hauptbahnhof 1,48.2910,14.2920,0,P1\n"
            "A2,Linz Hauptbahnhof 2,48.2909,14.2921,0,P1\n"
            "B,Beta,50.0,9.0,0,\n"
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A1,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
        ),
    )
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert [s.station for s in trip.stops] == ["P1", "B"]
    by_id = {s.stop_id: s for s in stops}
    assert set(by_id) == {"P1", "B"}
    assert by_id["P1"].name == "Linz Hauptbahnhof"
    assert by_id["P1"].lat == 48.2907


def test_resolved_stop_takes_shortest_name_of_parent_and_used_children(tmp_path):
    # db_fern's parent rows sometimes carry context-free names ("Hauptbahnhof
    # (oben)" as the parent of "Stuttgart Hbf"), while OEBB's children carry
    # platform-suffixed names ("Linz Hauptbahnhof 8" under "Linz Hauptbahnhof").
    # In both feeds the RIGHT display name is the shortest one on offer, so the
    # resolved stop uses the shortest of the parent's and used children's names.
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "P1,Hauptbahnhof (oben),48.78473,9.183172,1,\n"
            "A1,Stuttgart Hbf,48.78478,9.182757,0,P1\n"
            "B,Beta,50.0,9.0,0,\n"
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A1,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
        ),
    )
    stops, _ = load_feed(zip_path, CFG, SAMPLE)
    by_id = {s.stop_id: s for s in stops}
    assert by_id["P1"].name == "Stuttgart Hbf"  # child's name is shorter
    assert by_id["P1"].lat == 48.78473  # coords stay the parent's


def test_parent_resolution_is_transitive(tmp_path):
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "TOP,Station,48.0,14.0,1,\n"
            "MID,Station Hall 1,48.0,14.0,1,TOP\n"
            "A,Station Platform 1,48.0,14.0,0,MID\n"
            "B,Beta,50.0,9.0,0,\n"
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
        ),
    )
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert trip.stops[0].station == "TOP"


def test_parent_without_row_keeps_child(tmp_path):
    # A dangling parent_station reference (no stops.txt row for it) must not
    # invent a stop with no name/coords: the child stays as-is.
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
            "A,Alpha,50.0,8.0,GHOST\n"
            "B,Beta,50.0,9.0,\n"
        ),
    )
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    (trip,) = trips
    assert [s.station for s in trip.stops] == ["A", "B"]
    assert {s.stop_id for s in stops} == {"A", "B"}


def test_zero_zero_platform_with_real_parent_becomes_real_stop(tmp_path):
    # NS carries foreign platforms at (0,0) but the parent stoparea has real
    # coordinates (e.g. stoparea:40205 "Berlin Hbf" 52.5256): after parent
    # resolution the stop is real, no stub needed.
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "SA,Berlin Hbf,52.5256,13.3694,1,\n"
            "A,Berlin Hbf,0,0,0,SA\n"
            "B,Beta,50.0,9.0,0,\n"
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,A,1\n"
            "T1,09:00:00,09:00:00,B,2\n"
        ),
    )
    stops, _ = load_feed(zip_path, CFG, SAMPLE)
    by_id = {s.stop_id: s for s in stops}
    assert by_id["SA"].lat == 52.5256 and by_id["SA"].lon == 13.3694


# --- encoding ----------------------------------------------------------------


def test_bom_in_stops_txt_is_stripped(tmp_path):
    zip_path = _make_feed(tmp_path, stops_txt="\ufeff" + _DEFAULT_FILES["stops.txt"])
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    assert {s.stop_id for s in stops} == {"A", "B"}
    assert len(trips) == 1
    assert stops[0].lat == 50.0 and stops[0].lon == 8.0


# --- fixed-width padded exports (Renfe) ---------------------------------------


def test_fixed_width_padded_feed_loads(tmp_path):
    # Evidence: the real 2026-07 Renfe export (data/raw/renfe.zip) pads EVERY
    # line -- including header rows -- to a fixed ~350-byte width with
    # trailing spaces. Discovered 2026-07-10 (Task 3 blocker): the padded
    # calendar.txt header turns the last fieldname into "end_date" plus ~300
    # spaces, so row["end_date"] raises KeyError in _active_services before
    # any row is usable. Padded cell values would also poison stop_ids/names
    # downstream, so every file (not just calendar.txt) is padded here.
    width = 350
    padded = {
        name: "\n".join(line.ljust(width) for line in content.splitlines()) + "\n"
        for name, content in _DEFAULT_FILES.items()
    }
    zip_path = _make_feed(tmp_path, **{k.replace(".txt", "_txt"): v for k, v in padded.items()})
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    assert {s.stop_id for s in stops} == {"A", "B"}
    (trip,) = trips
    assert trip.train == "IC 9"
    assert [s.station for s in trip.stops] == ["A", "B"]
    assert trip.stops[0].dep == 8 * 60 and trip.stops[1].arr == 9 * 60


# --- stop-id brand labeling (SNCF) ---------------------------------------------


def test_brand_label_first_matching_stop_wins_in_sequence_order():
    patterns = [(re.compile("^A-"), "Alpha"), (re.compile("^B-"), "Beta")]
    # First stop matches nothing, second matches the SECOND pattern: the first
    # MATCHING STOP decides (not the first pattern with any match anywhere).
    assert _brand_label(["X-1", "B-2", "A-3"], patterns, "42") == "Beta 42"
    assert _brand_label(["X-1"], patterns, "42") is None  # no brand stop
    assert _brand_label(["A-1"], patterns, "") is None  # empty headsign


def test_stop_id_brand_filters_and_labels_brand_plus_headsign(tmp_path):
    # SNCF: the brand lives only in per-brand StopPoint ids and the train number
    # only in trip_headsign. stop_id_brand's patterns act as the stop-id trip
    # filter AND relabel each kept trip "<brand> <trip_headsign>".
    cfg = FeedConfig(
        url="u",
        country="XX",
        license="t",
        route_allow=["."],
        stop_id_brand={"^SP:OCETGV INOUI-": "TGV INOUI", "^SP:OCEOUIGO-": "OUIGO"},
    )
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "SP:OCETGV INOUI-1,Alpha,50.0,8.0\n"
            "SP:OCETGV INOUI-2,Beta,50.0,9.0\n"
            "SP:OCEOUIGO-1,Alpha,50.0,8.0\n"
            "SP:OCEOUIGO-3,Gamma,50.1,8.1\n"
            "SP:OCETER-1,Alpha,50.0,8.0\n"
            "SP:OCETER-3,Gamma,50.1,8.1\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,001G,2\nR2,C30,2\nR3,C31,2\n",
        trips_txt=(
            "route_id,service_id,trip_id,trip_headsign\n"
            "R1,S1,T1,9704\n"
            "R2,S1,T2,7871\n"
            "R3,S1,T3,4402\n"  # TER stops only: filtered out
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,SP:OCETGV INOUI-1,1\n"
            "T1,09:00:00,09:00:00,SP:OCETGV INOUI-2,2\n"
            "T2,07:00:00,07:00:00,SP:OCEOUIGO-1,1\n"
            "T2,07:30:00,07:30:00,SP:OCEOUIGO-3,2\n"
            "T3,07:00:00,07:00:00,SP:OCETER-1,1\n"
            "T3,07:30:00,07:30:00,SP:OCETER-3,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    assert {t.trip_id: t.train for t in trips} == {"T1": "TGV INOUI 9704", "T2": "OUIGO 7871"}


def test_stop_id_brand_empty_headsign_falls_back_to_route_label(tmp_path):
    # 100% headsign coverage in the real export, but a feed quirk must not
    # produce a dangling "TGV INOUI " label.
    cfg = FeedConfig(
        url="u",
        country="XX",
        license="t",
        route_allow=["."],
        stop_id_brand={"^SP:OCETGV-": "TGV INOUI"},
    )
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "SP:OCETGV-1,Alpha,50.0,8.0\n"
            "SP:OCETGV-2,Beta,50.0,9.0\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,001G,2\n",
        trips_txt="route_id,service_id,trip_id,trip_headsign\nR1,S1,T1,\n",
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,SP:OCETGV-1,1\n"
            "T1,09:00:00,09:00:00,SP:OCETGV-2,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips
    assert trip.train == "001G"
