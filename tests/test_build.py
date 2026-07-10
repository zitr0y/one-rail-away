import json
import logging
from datetime import date

import pytest

from pipeline.build import build, remap_trips, validate
from pipeline.models import Station, StopTime, Trip
from tests.fixtures import make_fixture_feeds

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


def test_build_produces_merged_graph(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    # Pass empty station_countries_path so the real pipeline/station_countries.toml
    # (which has prod station IDs absent from fixtures) doesn't trip stale-id validation.
    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text("[countries]\n")
    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_countries_path=countries_toml,
    )

    stations = json.loads((graph / "stations.json").read_text())
    ids = {s["id"] for s in stations["stations"]}
    assert ids == {"1111111", "2222222", "3333333", "4444444"}  # Gamma merged once

    trips = json.loads((graph / "trips.json").read_text())["trips"]
    tgv = next(t for t in trips if t["train"] == "TGV 10")
    assert [s["station"] for s in tgv["stops"]] == ["3333333", "4444444"]


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
# merge + country assignment, mirroring station_countries.toml exactly
# (same loading pattern, same stale-id validation). Spec:
# docs/superpowers/specs/2026-07-10-renfe-feed-design.md §3.


def test_station_names_override_applied(tmp_path):
    """A station_names.toml entry replaces the merged display name."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    # Gamma Hbf's canonical id is "3333333" (UIC merge from fixtures).
    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text('[names]\n"3333333" = "Gamma Zentral"\n')

    # Pass empty station_countries_path so prod keys don't trip stale-id validation.
    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text("[countries]\n")

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


def test_station_names_stale_id_fails_build(tmp_path):
    """A station_names.toml key not matching any station id must fail the build."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text('[names]\n"GHOST_ID" = "Phantom"\n')

    graph = tmp_path / "graph"
    with pytest.raises(SystemExit):
        build(
            raw,
            graph,
            feeds_toml,
            aliases_path=None,
            sample_date=SAMPLE,
            station_names_path=names_toml,
        )


def test_station_countries_stale_id_fails_build(tmp_path):
    """Align station_countries.toml: a stale override key must also fail the build.

    Today station_countries.toml silently ignores unknown keys. The spec requires
    BOTH override files to fail loudly on stale ids (Konstanz precedent).
    """
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    # Write a station_countries.toml with a key that doesn't match any station.
    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text('[countries]\n"GHOST_ID" = "XX"\n')

    graph = tmp_path / "graph"
    with pytest.raises(SystemExit):
        build(
            raw,
            graph,
            feeds_toml,
            aliases_path=None,
            sample_date=SAMPLE,
            station_countries_path=countries_toml,
        )
