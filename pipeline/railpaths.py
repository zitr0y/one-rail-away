"""Real rail geometry for reach-line hops (backlog item I).

Builds a speed-weighted rail graph from OSM extracts and writes
data/out/rail_paths.json: one polyline per unique physical hop found in the
reach files, keyed like the web's segmentKey ("idA|idB", idA < idB, path
oriented idA→idB). Unroutable hops and unsnappable stations are reported in
data/out/rail_paths_report.json instead of failing the build; the web falls
back to straight lines for anything missing.
"""

from __future__ import annotations

import heapq
import itertools
import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from pipeline.geo import _haversine_m

log = logging.getLogger(__name__)

SNAP_MAX_M = 1000.0

DEFAULT_SPEED_KMH = 100.0
MIN_SPEED_KMH = 10.0
MAX_SPEED_KMH = 320.0

_SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)")


def collect_hops(out_dir: Path) -> set[tuple[str, str]]:
    """Direction-normalized unique station-pair hops across all reach files."""
    hops: set[tuple[str, str]] = set()
    for path in sorted(out_dir.glob("reach_*.json")):
        reach = json.loads(path.read_text(encoding="utf-8"))
        for dest in reach["destinations"]:
            for journey in dest["journeys"]:
                for leg in journey["legs"]:
                    stops = [leg["from"], *leg["via"], leg["to"]]
                    for a, b in itertools.pairwise(stops):
                        if a != b:
                            hops.add((a, b) if a < b else (b, a))
    return hops


def parse_maxspeed(value: str | None) -> float:
    """OSM maxspeed tag → km/h, defaulted and clamped to sane rail bounds."""
    if not value:
        return DEFAULT_SPEED_KMH
    match = _SPEED_RE.search(value)
    if not match:
        return DEFAULT_SPEED_KMH
    speed = float(match.group(1))
    if "mph" in value:
        speed *= 1.609344
    return min(max(speed, MIN_SPEED_KMH), MAX_SPEED_KMH)


@dataclass(frozen=True)
class RailWay:
    refs: tuple[int, ...]
    speed_kmh: float


@dataclass
class Edge:
    a: int
    b: int
    coords: list[tuple[float, float]]  # (lon, lat), ordered a→b
    cost_h: float


@dataclass
class RailGraph:
    node_locs: dict[int, tuple[float, float]]
    edges: list[Edge] = field(default_factory=list)
    adjacency: dict[int, list[int]] = field(default_factory=dict)  # vertex → edge idx

    def add_edge(self, edge: Edge) -> None:
        index = len(self.edges)
        self.edges.append(edge)
        self.adjacency.setdefault(edge.a, []).append(index)
        self.adjacency.setdefault(edge.b, []).append(index)


def _length_km(coords: list[tuple[float, float]]) -> float:
    return sum(
        _haversine_m(a[1], a[0], b[1], b[0])
        for a, b in itertools.pairwise(coords)
    ) / 1000.0


def build_graph(
    ways: list[RailWay], node_locs: dict[int, tuple[float, float]],
    extra_junctions: set[int],
) -> RailGraph:
    """Contract degree-2 chains: an edge spans junction→junction with the full
    intermediate polyline, so the graph stays small while geometry stays exact."""
    usage: dict[int, int] = {}
    for way in ways:
        for ref in way.refs:
            usage[ref] = usage.get(ref, 0) + 1
    junctions = set(extra_junctions)
    for way in ways:
        if not way.refs:
            continue
        junctions.add(way.refs[0])
        junctions.add(way.refs[-1])
        seen_in_way: set[int] = set()
        for ref in way.refs:
            if usage[ref] >= 2 or ref in seen_in_way:
                junctions.add(ref)
            seen_in_way.add(ref)

    graph = RailGraph(node_locs=node_locs)
    for way in ways:
        if any(ref not in node_locs for ref in way.refs):
            log.warning("skipping rail way with %d refs: missing node location",
                        len(way.refs))
            continue
        chain: list[int] = []
        for ref in way.refs:
            chain.append(ref)
            if len(chain) > 1 and ref in junctions:
                coords = [node_locs[n] for n in chain]
                graph.add_edge(Edge(
                    a=chain[0], b=chain[-1], coords=coords,
                    cost_h=_length_km(coords) / way.speed_kmh,
                ))
                chain = [ref]
    return graph


