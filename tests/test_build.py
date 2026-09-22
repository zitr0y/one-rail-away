import json
import logging
from datetime import date

from pipeline.build import build, remap_trips, validate
from pipeline.models import Station, StopTime, Trip
from tests.fixtures import LANDIA, _zip, make_fixture_feeds

SAMPLE = date(2026, 7, 14)


def _write_feeds_toml(tmp_path, cfgs):
    lines = []
    for name, c in cfgs.items():
        # route_allow/uic_regex hold regex patterns (e.g. "^IC\\b") whose backslashes
        # must be doubled so TOML's own string-escape parsing round-trips them intact
        # (an unescaped "\b" is TOML's backspace escape, not a literal backslash-b).
        allow = ", ".join(f'"{p}"'.replace("\\", "\\\\") for p in c.route_allow)
        lines += [
            f"[feeds.{name}]",
            f'url = "{c.url}"',
            f'country = "{c.country}"',
            f'license = "{c.license}"',
            f"route_allow = [{allow}]",
        ]
        if c.uic_regex:
            lines.append(f'uic_regex = "{c.uic_regex}"'.replace("\\", "\\\\"))
    p = tmp_path / "feeds.toml"
    p.write_text("\n".join(lines))
    return p


def empty_overrides(tmp_path):
    """Empty coordinate-country and id-keyed name override files."""
    countries = tmp_path / "empty_countries.toml"
    countries.write_text("# No country overrides.\n")
    names = tmp_path / "empty_names.toml"
    names.write_text("[names]\n")
    return countries, names


def test_build_produces_merged_graph(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    countries_toml, names_toml = empty_overrides(tmp_path)
    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )

    stations = json.loads((graph / "stations.json").read_text())
    ids = {s["id"] for s in stations["stations"]}
    assert ids == {"1111111", "2222222", "3333333", "4444444"}  # Gamma merged once

    trips = json.loads((graph / "trips.json").read_text())["trips"]
    tgv = next(t for t in trips if t["train"] == "TGV 10")
    assert [s["station"] for s in tgv["stops"]] == ["3333333", "4444444"]


def test_build_skips_each_feeds_out_of_coverage_probes(tmp_path, caplog):
    """A narrow feed must not be parsed or represented as a zero-service day."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    narrow = dict(LANDIA)
    narrow["calendar.txt"] = narrow["calendar.txt"].replace("20261231", "20260131")
    (raw / "landia.zip").write_bytes(_zip(narrow))
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    countries_toml, names_toml = empty_overrides(tmp_path)
    graph = tmp_path / "graph"
    dates = [date(2026, 1, 13), date(2026, 7, 14)]

    with caplog.at_level(logging.WARNING, logger="pipeline.build"):
        build(
            raw,
            graph,
            feeds_toml,
            aliases_path=None,
            sample_date=dates[0],
            sample_dates=dates,
            station_names_path=names_toml,
            station_countries_path=countries_toml,
            workers=1,
        )

    payload = json.loads((graph / "trips.json").read_text())
    assert payload["feed_validity_by_date"]["2026-01-13"]["landia"]["covered"] is True
    assert payload["feed_validity_by_date"]["2026-07-14"]["landia"]["covered"] is False
    assert {trip["trip_id"] for trip in payload["trips_by_date"]["2026-07-14"]} == {"TT10"}
    assert any(
        "landia" in record.message and "2026-07-14" in record.message
        for record in caplog.records
    )


def test_parallel_feed_loading_matches_serial_graph(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    countries_toml, names_toml = empty_overrides(tmp_path)
    dates = [date(2026, 1, 13), date(2026, 7, 14)]
    serial, parallel = tmp_path / "serial", tmp_path / "parallel"
    kwargs = {
        "aliases_path": None,
        "sample_date": dates[0],
        "sample_dates": dates,
        "station_names_path": names_toml,
        "station_countries_path": countries_toml,
    }

    build(raw, serial, feeds_toml, workers=1, **kwargs)
    build(raw, parallel, feeds_toml, workers=2, **kwargs)

    for filename in ("stations.json", "trips.json"):
        serial_json = json.loads((serial / filename).read_text())
        parallel_json = json.loads((parallel / filename).read_text())
        assert serial_json == parallel_json


def test_remap_strips_stops_absent_from_mapping(caplog):
    # A stop whose (feed, stop_id) is missing from the mapping is an unresolved
    # stub the merge stage dropped: strip it from the trip, keep the rest.
    trip = Trip(
        trip_id="T",
        train="ICE 1",
        stops=[
            StopTime(station="a1", arr=0, dep=0),
            StopTime(station="stub", arr=30, dep=30),
            StopTime(station="a2", arr=60, dep=60),
        ],
    )
    mapping = {("de", "a1"): "111", ("de", "a2"): "222"}  # no ("de", "stub")
    with caplog.at_level(logging.WARNING, logger="pipeline.build"):
        kept = remap_trips({"de": [trip]}, mapping)
    (out,) = kept
    assert [s.station for s in out.stops] == ["111", "222"]
    assert any("stub" in r.message for r in caplog.records)


def test_remap_never_mutates_input_trips():
    # build() remaps the same mapping over per-day trip lists; nothing guards
    # against a caller passing the same Trip object twice, so remapping must
    # return fresh instances (a mutated input would re-remap canonical ids to
    # None and strip every stop on the second pass).
    trip = Trip(
        trip_id="T",
        train="ICE 1",
        stops=[StopTime(station="a1", arr=0, dep=0), StopTime(station="a2", arr=60, dep=60)],
    )
    mapping = {("de", "a1"): "111", ("de", "a2"): "222"}
    first = remap_trips({"de": [trip]}, mapping)
    assert [s.station for s in trip.stops] == ["a1", "a2"]  # input untouched
    second = remap_trips({"de": [trip]}, mapping)
    assert [s.station for s in second[0].stops] == ["111", "222"]
    assert first[0].stops is not trip.stops


def test_remap_drops_trip_left_with_fewer_than_two_stops(caplog):
    trip = Trip(
        trip_id="T",
        train="ICE 1",
        stops=[
            StopTime(station="stub1", arr=0, dep=0),
            StopTime(station="a1", arr=30, dep=30),
            StopTime(station="stub2", arr=60, dep=60),
        ],
    )
    mapping = {("de", "a1"): "111"}  # both stubs unresolved -> only 1 stop remains
    with caplog.at_level(logging.WARNING, logger="pipeline.build"):
        kept = remap_trips({"de": [trip]}, mapping)
    assert kept == []
    assert any("T" in r.message and "dropping trip" in r.message for r in caplog.records)


def test_validate_flags_nonsense():
    bad_station = Station(id="1", name="Zero", lat=0.0, lon=0.0, country="XX")
    bad_trip = Trip(
        trip_id="t",
        train="IC 1",
        stops=[StopTime(station="1", arr=600, dep=600), StopTime(station="2", arr=500, dep=500)],
    )
    problems = validate([bad_station], [bad_trip])
    assert any("0,0" in p for p in problems) and any("non-increasing" in p for p in problems)


# --- station_names.toml display-name overrides --------------------------------
#
# pipeline/station_names.toml overrides canonical station display names after
# merge + country assignment. Name overrides remain id-keyed while country
# overrides are coordinate-keyed. Spec:
# docs/superpowers/specs/2026-07-10-renfe-feed-design.md §3.


def test_station_names_override_applied(tmp_path):
    """A station_names.toml entry replaces the merged display name."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    # Gamma Hbf's canonical id is "3333333" (UIC merge from fixtures).
    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text('[names]\n"3333333" = "Gamma Zentral"\n')

    countries_toml, _ = empty_overrides(tmp_path)

    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )

    stations = json.loads((graph / "stations.json").read_text())
    gamma = next(s for s in stations["stations"] if s["id"] == "3333333")
    assert gamma["name"] == "Gamma Zentral"


