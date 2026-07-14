import json

import osmium
import osmium.osm.mutable as osmium_mutable

from pipeline.railpaths import (
    GEOFABRIK_REGION,
    RailWay,
    assemble_paths,
    build_graph,
    collect_hops,
    download_extracts,
    filter_rail_extract,
    needed_countries,
    parse_maxspeed,
    prepare_extracts,
    read_rail_network,
    route,
    snap_stations,
    write_outputs,
)


def _write_reach(tmp_path, origin, destinations):
    (tmp_path / f"reach_{origin}.json").write_text(json.dumps({
        "origin": origin, "computed_at": "x", "sample_date": "x",
        "destinations": destinations,
    }), encoding="utf-8")


def test_collect_hops_nonstop_and_via_legs(tmp_path):
    _write_reach(tmp_path, "s:a", [
        {"id": "s:d", "direct_per_day": 1, "journeys": [
            {"trains": 1, "duration_min": 60, "legs": [
                {"train": "T1", "dep": "", "arr": "", "from": "s:a", "to": "s:d",
                 "via": ["s:b", "s:c"]},
            ]},
            {"trains": 1, "duration_min": 90, "legs": [
                {"train": "T2", "dep": "", "arr": "", "from": "s:a", "to": "s:d", "via": []},
            ]},
        ]},
    ])
    assert collect_hops(tmp_path) == {
        ("s:a", "s:b"), ("s:b", "s:c"), ("s:c", "s:d"), ("s:a", "s:d"),
    }


def test_collect_hops_normalizes_direction_and_dedupes(tmp_path):
    leg_ab = {"train": "T", "dep": "", "arr": "", "from": "s:a", "to": "s:b", "via": []}
    leg_ba = {"train": "T", "dep": "", "arr": "", "from": "s:b", "to": "s:a", "via": []}
    _write_reach(tmp_path, "s:a", [{"id": "s:b", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [leg_ab]}]}])
    _write_reach(tmp_path, "s:b", [{"id": "s:a", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [leg_ba]}]}])
    assert collect_hops(tmp_path) == {("s:a", "s:b")}


def test_collect_hops_skips_self_pairs(tmp_path):
    _write_reach(tmp_path, "s:a", [{"id": "s:b", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [
            {"train": "T", "dep": "", "arr": "", "from": "s:a", "to": "s:b", "via": ["s:a"]},
        ]}]}])
    assert collect_hops(tmp_path) == {("s:a", "s:b")}


def test_parse_maxspeed():
    assert parse_maxspeed(None) == 100.0
    assert parse_maxspeed("signals") == 100.0
    assert parse_maxspeed("160") == 160.0
    assert parse_maxspeed("120 mph") == 120 * 1.609344
    assert parse_maxspeed("5") == 10.0     # clamped up
    assert parse_maxspeed("400") == 320.0  # clamped down


# A tiny synthetic network in lon/lat. 0.01° lon at lat 0 ≈ 1.11 km.
#   1 --- 2 --- 3 --- 4    slow line, 100 km/h (nodes 2,3 are degree-2)
#   1 --------- 5 ---- 4   fast bypass, 300 km/h
NODES = {
    1: (0.00, 0.0), 2: (0.01, 0.0), 3: (0.02, 0.0), 4: (0.03, 0.0),
    5: (0.015, 0.005),
}
SLOW = RailWay(refs=(1, 2, 3, 4), speed_kmh=100.0)
FAST = RailWay(refs=(1, 5, 4), speed_kmh=300.0)


def test_build_graph_contracts_degree2_chains():
    graph = build_graph([SLOW, FAST], NODES, extra_junctions=set())
    # Vertices: only 1 and 4 (2, 3, 5 are interior degree-2 nodes).
    assert set(graph.adjacency) == {1, 4}
    assert len(graph.edges) == 2
    slow_edge = next(e for e in graph.edges if len(e.coords) == 4)
    assert slow_edge.coords == [NODES[1], NODES[2], NODES[3], NODES[4]]