def snap_stations(
    stations: list[dict], node_locs: dict[int, tuple[float, float]],
) -> tuple[dict[str, int], list[dict]]:
    node_ids = list(node_locs)
    tree = STRtree([Point(*node_locs[n]) for n in node_ids])
    snapped: dict[str, int] = {}
    failures: list[dict] = []
    for station in stations:
        index = tree.nearest(Point(station["lon"], station["lat"]))
        node_id = node_ids[index]
        lon, lat = node_locs[node_id]
        distance_m = _haversine_m(station["lat"], station["lon"], lat, lon)
        if distance_m <= SNAP_MAX_M:
            snapped[station["id"]] = node_id
        else:
            failures.append({
                "station": station["id"], "reason": "no_rail_within_snap_radius",
                "nearest_m": round(distance_m),
            })
    return snapped, failures


SIMPLIFY_TOLERANCE_DEG = 0.0003  # ~30 m; TUNING POINT


def _heuristic_h(graph: RailGraph, node: int, goal: int) -> float:
    a, b = graph.node_locs[node], graph.node_locs[goal]
    return _haversine_m(a[1], a[0], b[1], b[0]) / 1000.0 / MAX_SPEED_KMH


def route(graph: RailGraph, start: int, goal: int) -> list[tuple[float, float]] | None:
    """A* over the contracted graph; returns the full polyline start→goal."""
    if start == goal:
        return None
    best_g: dict[int, float] = {start: 0.0}
    # parent[vertex] = (previous vertex, edge index used to arrive)
    parent: dict[int, tuple[int, int]] = {}
    open_heap: list[tuple[float, int]] = [(_heuristic_h(graph, start, goal), start)]
    closed: set[int] = set()
    while open_heap:
        _, vertex = heapq.heappop(open_heap)
        if vertex == goal:
            break
        if vertex in closed:
            continue
        closed.add(vertex)
        for edge_index in graph.adjacency.get(vertex, []):
            edge = graph.edges[edge_index]
            neighbor = edge.b if edge.a == vertex else edge.a
            candidate = best_g[vertex] + edge.cost_h
            if candidate < best_g.get(neighbor, float("inf")):
                best_g[neighbor] = candidate
                parent[neighbor] = (vertex, edge_index)
                heapq.heappush(
                    open_heap,
                    (candidate + _heuristic_h(graph, neighbor, goal), neighbor),
                )
    if goal not in parent:
        return None
    coords: list[tuple[float, float]] = []
    vertex = goal
    while vertex != start:
        previous, edge_index = parent[vertex]
        edge = graph.edges[edge_index]
        piece = edge.coords if edge.b == vertex else list(reversed(edge.coords))
        # piece[:-1] drops the duplicated joint vertex between consecutive edges.
        coords = piece if not coords else piece[:-1] + coords
        vertex = previous
    return coords


def assemble_paths(
    hops: set[tuple[str, str]], snapped: dict[str, int], graph: RailGraph,
    stations_by_id: dict[str, dict],
) -> tuple[dict[str, list[list[float]]], list[dict]]:
    paths: dict[str, list[list[float]]] = {}
    failures: list[dict] = []
    for a_id, b_id in sorted(hops):
        key = f"{a_id}|{b_id}"
        node_a, node_b = snapped.get(a_id), snapped.get(b_id)
        if node_a is None or node_b is None:
            failures.append({"hop": key, "reason": "endpoint_not_snapped"})
            continue
        coords = route(graph, node_a, node_b)
        if coords is None:
            failures.append({"hop": key, "reason": "no_rail_path"})
            continue
        simplified = list(LineString(coords).simplify(SIMPLIFY_TOLERANCE_DEG).coords)
        station_a, station_b = stations_by_id[a_id], stations_by_id[b_id]
        points = [[round(lon, 5), round(lat, 5)] for lon, lat in simplified]
        full = [[station_a["lon"], station_a["lat"]], *points,
                [station_b["lon"], station_b["lat"]]]
        deduped = [p for i, p in enumerate(full) if i == 0 or p != full[i - 1]]
        paths[key] = deduped
    return paths, failures


