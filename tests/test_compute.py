import json
from datetime import date

from pipeline.build import build
from pipeline.capitals import load_capitals
from pipeline.compute import compute_all, route_counts
from pipeline.models import StopTime, Trip
from pipeline.sampling import service_week_dates
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides

SAMPLE = date(2026, 7, 14)


def test_compute_all_writes_reach_files(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)

    reach = json.loads((tmp_path / "out" / "reach_1111111.json").read_text())
    beta = next(d for d in reach["destinations"] if d["id"] == "2222222")
    assert beta["direct_per_day"] == 2  # IC 100 + IC 101
    assert beta["journeys"][0]["legs"][0]["from"] == "1111111"  # alias serialization

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    delta = next(s for s in stations["stations"] if s["id"] == "4444444")
    assert alpha["has_reach"] is True and delta["has_reach"] is False

    meta = json.loads((tmp_path / "out" / "meta.json").read_text())
    assert meta["sample_date"] == "2026-07-14" and "computed_at" in meta


def test_compute_all_prunes_stale_reach_files(tmp_path):
    # A station whose canonical id changed between runs (Konstanz alias, 2026-07-09)
    # leaves its old reach file behind; the server derives has_reach from files on
    # disk, so a stale file resurrects a dead station in search. Prune it.
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "reach_9999999.json"
    stale.write_text("{}")
    compute_all(tmp_path / "graph", out, workers=1, feeds_path=feeds_toml)
    assert not stale.exists()
    assert (out / "reach_1111111.json").exists()  # fresh files kept


def test_compute_all_parallel_matches_serial(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "serial", workers=1, feeds_path=feeds_toml)
    compute_all(tmp_path / "graph", tmp_path / "par", workers=2, feeds_path=feeds_toml)

    def reach_files(d):  # computed_at differs across runs (not within), drop it
        return {
            p.name: {k: v for k, v in json.loads(p.read_text()).items() if k != "computed_at"}
            for p in d.glob("reach_*.json")
        }

    serial, par = reach_files(tmp_path / "serial"), reach_files(tmp_path / "par")
    assert serial and serial == par
    s_stations = json.loads((tmp_path / "serial" / "stations.json").read_text())
    p_stations = json.loads((tmp_path / "par" / "stations.json").read_text())
    assert s_stations == p_stations  # has_reach flags identical


def test_compute_all_writes_n_dest(tmp_path):
    """n_dest on each station equals the destination count from its reach file."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    delta = next(s for s in stations["stations"] if s["id"] == "4444444")
    # Alpha reaches Beta, Gamma, Delta → 3 destinations
    assert alpha["n_dest"] == 3
    # Delta has no reach
    assert delta["n_dest"] == 0
    # n_routes counts distinct trip endpoint pairs calling at the station;
    # every fixture station lies on at least one trip, so all are >= 1
    assert alpha["n_routes"] >= 1
    assert all(s["n_routes"] >= 1 for s in stations["stations"])


def test_compute_all_sets_is_capital(tmp_path):
    """is_capital is set for stations matching capitals.toml entries."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    countries_toml.write_text('[countries]\n1111111 = "LA"\n')
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    # Write a capitals.toml that matches Alpha Hbf in Landia (country=LA)
    (tmp_path / "capitals.toml").write_text('[capitals]\nLA = "Alpha Hbf"\n')
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)
    finally:
        os.chdir(old_cwd)

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    beta = next(s for s in stations["stations"] if s["id"] == "2222222")
    assert alpha["is_capital"] is True
    assert beta["is_capital"] is False


def test_load_capitals_warns_on_unmatched(tmp_path):
    """An entry in capitals.toml that matches no station produces a warning, not an error."""
    from pipeline.models import Station

    toml_path = tmp_path / "capitals.toml"
    toml_path.write_text('[capitals]\nXX = "Nonexistent Station"\nLA = "Alpha Hbf"\n')
    stations = [
        Station(id="1111111", name="Alpha Hbf", lat=50, lon=8, country="LA"),
    ]
    ids, warnings = load_capitals(toml_path, stations)
    assert ids == {"1111111"}
    assert len(warnings) == 1
    assert "XX" in warnings[0] and "Nonexistent" in warnings[0]


def test_load_capitals_missing_file(tmp_path):
    """Missing capitals.toml returns empty set and no warnings (graceful)."""
    ids, warnings = load_capitals(tmp_path / "nope.toml", [])
    assert ids == set()
    assert warnings == []


def test_compute_aggregates_independent_sample_days_and_frequency(tmp_path):
    """A seasonal trip contributes evidence, but cannot join a different day's trip."""
    graph = tmp_path / "graph"
    graph.mkdir()
    graph.joinpath("stations.json").write_text(
        json.dumps(
            {
                "sample_date": "2026-01-13",
                "sample_dates": ["2026-01-13", "2026-07-14"],
                "stations": [
                    {"id": "A", "name": "Alpha", "lat": 50, "lon": 8, "country": "XX"},
                    {"id": "B", "name": "Beta", "lat": 51, "lon": 9, "country": "XX"},
                    {"id": "C", "name": "Gamma", "lat": 52, "lon": 10, "country": "XX"},
                ],
            }
        )
    )
    jan = Trip(
        trip_id="jan",
        train="IC Jan",
        stops=[
            StopTime(station="A", arr=480, dep=480),
            StopTime(station="B", arr=540, dep=540),
        ],
    )
    jul = Trip(
        trip_id="jul",
        train="IC Jul",
        stops=[
            StopTime(station="B", arr=560, dep=560),
            StopTime(station="C", arr=620, dep=620),
        ],
    )
    graph.joinpath("trips.json").write_text(
        json.dumps(
            {
                "trips_by_date": {
                    "2026-01-13": [jan.model_dump()],
                    "2026-07-14": [jul.model_dump()],
                },
                "trips": [jan.model_dump()],
            }
        )
    )
    compute_all(graph, tmp_path / "out", workers=1, feeds_path=tmp_path / "no-feeds.toml")
    reach = json.loads((tmp_path / "out" / "reach_A.json").read_text())
    assert [d["id"] for d in reach["destinations"]] == ["B"]  # never cross-date A→B→C
    frequency = reach["destinations"][0]["frequency"]
    assert frequency == {
        "requested_sample_days": 2,
        "sample_days": 2,
        "available_days": 1,
        "direct_days": 1,
        "direct_trips": 1,
        "direct_per_active_day": 1.0,
        "weekly_direct_estimate": 4,
        "availability": "coverage_limited",
        "seasonal": False,
        "active_months": ["Jan"],
    }


