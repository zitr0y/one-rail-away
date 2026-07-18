import gzip
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


def _write_transfer_graph(tmp_path, include_transfer):
    graph = tmp_path / "graph"
    graph.mkdir(exist_ok=True)
    stations = [
        {"id": "origin", "name": "Origin", "lat": 50, "lon": 8, "country": "XX"},
        {
            "id": "south",
            "name": "South Terminal",
            "lat": 50.1,
            "lon": 8.1,
            "country": "XX",
        },
        {
            "id": "north",
            "name": "North Terminal",
            "lat": 50.2,
            "lon": 8.2,
            "country": "XX",
        },
        {
            "id": "destination",
            "name": "Destination",
            "lat": 51,
            "lon": 9,
            "country": "XX",
        },
    ]
    graph.joinpath("stations.json").write_text(
        json.dumps({"sample_date": "2026-07-14", "stations": stations})
    )
    trips = [
        Trip(
            trip_id="to-south",
            train="IC South",
            stops=[
                StopTime(station="origin", arr=480, dep=480),
                StopTime(station="south", arr=600, dep=600),
            ],
        ),
        Trip(
            trip_id="from-north",
            train="IC North",
            stops=[
                StopTime(station="north", arr=630, dep=630),
                StopTime(station="destination", arr=690, dep=690),
            ],
        ),
    ]
    graph.joinpath("trips.json").write_text(
        json.dumps(
            {
                "trips": [trip.model_dump() for trip in trips],
                "trips_by_date": {"2026-07-14": [trip.model_dump() for trip in trips]},
            }
        )
    )
    cities_path = tmp_path / ("with-transfer.toml" if include_transfer else "no-transfer.toml")
    cities_path.write_text(
        '[cities]\nMetroville = ["South Terminal", "North Terminal"]\n'
        + (
            '\n[transfers]\nMetroville = [["South Terminal", "North Terminal", "metro", 20]]\n'
            if include_transfer
            else ""
        )
    )
    return graph, cities_path


def _write_two_date_graph(tmp_path, trips_by_date, extra_trips=None, include_transfer=False):
    graph = tmp_path / "graph"
    graph.mkdir()
    stations = [
        {"id": "origin", "name": "Origin", "lat": 50, "lon": 8, "country": "XX"},
        {
            "id": "junction",
            "name": "Junction",
            "lat": 50.1,
            "lon": 8.1,
            "country": "XX",
        },
        {
            "id": "south",
            "name": "South Terminal",
            "lat": 50.2,
            "lon": 8.2,
            "country": "XX",
        },
        {
            "id": "north",
            "name": "North Terminal",
            "lat": 50.3,
            "lon": 8.3,
            "country": "XX",
        },
        {
            "id": "destination",
            "name": "Destination",
            "lat": 51,
            "lon": 9,
            "country": "XX",
        },
    ]
    sample_dates = list(trips_by_date)
    graph.joinpath("stations.json").write_text(
        json.dumps({"sample_date": sample_dates[0], "stations": stations})
    )
    graph.joinpath("trips.json").write_text(
        json.dumps(
            {
                "trips": [
                    trip.model_dump()
                    for trips in trips_by_date.values()
                    for trip in trips
                ],
                "trips_by_date": {
                    day: [trip.model_dump() for trip in trips]
                    for day, trips in trips_by_date.items()
                },
                "extra_trips": [trip.model_dump() for trip in extra_trips or []],
            }
        )
    )
    cities_path = tmp_path / "cities.toml"
    cities_path.write_text(
        '[cities]\nMetroville = ["South Terminal", "North Terminal"]\n'
        + (
            '\n[transfers]\nMetroville = [["South Terminal", "North Terminal", "metro", 20]]\n'
            if include_transfer
            else ""
        )
    )
    return graph, cities_path