def write_outputs(
    out_dir: Path, paths: dict[str, list[list[float]]],
    snap_failures: list[dict], hop_failures: list[dict],
) -> None:
    (out_dir / "rail_paths.json").write_text(json.dumps({
        "attribution": "© OpenStreetMap contributors (ODbL)",
        "paths": paths,
    }, separators=(",", ":")), encoding="utf-8")
    (out_dir / "rail_paths_report.json").write_text(json.dumps({
        "summary": {
            "paths": len(paths),
            "snap_failures": len(snap_failures),
            "hop_failures": len(hop_failures),
        },
        "snap_failures": snap_failures,
        "hop_failures": hop_failures,
    }, indent=1), encoding="utf-8")
    log.info("rail paths: %d written, %d snap failures, %d hop failures",
             len(paths), len(snap_failures), len(hop_failures))


GEOFABRIK_REGION = {
    "AT": "europe/austria", "BE": "europe/belgium", "CH": "europe/switzerland",
    "CZ": "europe/czech-republic", "DE": "europe/germany", "DK": "europe/denmark",
    "ES": "europe/spain", "FR": "europe/france", "GB": "europe/great-britain",
    "HR": "europe/croatia", "HU": "europe/hungary", "IT": "europe/italy",
    "LI": "europe/liechtenstein", "LT": "europe/lithuania",
    "LU": "europe/luxembourg", "NL": "europe/netherlands", "PL": "europe/poland",
    "PT": "europe/portugal", "RO": "europe/romania", "SI": "europe/slovenia",
    "SK": "europe/slovakia", "UA": "europe/ukraine",
}


def needed_countries(
    hops: set[tuple[str, str]], stations_by_id: dict[str, dict],
) -> tuple[list[str], list[str]]:
    """Countries of every station participating in a hop; unmapped codes reported."""
    codes = {
        stations_by_id[sid]["country"]
        for pair in hops for sid in pair if sid in stations_by_id
    }
    return (sorted(c for c in codes if c in GEOFABRIK_REGION),
            sorted(c for c in codes if c not in GEOFABRIK_REGION))


def download_extracts(countries: list[str], osm_dir: Path, force: bool) -> list[Path]:
    osm_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for code in countries:
        region = GEOFABRIK_REGION[code]
        filename = region.rsplit("/", 1)[-1] + "-latest.osm.pbf"
        target = osm_dir / filename
        if target.exists() and not force:
            paths.append(target)
            continue
        url = f"https://download.geofabrik.de/{region}-latest.osm.pbf"
        log.info("downloading %s", url)
        part = target.with_suffix(".part")
        with urllib.request.urlopen(url) as response, part.open("wb") as out:
            expected = int(response.headers.get("Content-Length", 0))
            written = 0
            while chunk := response.read(1 << 20):
                out.write(chunk)
                written += len(chunk)
        if expected and written != expected:
            part.unlink()
            raise RuntimeError(
                f"{url}: truncated download ({written} of {expected} bytes)")
        part.rename(target)
        paths.append(target)
    return paths


def filter_rail_extract(src: Path, dst: Path) -> Path:
    """Filter a raw Geofabrik extract down to railway=rail ways plus the nodes
    they reference, writing the result to `dst`.

    Uses pyosmium's C++-level filtering (FileProcessor + filters) rather than
    per-object Python callbacks, since a per-object Python callback is far too
    slow to run over a 24 GB corpus of raw extracts. BackReferenceWriter adds
    the referenced nodes back in a second pass over `src`, emitting a
    correctly ordered PBF. Writes to a `.part` file and renames on success, so
    an interrupted filter never leaves a corrupt file at `dst`.
    """
    import osmium

    part = dst.with_suffix(".part")
    if part.exists():
        part.unlink()
    log.info("filtering rail ways: %s -> %s", src.name, dst.name)
    # Explicit format: the ".part" extension isn't one osmium recognizes.
    writer = osmium.BackReferenceWriter(
        osmium.io.File(str(part), "pbf"), ref_src=str(src))
    try:
        for obj in (
            osmium.FileProcessor(str(src))
            .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
            .with_filter(osmium.filter.TagFilter(("railway", "rail")))
        ):
            writer.add(obj)
    finally:
        writer.close()
    part.rename(dst)
    return dst


