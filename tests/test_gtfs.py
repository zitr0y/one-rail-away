"""Tests for pipeline.gtfs: feed loading, service-day logic, and long-distance filtering."""

import io
import logging
import zipfile
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import FeedConfig
from pipeline.gtfs import load_feed, next_tuesday
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)  # a Tuesday

CFG = FeedConfig(url="u", country="XX", license="t", route_allow=["^IC\\b"])

CAL_ALL_DAYS = (
    "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
    "S1,1,1,1,1,1,1,1,20260101,20261231\n"
)

_DEFAULT_FILES = {
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "A,Alpha,50.0,8.0\n"
        "B,Beta,50.0,9.0\n"
    ),
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
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Alpha,50.0,8.0\n"
            "B,Beta,0,0\n"
        ),
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
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Alpha,50.0,8.0\n"
            "B,Beta,,\n"
        ),
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
            "route_id,route_short_name,route_long_name,route_type\n"
            "R1,,Intercity Direct,2\n"
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
            "route_id,route_short_name,route_long_name,route_type\n"
            "R1,001G,Lille - Alpes TGV,2\n"
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
        url="u", country="XX", license="t",
        route_allow=["."], trip_allow=["^RJ\\b", "^ICE\\b"],
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


# --- encoding ----------------------------------------------------------------


def test_bom_in_stops_txt_is_stripped(tmp_path):
    zip_path = _make_feed(tmp_path, stops_txt="\ufeff" + _DEFAULT_FILES["stops.txt"])
    stops, trips = load_feed(zip_path, CFG, SAMPLE)
    assert {s.stop_id for s in stops} == {"A", "B"}
    assert len(trips) == 1
    assert stops[0].lat == 50.0 and stops[0].lon == 8.0