def test_compute_writes_exact_two_date_hourly_histogram_without_changing_frequency(tmp_path):
    trips_by_date = {
        "2026-07-14": [
            Trip(
                trip_id="tuesday-midnight",
                train="Tuesday Midnight",
                stops=[
                    StopTime(station="origin", arr=15, dep=15),
                    StopTime(station="destination", arr=75, dep=75),
                ],
            ),
            Trip(
                trip_id="tuesday-morning",
                train="Tuesday Morning",
                stops=[
                    StopTime(station="origin", arr=705, dep=705),
                    StopTime(station="destination", arr=765, dep=765),
                ],
            ),
            Trip(
                trip_id="tuesday-afternoon",
                train="Tuesday Afternoon",
                stops=[
                    StopTime(station="origin", arr=725, dep=725),
                    StopTime(station="destination", arr=785, dep=785),
                ],
            ),
        ],
        "2026-07-15": [
            Trip(
                trip_id="wednesday-evening",
                train="Wednesday Evening",
                stops=[
                    StopTime(station="origin", arr=1110, dep=1110),
                    StopTime(station="destination", arr=1170, dep=1170),
                ],
            ),
        ],
    }
    graph, cities_path = _write_two_date_graph(tmp_path, trips_by_date)

    compute_all(
        graph,
        tmp_path / "out",
        workers=1,
        feeds_path=tmp_path / "no-feeds.toml",
        cities_path=cities_path,
    )

    reach = json.loads((tmp_path / "out" / "reach_origin.json").read_text())
    destination = next(d for d in reach["destinations"] if d["id"] == "destination")
    histogram = destination["histogram"]
    assert list(histogram) == ["2026-07-14", "2026-07-15"]
    assert all(len(row) == 24 for row in histogram.values())
    assert histogram == {
        "2026-07-14": [1 if hour in {0, 11, 12} else 0 for hour in range(24)],
        "2026-07-15": [1 if hour == 18 else 0 for hour in range(24)],
    }
    assert destination["direct_per_day"] == 2
    assert destination["frequency"]["direct_trips"] == 4
    assert destination["frequency"]["direct_days"] == 2
    assert destination["frequency"]["direct_per_active_day"] == 2.0


def test_compute_histogram_counts_a_routed_footpath_departure_once(tmp_path):
    trips_by_date = {
        "2026-07-14": [
            Trip(
                trip_id="to-south",
                train="To South",
                stops=[
                    StopTime(station="origin", arr=480, dep=480),
                    StopTime(station="south", arr=600, dep=600),
                ],
            ),
            Trip(
                trip_id="first-onward",
                train="First Onward",
                stops=[
                    StopTime(station="north", arr=630, dep=630),
                    StopTime(station="destination", arr=690, dep=690),
                ],
            ),
            Trip(
                trip_id="second-onward",
                train="Second Onward",
                stops=[
                    StopTime(station="north", arr=640, dep=640),
                    StopTime(station="destination", arr=700, dep=700),
                ],
            ),
        ]
    }
    graph, cities_path = _write_two_date_graph(
        tmp_path, trips_by_date, include_transfer=True
    )

    compute_all(
        graph,
        tmp_path / "out",
        workers=1,
        feeds_path=tmp_path / "no-feeds.toml",
        cities_path=cities_path,
    )

    reach = json.loads((tmp_path / "out" / "reach_origin.json").read_text())
    destination = next(d for d in reach["destinations"] if d["id"] == "destination")
    assert sum(destination["histogram"]["2026-07-14"]) == 1
    assert destination["histogram"]["2026-07-14"][8] == 1
    assert destination["direct_per_day"] == 0
    assert destination["frequency"]["direct_trips"] == 0
    assert destination["journeys"][0]["trains"] == 2


def test_compute_omits_histogram_for_extra_only_destination(tmp_path):
    trips_by_date = {"2026-07-14": [], "2026-07-15": []}
    extra_trips = [
        Trip(
            trip_id="extra-direct",
            train="Extra Direct",
            stops=[
                StopTime(station="origin", arr=480, dep=480),
                StopTime(station="destination", arr=540, dep=540),
            ],
        )
    ]
    graph, cities_path = _write_two_date_graph(tmp_path, trips_by_date, extra_trips)

    compute_all(
        graph,
        tmp_path / "out",
        workers=1,
        feeds_path=tmp_path / "no-feeds.toml",
        cities_path=cities_path,
    )

    reach = json.loads((tmp_path / "out" / "reach_origin.json").read_text())
    destination = next(d for d in reach["destinations"] if d["id"] == "destination")
    assert destination["direct_per_day"] == 0
    assert "histogram" not in destination