def prepare_extracts(countries: list[str], osm_dir: Path, force: bool) -> list[Path]:
    """Rail-only extract per country: cached if present, else downloaded raw
    (or reused from cache) and filtered, then the raw extract is deleted.

    The rail-only cache (~50-150 MB per country) replaces the raw Geofabrik
    extract (multiple GB per country) as the on-disk cache, so repeated runs
    don't re-scan the full planet slice.
    """
    osm_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for code in countries:
        region = GEOFABRIK_REGION[code]
        stem = region.rsplit("/", 1)[-1]
        rail_target = osm_dir / f"{stem}-rail.osm.pbf"
        if rail_target.exists() and not force:
            paths.append(rail_target)
            continue
        (raw,) = download_extracts([code], osm_dir, force)
        raw_size = raw.stat().st_size
        filter_rail_extract(raw, rail_target)
        rail_size = rail_target.stat().st_size
        raw.unlink()
        log.info(
            "filtered %s (%.1f MB) -> %s (%.1f MB); raw deleted",
            raw.name, raw_size / 1e6, rail_target.name, rail_size / 1e6,
        )
        paths.append(rail_target)
    return paths


def read_rail_network(
    pbf_paths: list[Path],
) -> tuple[list[RailWay], dict[int, tuple[float, float]]]:
    """Two-pass read: rail ways first, then only their node locations.

    Keeps memory bounded by the RAIL subset, not the full extract. Ways are
    deduped by OSM way id — border-crossing ways appear in both extracts.
    """
    import osmium

    class WayCollector(osmium.SimpleHandler):
        def __init__(self) -> None:
            super().__init__()
            self.ways: dict[int, RailWay] = {}

        def way(self, w) -> None:  # noqa: ANN001 - osmium type
            if w.tags.get("railway") == "rail":
                self.ways[w.id] = RailWay(
                    refs=tuple(n.ref for n in w.nodes),
                    speed_kmh=parse_maxspeed(w.tags.get("maxspeed")),
                )

    class NodeCollector(osmium.SimpleHandler):
        def __init__(self, wanted: set[int]) -> None:
            super().__init__()
            self.wanted = wanted
            self.locs: dict[int, tuple[float, float]] = {}

        def node(self, n) -> None:  # noqa: ANN001 - osmium type
            if n.id in self.wanted:
                self.locs[n.id] = (n.location.lon, n.location.lat)

    way_collector = WayCollector()
    for path in pbf_paths:
        log.info("reading rail ways from %s", path.name)
        way_collector.apply_file(str(path))
    ways = list(way_collector.ways.values())
    wanted = {ref for way in ways for ref in way.refs}
    node_collector = NodeCollector(wanted)
    for path in pbf_paths:
        log.info("reading node locations from %s", path.name)
        node_collector.apply_file(str(path))
    log.info("rail network: %d ways, %d nodes", len(ways), len(node_collector.locs))
    return ways, node_collector.locs


def build_rail_paths(out_dir: Path, osm_dir: Path, force_download: bool = False) -> None:
    stations_by_id = {
        s["id"]: s
        for s in json.loads((out_dir / "stations.json").read_text(encoding="utf-8"))["stations"]
    }
    hops = collect_hops(out_dir)
    log.info("collected %d unique hops", len(hops))
    countries, unmapped = needed_countries(hops, stations_by_id)
    if unmapped:
        log.warning("no Geofabrik region mapped for countries: %s", unmapped)
    pbf_paths = prepare_extracts(countries, osm_dir, force_download)
    ways, node_locs = read_rail_network(pbf_paths)
    hop_station_ids = sorted(
        {sid for pair in hops for sid in pair if sid in stations_by_id})
    snapped, snap_failures = snap_stations(
        [stations_by_id[sid] for sid in hop_station_ids], node_locs)
    graph = build_graph(ways, node_locs, extra_junctions=set(snapped.values()))
    paths, hop_failures = assemble_paths(hops, snapped, graph, stations_by_id)
    write_outputs(out_dir, paths, snap_failures, hop_failures)