def test_build_graph_extra_junctions_split_edges():
    graph = build_graph([SLOW], NODES, extra_junctions={2})
    assert set(graph.adjacency) == {1, 2, 4}
    assert len(graph.edges) == 2


def test_build_graph_speed_weights_cost():
    graph = build_graph([SLOW, FAST], NODES, extra_junctions=set())
    slow_edge = next(e for e in graph.edges if len(e.coords) == 4)
    fast_edge = next(e for e in graph.edges if len(e.coords) == 3)
    # The bypass is geometrically longer but 3× faster → cheaper.
    assert fast_edge.cost_h < slow_edge.cost_h


def test_build_graph_skips_way_with_missing_node():
    graph = build_graph([RailWay(refs=(1, 99), speed_kmh=100.0)], NODES,
                        extra_junctions=set())
    assert graph.edges == []


def test_snap_stations():
    stations = [
        {"id": "s:near", "lon": 0.0101, "lat": 0.0001},  # ~15 m from node 2
        {"id": "s:far", "lon": 1.0, "lat": 1.0},         # ~150 km from anything
    ]
    snapped, failures = snap_stations(stations, NODES)
    assert snapped == {"s:near": 2}
    assert [f["station"] for f in failures] == ["s:far"]
    assert failures[0]["reason"] == "no_rail_within_snap_radius"


def _routed_graph():
    return build_graph([SLOW, FAST], NODES, extra_junctions=set())


def test_route_prefers_fast_bypass():
    graph = _routed_graph()
    coords = route(graph, 1, 4)
    assert coords == [NODES[1], NODES[5], NODES[4]]


def test_route_unreachable_returns_none():
    graph = build_graph([SLOW, RailWay(refs=(10, 11), speed_kmh=100.0)],
                        {**NODES, 10: (5.0, 5.0), 11: (5.01, 5.0)},
                        extra_junctions=set())
    assert route(graph, 1, 10) is None


def test_assemble_paths_orientation_endpoints_and_failures():
    graph = _routed_graph()
    stations = {
        "s:x": {"id": "s:x", "lon": 0.0001, "lat": 0.0},   # snaps to node 1
        "s:y": {"id": "s:y", "lon": 0.0299, "lat": 0.0},   # snaps to node 4
        "s:far": {"id": "s:far", "lon": 1.0, "lat": 1.0},  # unsnappable
    }
    snapped = {"s:x": 1, "s:y": 4}
    hops = {("s:x", "s:y"), ("s:far", "s:x")}
    paths, failures = assemble_paths(hops, snapped, graph, stations)
    assert set(paths) == {"s:x|s:y"}
    coords = paths["s:x|s:y"]
    # Stitched to exact station coords at both ends, oriented s:x → s:y.
    assert coords[0] == [0.0001, 0.0]
    assert coords[-1] == [0.0299, 0.0]
    # Interior follows the fast bypass through node 5.
    assert [0.015, 0.005] in coords
    assert failures == [{"hop": "s:far|s:x", "reason": "endpoint_not_snapped"}]


def test_write_outputs(tmp_path):
    write_outputs(tmp_path, {"a|b": [[0.0, 0.0], [1.0, 1.0]]},
                  snap_failures=[{"station": "s", "reason": "r", "nearest_m": 9}],
                  hop_failures=[{"hop": "h", "reason": "r"}])
    data = json.loads((tmp_path / "rail_paths.json").read_text(encoding="utf-8"))
    assert "OpenStreetMap" in data["attribution"]
    assert data["paths"] == {"a|b": [[0.0, 0.0], [1.0, 1.0]]}
    report = json.loads((tmp_path / "rail_paths_report.json").read_text(encoding="utf-8"))
    assert report["summary"] == {"paths": 1, "snap_failures": 1, "hop_failures": 1}
    assert report["snap_failures"][0]["station"] == "s"
    assert report["hop_failures"][0]["hop"] == "h"