def test_compute_all_writes_two_train_journey_with_transfer_leg(tmp_path):
    graph, no_transfer_path = _write_transfer_graph(tmp_path, include_transfer=False)
    compute_all(
        graph,
        tmp_path / "without-transfer",
        workers=1,
        feeds_path=tmp_path / "no-feeds.toml",
        cities_path=no_transfer_path,
    )
    without = tmp_path / "without-transfer" / "reach_origin.json"
    assert not without.exists() or all(
        destination["id"] != "destination"
        for destination in json.loads(without.read_text())["destinations"]
    )

    _, transfer_path = _write_transfer_graph(tmp_path, include_transfer=True)
    compute_all(
        graph,
        tmp_path / "with-transfer",
        workers=1,
        feeds_path=tmp_path / "no-feeds.toml",
        cities_path=transfer_path,
    )
    reach = json.loads((tmp_path / "with-transfer" / "reach_origin.json").read_text())
    destination = next(d for d in reach["destinations"] if d["id"] == "destination")
    journey = destination["journeys"][0]
    assert journey["trains"] == 2
    assert journey["duration_min"] == 210
    assert journey["legs"][1] == {
        "type": "transfer",
        "mode": "metro",
        "minutes": 20,
        "from_id": "south",
        "to_id": "north",
    }
    assert len(journey["legs"]) == 3
    assert all(
        set(leg) == {"train", "dep", "arr", "from", "to", "via"}
        for leg in (journey["legs"][0], journey["legs"][2])
    )
    assert destination["direct_per_day"] == 0
    assert destination["frequency"]["direct_trips"] == 0


def test_compute_all_transfer_route_matches_in_parallel(tmp_path):
    graph, cities_path = _write_transfer_graph(tmp_path, include_transfer=True)
    common = {"feeds_path": tmp_path / "no-feeds.toml", "cities_path": cities_path}
    compute_all(graph, tmp_path / "serial", workers=1, **common)
    compute_all(graph, tmp_path / "parallel", workers=2, **common)

    def reach_files(out_dir):
        return {
            path.name: {
                key: value
                for key, value in json.loads(path.read_text()).items()
                if key != "computed_at"
            }
            for path in out_dir.glob("reach_*.json")
        }

    assert reach_files(tmp_path / "serial") == reach_files(tmp_path / "parallel")


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


def test_compute_all_writes_gzip_siblings(tmp_path):
    # coverage, reach, cities, meta are served verbatim by
    # server/app.py, so the pipeline writes a `.json.gz` sibling for each,
    # byte-identical (once decompressed) to the plain file and no staler.
    # stations.json is merged with a live has_reach set per request, so it's
    # never served verbatim and gets no sibling.
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
    compute_all(tmp_path / "graph", out, feeds_path=feeds_toml)

    for name in ("reach_1111111.json", "meta.json", "cities.json", "coverage.json"):
        plain = out / name
        gz = out / f"{name}.gz"
        assert gz.exists(), f"missing {gz}"
        assert gzip.decompress(gz.read_bytes()) == plain.read_bytes()
        assert gz.stat().st_mtime >= plain.stat().st_mtime

    assert not (out / "stations.json.gz").exists()


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
    stale_gz = out / "reach_9999999.json.gz"
    stale_gz.write_bytes(gzip.compress(b"{}"))
    compute_all(tmp_path / "graph", out, workers=1, feeds_path=feeds_toml)
    assert not stale.exists()
    assert not stale_gz.exists()  # gz sibling pruned alongside the stale plain file
    assert (out / "reach_1111111.json").exists()  # fresh files kept
    assert (out / "reach_1111111.json.gz").exists()


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
    countries_toml.write_text(
        '[[override]]\nname = "Alpha Hbf"\nlat = 50.0\nlon = 8.0\ncountry = "LA"\n'
    )
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
    capitals_toml = tmp_path / "capitals.toml"
    capitals_toml.write_text('[capitals]\nLA = "Alpha Hbf"\n')
    compute_all(
        tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml,
        capitals_path=capitals_toml,
    )

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    beta = next(s for s in stations["stations"] if s["id"] == "2222222")
    assert alpha["is_capital"] is True
    assert beta["is_capital"] is False