def test_compute_ignores_probes_outside_a_route_feeds_validity_window(tmp_path):
    """A narrow downloaded feed must not make its normal route look seasonal."""
    graph = tmp_path / "graph"
    graph.mkdir()
    dates = ["2026-01-13", "2026-04-14", "2026-07-14", "2026-10-13"]
    graph.joinpath("stations.json").write_text(
        json.dumps(
            {
                "sample_date": dates[0],
                "sample_dates": dates,
                "stations": [
                    {"id": "A", "name": "Alpha", "lat": 50, "lon": 8, "country": "XX"},
                    {"id": "B", "name": "Beta", "lat": 51, "lon": 9, "country": "XX"},
                ],
            }
        )
    )
    trip = Trip(
        trip_id="normal",
        train="IC",
        feeds=["narrow"],
        stops=[
            StopTime(station="A", arr=480, dep=480),
            StopTime(station="B", arr=540, dep=540),
        ],
    )
    graph.joinpath("trips.json").write_text(
        json.dumps(
            {
                "trips": [trip.model_dump()],
                "trips_by_date": {
                    day: [trip.model_dump()] if day == dates[0] else [] for day in dates
                },
                "feed_validity_by_date": {
                    day: {
                        "narrow": {
                            "covered": day == dates[0],
                            "start_date": "20260101",
                            "end_date": "20260131",
                        },
                        # An unrelated feed remains usable for every probe.
                        # Its coverage must not inflate narrow's denominator.
                        "broad": {
                            "covered": True,
                            "start_date": "20260101",
                            "end_date": "20261231",
                        },
                    }
                    for day in dates
                },
            }
        )
    )
    compute_all(graph, tmp_path / "out", workers=1, feeds_path=tmp_path / "no-feeds.toml")
    reach = json.loads((tmp_path / "out" / "reach_A.json").read_text())
    frequency = reach["destinations"][0]["frequency"]
    assert frequency["requested_sample_days"] == 4
    assert frequency["sample_days"] == frequency["available_days"] == 1
    assert frequency["availability"] == "coverage_limited"


def test_route_counts_deduplicates_the_same_endpoint_pair_across_sample_dates(tmp_path):
    trip = Trip(
        trip_id="jan",
        train="IC",
        stops=[
            StopTime(station="A", arr=480, dep=480),
            StopTime(station="B", arr=540, dep=540),
        ],
    ).model_dump()
    trips = tmp_path / "trips.json"
    trips.write_text(
        json.dumps(
            {
                "trips": [trip],
                "trips_by_date": {"2026-01-13": [trip], "2026-07-14": [trip]},
            }
        )
    )
    assert route_counts(trips) == {"A": 1, "B": 1}


def test_service_week_is_deterministic_and_respects_feed_coverage():
    dates = service_week_dates(date(2026, 7, 14))
    assert [d.isoformat() for d in dates] == [
        "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
        "2026-07-17", "2026-07-18", "2026-07-19",
    ]
    short_window = service_week_dates(date(2026, 7, 14), ("20260716", "20260721"))
    assert [d.isoformat() for d in short_window] == [
        "2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19", "2026-07-20", "2026-07-21",
    ]


def test_compute_keeps_inactive_seasonal_trip_visible_and_labeled(tmp_path):
    graph = tmp_path / "graph"
    graph.mkdir()
    dates = [f"2026-07-{day:02d}" for day in range(13, 20)]
    graph.joinpath("stations.json").write_text(json.dumps({
        "sample_date": dates[0], "sample_dates": dates,
        "stations": [
            {"id": "A", "name": "Alpha", "lat": 50, "lon": 8, "country": "XX"},
            {"id": "B", "name": "Beta", "lat": 51, "lon": 9, "country": "XX"},
        ],
    }))
    seasonal = Trip(
        trip_id="winter", train="Night", feeds=["rail"], seasonal=True,
        stops=[StopTime(station="A", arr=480, dep=480), StopTime(station="B", arr=540, dep=540)],
    )
    graph.joinpath("trips.json").write_text(json.dumps({
        "trips": [], "trips_by_date": {day: [] for day in dates},
        "seasonal_trips": [seasonal.model_dump()],
        "feed_validity_by_date": {
            day: {"rail": {"covered": True, "sampled": True}} for day in dates
        },
    }))
    compute_all(graph, tmp_path / "out", workers=1, feeds_path=tmp_path / "no-feeds.toml")
    reach = json.loads((tmp_path / "out" / "reach_A.json").read_text())
    frequency = reach["destinations"][0]["frequency"]
    assert frequency["seasonal"] is True
    assert frequency["availability"] == "seasonal_or_limited"
    assert frequency["direct_trips"] == 0