ALL_DATA_COUNTRIES = {
    "AT", "BE", "CH", "CZ", "DE", "DK", "ES", "FR", "GB", "HR", "HU", "IT",
    "LI", "LT", "LU", "NL", "PL", "PT", "RO", "SI", "SK", "UA",
}


def test_geofabrik_region_covers_all_data_countries():
    assert ALL_DATA_COUNTRIES <= set(GEOFABRIK_REGION)


def test_needed_countries_from_hop_stations():
    stations = {
        "s:a": {"id": "s:a", "country": "DE"},
        "s:b": {"id": "s:b", "country": "FR"},
        "s:c": {"id": "s:c", "country": "XX"},   # unmapped
        "s:d": {"id": "s:d", "country": "PL"},   # not in any hop
    }
    hops = {("s:a", "s:b"), ("s:a", "s:c")}
    countries, unmapped = needed_countries(hops, stations)
    assert countries == ["DE", "FR"]
    assert unmapped == ["XX"]


def test_download_extracts_skips_cached(tmp_path):
    cached = tmp_path / "germany-latest.osm.pbf"
    cached.write_bytes(b"cached")
    paths = download_extracts(["DE"], tmp_path, force=False)
    assert paths == [cached]
    assert cached.read_bytes() == b"cached"  # untouched, no network call


def _write_osm_fixture(path):
    """A tiny OSM PBF: one railway=rail way, one highway=residential way,
    and the two nodes each of them reference."""
    writer = osmium.SimpleWriter(str(path))
    common = {
        "version": 1, "visible": True, "changeset": 1,
        "timestamp": "2020-01-01T00:00:00Z", "uid": 1,
    }
    writer.add_node(osmium_mutable.Node(id=1, location=(10.0, 47.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=2, location=(10.01, 47.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=3, location=(11.0, 48.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=4, location=(11.01, 48.0), tags={}, **common))
    writer.add_way(osmium_mutable.Way(
        id=100, nodes=[1, 2], tags={"railway": "rail"}, **common))
    writer.add_way(osmium_mutable.Way(
        id=200, nodes=[3, 4], tags={"highway": "residential"}, **common))
    writer.close()


def test_filter_rail_extract_keeps_only_rail_ways_and_their_nodes(tmp_path):
    src = tmp_path / "fixture.osm.pbf"
    _write_osm_fixture(src)
    dst = tmp_path / "fixture-rail.osm.pbf"

    result = filter_rail_extract(src, dst)

    assert result == dst
    assert dst.exists()
    assert not dst.with_suffix(".part").exists()
    ways, node_locs = read_rail_network([dst])
    assert len(ways) == 1
    assert ways[0].refs == (1, 2)
    assert node_locs == {1: (10.0, 47.0), 2: (10.01, 47.0)}


def test_prepare_extracts_uses_cached_rail_file(tmp_path, monkeypatch):
    rail = tmp_path / "germany-rail.osm.pbf"
    rail.write_bytes(b"cached rail")

    def _boom(*args, **kwargs):
        raise AssertionError("filter_rail_extract should not be called")

    monkeypatch.setattr("pipeline.railpaths.filter_rail_extract", _boom)
    monkeypatch.setattr("pipeline.railpaths.download_extracts", _boom)

    paths = prepare_extracts(["DE"], tmp_path, force=False)

    assert paths == [rail]
    assert rail.read_bytes() == b"cached rail"


def test_prepare_extracts_filters_and_deletes_raw(tmp_path, monkeypatch):
    raw = tmp_path / "germany-latest.osm.pbf"
    raw.write_bytes(b"raw extract")

    def _stub_filter(src, dst):
        dst.write_bytes(b"filtered")
        return dst

    monkeypatch.setattr("pipeline.railpaths.filter_rail_extract", _stub_filter)

    paths = prepare_extracts(["DE"], tmp_path, force=False)

    rail = tmp_path / "germany-rail.osm.pbf"
    assert paths == [rail]
    assert rail.read_bytes() == b"filtered"
    assert not raw.exists()