def test_compute_all_sets_is_capital_for_dk_and_pt(tmp_path):
    """Proves a Lisboa-like and a København-like synthetic station now gets is_capital=true."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    # Map 'st:1111111' to name 'København H' and country 'DK'
    # Map 'st:2222222' to name 'Lisboa Oriente' and country 'PT'
    countries_toml.write_text(
        '[[override]]\nname = "København H"\nlat = 50.0\nlon = 8.0\ncountry = "DK"\n\n'
        '[[override]]\nname = "Lisboa Oriente"\nlat = 50.0\nlon = 9.0\ncountry = "PT"\n'
    )
    names_toml.write_text(
        '[names]\n"1111111" = "København H"\n"2222222" = "Lisboa Oriente"\n'
    )
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
    # Write a capitals.toml with the DK and PT entries
    capitals_toml = tmp_path / "capitals.toml"
    capitals_toml.write_text(
        '[capitals]\nDK = "København H"\nPT = "Lisboa Oriente"\n'
    )
    compute_all(
        tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml,
        capitals_path=capitals_toml,
    )

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    kobenhavn = next(s for s in stations["stations"] if s["name"] == "København H")
    lisboa = next(s for s in stations["stations"] if s["name"] == "Lisboa Oriente")
    assert kobenhavn["is_capital"] is True
    assert lisboa["is_capital"] is True


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
    """A trip seen on one sampled date contributes evidence, but cannot join a
    different sampled date's trip into a single journey."""
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
        "active_months": ["Jan"],
    }


def test_compute_ignores_probes_outside_a_route_feeds_validity_window(tmp_path):
    """A narrow downloaded feed must not make its normal route look limited."""
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


def test_compute_keeps_absent_from_week_trip_visible(tmp_path):
    """A trip whose service is absent from every sampled date (see
    services_absent_from_week / build.py's extra_trips) still makes its
    destination reachable -- this is real map coverage, not a classification.
    It carries no direct-day evidence and is honestly reported "limited", never
    "seasonal": that label is retired (backlog AF)."""
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
    extra = Trip(
        trip_id="winter", train="Night", feeds=["rail"],
        stops=[StopTime(station="A", arr=480, dep=480), StopTime(station="B", arr=540, dep=540)],
    )
    graph.joinpath("trips.json").write_text(json.dumps({
        "trips": [], "trips_by_date": {day: [] for day in dates},
        "extra_trips": [extra.model_dump()],
        "feed_validity_by_date": {
            day: {"rail": {"covered": True, "sampled": True}} for day in dates
        },
    }))
    compute_all(graph, tmp_path / "out", workers=1, feeds_path=tmp_path / "no-feeds.toml")
    reach = json.loads((tmp_path / "out" / "reach_A.json").read_text())
    assert [d["id"] for d in reach["destinations"]] == ["B"]  # still on the map
    frequency = reach["destinations"][0]["frequency"]
    assert "seasonal" not in frequency
    assert frequency["availability"] == "limited"
    assert frequency["direct_trips"] == 0


def test_compute_marks_year_round_when_reachable_every_sampled_date(tmp_path):
    """Regression for the removed calendar-shortfall classification (backlog
    AF): a destination reachable on every sampled date must be "year_round",
    no matter how short its underlying GTFS calendar row looked upstream --
    compute.py never sees calendar spans at all, only observed reachability."""
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
    trip = Trip(
        trip_id="ice", train="ICE 100", feeds=["rail"],
        stops=[StopTime(station="A", arr=480, dep=480), StopTime(station="B", arr=540, dep=540)],
    )
    graph.joinpath("trips.json").write_text(json.dumps({
        "trips": [trip.model_dump()],
        "trips_by_date": {day: [trip.model_dump()] for day in dates},
        "feed_validity_by_date": {
            day: {"rail": {"covered": True, "sampled": True}} for day in dates
        },
    }))
    compute_all(graph, tmp_path / "out", workers=1, feeds_path=tmp_path / "no-feeds.toml")
    reach = json.loads((tmp_path / "out" / "reach_A.json").read_text())
    frequency = reach["destinations"][0]["frequency"]
    assert frequency["availability"] == "year_round"
    assert frequency["direct_trips"] == 7
