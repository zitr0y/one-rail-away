import gzip
import json

import osmium
import osmium.osm.mutable as osmium_mutable

from pipeline.railpaths import (
    GEOFABRIK_REGION,
    MIN_COMPONENT_NODES,
    RAIL_RAILWAY_VALUES,
    SNAP_MAX_M,
    RailWay,
    SnapCandidate,
    assemble_paths,
    build_graph,
    collect_hops,
    connected_components,
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


def test_connected_components_groups_and_separates():
    way_a = RailWay(refs=(1, 2), speed_kmh=100.0)
    way_b = RailWay(refs=(2, 3), speed_kmh=100.0)  # shares node 2 with way_a
    way_c = RailWay(refs=(10, 11), speed_kmh=100.0)  # disjoint
    components = connected_components([way_a, way_b, way_c])
    assert components[1] == components[2] == components[3]
    assert components[10] == components[11]
    assert components[1] != components[10]


def _big_component(ids, lon0, lat, comp_id, step=0.0001):
    """A component with >= MIN_COMPONENT_NODES nodes, spaced along a line."""
    node_locs = {n: (lon0 + i * step, lat) for i, n in enumerate(ids)}
    components = dict.fromkeys(ids, comp_id)
    return node_locs, components


def _component_sizes(components):
    sizes = {}
    for comp in components.values():
        sizes[comp] = sizes.get(comp, 0) + 1
    return sizes


def test_snap_stations_ignores_small_component():
    big_ids = range(100, 100 + MIN_COMPONENT_NODES)
    node_locs, components = _big_component(big_ids, 0.0, 0.0, comp_id=1)
    # A 2-node stub sits closer to the station than anything in the big
    # component, but must be ignored: its component is below the threshold.
    node_locs[900] = (0.00001, 0.0)
    node_locs[901] = (0.00002, 0.0)
    components[900] = components[901] = 2

    station = {"id": "s:a", "lon": 0.0, "lat": 0.0}
    candidates, failures = snap_stations(
        [station], node_locs, components, _component_sizes(components))

    assert failures == []
    cands = candidates["s:a"]
    assert all(c.component == 1 for c in cands)
    assert cands[0].node == 100  # nearest node in the big component (distance 0)


def test_snap_stations_two_networks_each_get_one_candidate():
    # Simulates an interchange like Chur, served by both a standard-gauge and
    # a metre-gauge network: one candidate per component, nearest first.
    ids_a = range(200, 200 + MIN_COMPONENT_NODES)
    ids_b = range(300, 300 + MIN_COMPONENT_NODES)
    node_locs_a, components_a = _big_component(ids_a, 0.0, 0.0, comp_id=10)
    node_locs_b, components_b = _big_component(ids_b, 0.0, 0.0002, comp_id=20)
    node_locs = {**node_locs_a, **node_locs_b}
    components = {**components_a, **components_b}

    station = {"id": "s:interchange", "lon": 0.0, "lat": 0.0001}
    candidates, failures = snap_stations(
        [station], node_locs, components, _component_sizes(components))

    assert failures == []
    cands = candidates["s:interchange"]
    assert {c.component for c in cands} == {10, 20}
    assert len(cands) == 2
    assert cands[0].distance_m <= cands[1].distance_m


def test_snap_stations_reports_nearest_m_beyond_radius():
    big_ids = range(400, 400 + MIN_COMPONENT_NODES)
    node_locs, components = _big_component(big_ids, 0.5, 0.0, comp_id=30)
    station = {"id": "s:far", "lon": 0.0, "lat": 0.0}

    candidates, failures = snap_stations(
        [station], node_locs, components, _component_sizes(components))

    assert candidates == {}
    assert failures[0]["station"] == "s:far"
    assert failures[0]["reason"] == "no_rail_within_snap_radius"
    assert failures[0]["nearest_m"] > SNAP_MAX_M


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
    candidates = {
        "s:x": [SnapCandidate(node=1, distance_m=10.0, component=1)],
        "s:y": [SnapCandidate(node=4, distance_m=10.0, component=1)],
    }
    hops = {("s:x", "s:y"), ("s:far", "s:x")}
    paths, failures = assemble_paths(hops, candidates, graph, stations)
    assert set(paths) == {"s:x|s:y"}
    coords = paths["s:x|s:y"]
    # Stitched to exact station coords at both ends, oriented s:x → s:y.
    assert coords[0] == [0.0001, 0.0]
    assert coords[-1] == [0.0299, 0.0]
    # Interior follows the fast bypass through node 5.
    assert [0.015, 0.005] in coords
    assert failures == [{"hop": "s:far|s:x", "reason": "endpoint_not_snapped"}]


def test_assemble_paths_no_shared_component():
    graph = _routed_graph()
    stations = {
        "s:p": {"id": "s:p", "lon": 0.0001, "lat": 0.0},
        "s:q": {"id": "s:q", "lon": 0.0299, "lat": 0.0},
    }
    candidates = {
        "s:p": [SnapCandidate(node=1, distance_m=10.0, component=1)],
        "s:q": [SnapCandidate(node=4, distance_m=10.0, component=2)],
    }
    hops = {("s:p", "s:q")}
    paths, failures = assemble_paths(hops, candidates, graph, stations)
    assert paths == {}
    assert failures == [{"hop": "s:p|s:q", "reason": "no_shared_rail_component"}]


def test_assemble_paths_tries_shared_components_by_ascending_distance():
    # Component 2 has the smaller combined snap distance but its candidate
    # nodes aren't connected to anything in the graph, so routing must fall
    # back to component 1 (the real, routable, network).
    extra_nodes = {**NODES, 20: (9.0, 9.0), 21: (9.01, 9.0)}
    graph = build_graph([SLOW, FAST], extra_nodes, extra_junctions=set())
    stations = {
        "s:x": {"id": "s:x", "lon": 0.0001, "lat": 0.0},
        "s:y": {"id": "s:y", "lon": 0.0299, "lat": 0.0},
    }
    candidates = {
        "s:x": [
            SnapCandidate(node=20, distance_m=1.0, component=2),
            SnapCandidate(node=1, distance_m=50.0, component=1),
        ],
        "s:y": [
            SnapCandidate(node=21, distance_m=1.0, component=2),
            SnapCandidate(node=4, distance_m=50.0, component=1),
        ],
    }
    hops = {("s:x", "s:y")}
    paths, failures = assemble_paths(hops, candidates, graph, stations)
    assert failures == []
    coords = paths["s:x|s:y"]
    assert coords[0] == [0.0001, 0.0]
    assert coords[-1] == [0.0299, 0.0]


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

    # rail_paths.json is served verbatim (server/app.py), so it gets a
    # pre-gzipped sibling the pipeline writes at the same time; the report is
    # diagnostics only and is never served, so it doesn't.
    plain = tmp_path / "rail_paths.json"
    gz = tmp_path / "rail_paths.json.gz"
    assert gzip.decompress(gz.read_bytes()) == plain.read_bytes()
    assert gz.stat().st_mtime >= plain.stat().st_mtime
    assert not (tmp_path / "rail_paths_report.json.gz").exists()


ALL_DATA_COUNTRIES = {
    "AT", "BE", "CH", "CZ", "DE", "DK", "ES", "FR", "GB", "HR", "HU", "IT",
    "LI", "LT", "LU", "NL", "PL", "PT", "RO", "SI", "SK", "UA",
}


def test_geofabrik_region_covers_all_data_countries():
    assert set(GEOFABRIK_REGION) >= ALL_DATA_COUNTRIES


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
    """A tiny OSM PBF covering every railway value we care about: rail,
    narrow_gauge (e.g. Rhaetian Railway), light_rail, plus a subway (must be
    excluded) and a highway (must be excluded), each with its own nodes."""
    writer = osmium.SimpleWriter(str(path))
    common = {
        "version": 1, "visible": True, "changeset": 1,
        "timestamp": "2020-01-01T00:00:00Z", "uid": 1,
    }
    writer.add_node(osmium_mutable.Node(id=1, location=(10.0, 47.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=2, location=(10.01, 47.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=3, location=(11.0, 48.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=4, location=(11.01, 48.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=5, location=(12.0, 46.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=6, location=(12.01, 46.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=7, location=(13.0, 45.0), tags={}, **common))
    writer.add_node(osmium_mutable.Node(id=8, location=(13.01, 45.0), tags={}, **common))
    writer.add_way(osmium_mutable.Way(
        id=100, nodes=[1, 2], tags={"railway": "rail"}, **common))
    writer.add_way(osmium_mutable.Way(
        id=200, nodes=[3, 4], tags={"highway": "residential"}, **common))
    writer.add_way(osmium_mutable.Way(
        id=300, nodes=[5, 6], tags={"railway": "narrow_gauge", "gauge": "1000"},
        **common))
    writer.add_way(osmium_mutable.Way(
        id=400, nodes=[7, 8], tags={"railway": "subway"}, **common))
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
    assert {w.refs for w in ways} == {(1, 2), (5, 6)}
    assert node_locs == {
        1: (10.0, 47.0), 2: (10.01, 47.0),
        5: (12.0, 46.0), 6: (12.01, 46.0),
    }


def test_rail_railway_values_excludes_subway_and_tram():
    assert RAIL_RAILWAY_VALUES == ("rail", "narrow_gauge", "light_rail")
    assert "subway" not in RAIL_RAILWAY_VALUES
    assert "tram" not in RAIL_RAILWAY_VALUES


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