def _build_fixture(tmp_path, *, names="", aliases=""):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text("[names]\n" + names)
    aliases_toml = tmp_path / "station_aliases.toml"
    aliases_toml.write_text("[aliases]\n" + aliases)
    countries_toml, _ = empty_overrides(tmp_path)
    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=aliases_toml,
        sample_date=SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    stations = json.loads((graph / "stations.json").read_text())["stations"]
    issues = json.loads((graph / "build_issues.json").read_text())
    return stations, issues


def test_station_names_stale_key_is_reported_not_fatal(tmp_path):
    """A stale key must not freeze the weekly refresh; it lands in build_issues."""
    stations, issues = _build_fixture(tmp_path, names='"GHOST_ID" = "Phantom"\n')
    assert "Phantom" not in {s["name"] for s in stations}
    assert issues["issues"] == [
        {"kind": "stale_override", "detail": "station_names.toml key 'GHOST_ID' matches no station"}
    ]


def test_station_names_name_keyed_override_follows_the_feed_stop(tmp_path):
    stations, issues = _build_fixture(tmp_path, names='"borderia@Delta Gare" = "Delta Zentrum"\n')
    assert "Delta Zentrum" in {s["name"] for s in stations}
    assert issues["issues"] == []


def test_unmerged_duplicate_is_reported_and_build_still_publishes(tmp_path):
    """Force a same-name twin: alias borderia's Gamma off the UIC merge, then
    rename it to landia's name. Validation must report, not abort."""
    stations, issues = _build_fixture(
        tmp_path,
        aliases='"borderia:bs-3333333" = "GHOST"\n',
        names='"GHOST" = "Gamma Hbf"\n',
    )
    assert [s["name"] for s in stations].count("Gamma Hbf") == 2
    assert issues["issues"] == [
        {"kind": "unmerged_duplicate", "detail": "3333333 / GHOST (Gamma Hbf)"}
    ]


def test_unresolved_alias_reference_is_reported(tmp_path):
    _, issues = _build_fixture(tmp_path, aliases='"borderia@Renamed Station" = "3333333"\n')
    assert issues["issues"] == [
        {"kind": "alias", "detail": "alias key 'borderia@Renamed Station' matches no stop"}
    ]


def test_station_countries_unmatched_override_warns_not_aborts(tmp_path, capsys):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text(
        '[[override]]\n'
        'name = "Ghost station"\n'
        "lat = 0.0\n"
        "lon = 0.0\n"
        'country = "XX"\n'
    )

    _, names_toml = empty_overrides(tmp_path)

    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )

    output = capsys.readouterr().out
    assert (
        "country: unused override 'Ghost station' (0.000000, 0.000000): "
        "no station within 500m"
    ) in output
    assert (graph / "stations.json").exists()
    assert (graph / "trips.json").exists()


def test_munchen_ostbahnhof_rename_does_not_affect_graz():
    import tomllib
    from pathlib import Path

    from pipeline.merge import _name_ref, _norm

    names_path = Path(__file__).parent.parent / "pipeline" / "station_names.toml"
    name_overrides = tomllib.loads(names_path.read_text()).get("names", {})
    key = next(k for k, v in name_overrides.items() if v == "München Ostbahnhof")

    # Feed-scoped and normalized-name keyed: db_fern's bare "Ostbahnhof" only.
    assert _name_ref(key) == ("db_fern", _norm("Ostbahnhof"))  # "~lat,lon" hint ignored
    assert _name_ref(key) != ("oebb", _norm("Graz Ostbahnhof"))
    assert _norm("Graz Ostbahnhof") != _norm("Ostbahnhof")
