# Real Rail Geometry + Target-Chooser Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reach lines follow real railway tracks (OSM-derived geometry, precomputed per physical hop), and the click-disambiguation popup stops changing the origin when picking a target.

**Architecture:** A new pipeline stage `ose paths` builds a speed-weighted rail graph from cached Geofabrik OSM extracts, routes each of the ~4.3k unique station-pair hops found in `data/out/reach_*.json`, and writes `data/out/rail_paths.json` keyed exactly like the web's `segmentKey`. The web fetches that file once and `legSegments` substitutes real geometry for straight lines (straight-line fallback stays). Curated corridors and chaikin smoothing are deleted. The AE fix is web-only: target-mode popups drop city entries and re-rank by reachability.

**Tech Stack:** Python 3.14 (pyosmium, shapely — shapely already a dep), FastAPI, TypeScript/React/MapLibre, vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-07-14-rail-geometry-and-target-chooser-design.md`

Key existing anchors:
- `web/src/lib/geojson.ts` — `segmentKey(a,b)` = lexicographic `"idA|idB"`; `legSegments` / `journeyLegPaths` / `segmentsGeoJSON` / `linesGeoJSON`.
- `web/src/components/Map.tsx` — `syncData()` (~line 312), rider effect (~line 441), `showOverlapChoice` (~line 213), `selectStation` (~line 164).
- `server/app.py::create_app(data_dir)` — endpoint pattern with 404 for missing files; tests use `TestClient(create_app(tmp_path))`.
- `pipeline/cli.py` — argparse subcommands, lazy imports per command.
- `pipeline/geo.py::_haversine_m(lat1, lon1, lat2, lon2)` — meters.

Verification commands: `uv run pytest -q` (pipeline+server), `cd web && npx vitest run` (web), `cd web && npm run build`.

---

## Task 1: railpaths core — hop collection + maxspeed parsing

**Goal:** New `pipeline/railpaths.py` with the pure input-side helpers: unique hop extraction from reach files and OSM maxspeed parsing.

**Files:**
- Create: `pipeline/railpaths.py`
- Test: `tests/test_railpaths.py`

**Acceptance Criteria:**
- [ ] `collect_hops` walks every leg of every `reach_*.json` in a dir and returns direction-normalized `(idA, idB)` pairs (`idA < idB`), deduped, self-pairs skipped; nonstop legs contribute their from→to pair, via-legs contribute each consecutive pair.
- [ ] `parse_maxspeed` handles None/garbage → 100.0 default, plain km/h ints, `"120 mph"` → km/h, clamps to [10, 320].
- [ ] No live station ids in tests (synthetic ids only — backlog AD).

**Verify:** `uv run pytest tests/test_railpaths.py -q` → all pass; `uv run ruff check pipeline/railpaths.py tests/test_railpaths.py` → clean.

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_railpaths.py
import json

from pipeline.railpaths import collect_hops, parse_maxspeed


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.railpaths'`

- [ ] **Step 3: Write the implementation**

```python
# pipeline/railpaths.py
"""Real rail geometry for reach-line hops (backlog item I).

Builds a speed-weighted rail graph from OSM extracts and writes
data/out/rail_paths.json: one polyline per unique physical hop found in the
reach files, keyed like the web's segmentKey ("idA|idB", idA < idB, path
oriented idA→idB). Unroutable hops and unsnappable stations are reported in
data/out/rail_paths_report.json instead of failing the build; the web falls
back to straight lines for anything missing.
"""

from __future__ import annotations

import itertools
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/railpaths.py tests/test_railpaths.py
git commit -m "feat(pipeline): rail-path hop collection and maxspeed parsing"
```

---

## Task 2: rail graph — junctions, contraction, station snapping

**Goal:** Build a contracted, speed-weighted graph from plain ways/node dicts (no OSM I/O here — that thin layer comes in Task 4), and snap stations to rail nodes.

**Files:**
- Modify: `pipeline/railpaths.py`
- Test: `tests/test_railpaths.py`

**Acceptance Criteria:**
- [ ] `build_graph(ways, node_locs, extra_junctions)` contracts degree-2 chains into single edges carrying the full polyline; junctions are way endpoints, nodes shared by ≥2 ways, nodes appearing twice in one way, and `extra_junctions`.
- [ ] Edge cost = geodesic length (km) ÷ way speed (h); ways referencing missing node locations are skipped with a log line, not fatal.
- [ ] `snap_stations(stations, node_locs)` returns `(snapped: dict[station_id, node_id], failures: list[dict])`; stations >1 km from any rail node fail with reason + distance.

**Verify:** `uv run pytest tests/test_railpaths.py -q` → all pass.

**Steps:**

- [ ] **Step 1: Write the failing tests** (append to `tests/test_railpaths.py`)

```python
from pipeline.railpaths import RailWay, build_graph, snap_stations

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: FAIL — `ImportError: cannot import name 'RailWay'`

- [ ] **Step 3: Write the implementation** — the import lines below go into the TOP import block of `pipeline/railpaths.py` (never mid-file — ruff E402); the rest is appended:

```python
from dataclasses import dataclass, field

from shapely.geometry import Point
from shapely.strtree import STRtree

from pipeline.geo import _haversine_m

SNAP_MAX_M = 1000.0


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
```

Note: `build_graph` must consider a node that appears twice within ONE way a junction (self-loop protection) — the `seen_in_way` set above does this.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: all pass (9 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/railpaths.py tests/test_railpaths.py
git commit -m "feat(pipeline): contracted speed-weighted rail graph + station snapping"
```

---

## Task 3: A* routing, path assembly, report — `build_rail_paths` orchestrator

**Goal:** Route every hop through the graph, emit `rail_paths.json` (simplified, rounded, station-endpoint-stitched, oriented idA→idB) and `rail_paths_report.json`.

**Files:**
- Modify: `pipeline/railpaths.py`
- Test: `tests/test_railpaths.py`

**Acceptance Criteria:**
- [ ] `route(graph, start, goal)` returns the min-cost polyline (A*, admissible heuristic geodesic÷320 km/h) or None when unreachable.
- [ ] Speed-weighted routing picks the fast bypass over the shorter slow line in the synthetic network.
- [ ] `assemble_paths` output: key `"idA|idB"` (idA<idB), value `[[lon,lat],…]` rounded to 5 decimals, Douglas-Peucker-simplified (tolerance 0.0003° — TUNING POINT), first/last points are the exact station coordinates.
- [ ] Unroutable hops and hops with unsnapped endpoints land in the failures list with reasons; `write_outputs` writes both JSON files, report includes summary counts.

**Verify:** `uv run pytest tests/test_railpaths.py -q` → all pass.

**Steps:**

- [ ] **Step 1: Write the failing tests** (append to `tests/test_railpaths.py`)

```python
from pipeline.railpaths import assemble_paths, route, write_outputs


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: FAIL — `ImportError: cannot import name 'assemble_paths'`

- [ ] **Step 3: Write the implementation** — `import heapq` and the `LineString` import go into the TOP import block (merge with the existing `from shapely.geometry import Point` line); the rest is appended:

```python
import heapq

from shapely.geometry import LineString, Point  # replaces the Point-only import

SIMPLIFY_TOLERANCE_DEG = 0.0003  # ~30 m; TUNING POINT (spec §1)


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: all pass (13 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/railpaths.py tests/test_railpaths.py
git commit -m "feat(pipeline): route hops through rail graph and emit rail_paths.json"
```

---

## Task 4: OSM I/O — Geofabrik download, pyosmium reader, CLI `ose paths`

**Goal:** The thin I/O layer: cached per-country Geofabrik downloads, two-pass pyosmium extraction of `railway=rail` ways + their node locations, the `build_rail_paths` orchestrator, CLI subcommand, dependency, justfile.

**Files:**
- Modify: `pipeline/railpaths.py`
- Modify: `pipeline/cli.py`
- Modify: `pyproject.toml` (add `"osmium>=3.7"` to `dependencies`)
- Modify: `justfile` (pipeline recipe gains `&& uv run ose paths`)
- Test: `tests/test_railpaths.py`

**Acceptance Criteria:**
- [ ] `GEOFABRIK_REGION` maps every country code present in `data/out/stations.json` (AT BE CH CZ DE DK ES FR GB HR HU IT LI LT LU NL PL PT RO SI SK UA); `needed_countries` derives the set from hop-participating stations and logs unmapped codes into the report rather than crashing.
- [ ] `download_extracts` skips existing files unless `force=True`, downloads to a `.part` file first, and rejects a download whose size differs from the server's Content-Length (truncated-download lesson, 2026-07-14).
- [ ] Two-pass PBF read: pass 1 collects `railway=rail` ways (deduped by way id across country extracts — border ways appear twice); pass 2 collects only referenced node locations.
- [ ] `ose paths [--force-download]` runs end-to-end; network functions stay untested (unit tests cover region mapping, country derivation, and cache-skip logic only).

**Verify:** `uv run pytest tests/test_railpaths.py -q` → pass; `uv run ose paths --help` → shows the subcommand.

**Steps:**

- [ ] **Step 1: Add dependency**

In `pyproject.toml` `dependencies`, after `"shapely>=2.0",` add:

```toml
    "osmium>=3.7",
```

Run: `uv sync` → resolves and installs pyosmium.

- [ ] **Step 2: Write the failing tests** (append to `tests/test_railpaths.py`)

```python
from pipeline.railpaths import GEOFABRIK_REGION, download_extracts, needed_countries

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_railpaths.py -q`
Expected: FAIL — `ImportError: cannot import name 'GEOFABRIK_REGION'`

- [ ] **Step 4: Write the implementation** — `import urllib.request` goes into the TOP import block; `import osmium` stays function-local (heavy, lazy, matching cli.py's pattern); the rest is appended:

```python
import urllib.request

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
    pbf_paths = download_extracts(countries, osm_dir, force_download)
    ways, node_locs = read_rail_network(pbf_paths)
    hop_station_ids = sorted(
        {sid for pair in hops for sid in pair if sid in stations_by_id})
    snapped, snap_failures = snap_stations(
        [stations_by_id[sid] for sid in hop_station_ids], node_locs)
    graph = build_graph(ways, node_locs, extra_junctions=set(snapped.values()))
    paths, hop_failures = assemble_paths(hops, snapped, graph, stations_by_id)
    write_outputs(out_dir, paths, snap_failures, hop_failures)
```

- [ ] **Step 5: Wire the CLI** — in `pipeline/cli.py`, after the `compute` subparser add:

```python
    p = sub.add_parser("paths", help="derive real rail geometry for reach-line hops")
    p.add_argument("--force-download", action="store_true",
                   help="re-download cached OSM extracts")
```

and after the `compute` dispatch branch add:

```python
    elif args.cmd == "paths":
        from pipeline.railpaths import build_rail_paths

        build_rail_paths(OUT, Path("data/osm"), force_download=args.force_download)
```

- [ ] **Step 6: Update justfile** pipeline recipe:

```make
pipeline:
    uv run ose fetch && uv run ose build && uv run ose compute && uv run ose paths
```

- [ ] **Step 7: Run tests + ruff**

Run: `uv run pytest tests/test_railpaths.py -q && uv run ruff check . && uv run ose paths --help`
Expected: tests pass, ruff clean, help shows `--force-download`.

- [ ] **Step 8: Commit**

```bash
git add pipeline/railpaths.py pipeline/cli.py pyproject.toml uv.lock justfile tests/test_railpaths.py
git commit -m "feat(pipeline): ose paths — Geofabrik OSM ingest and rail-path build"
```

---

## Task 5: server — `/api/rail-paths` endpoint

**Goal:** Serve `rail_paths.json` with the established 404-when-missing pattern (gzip comes free from the existing middleware).

**Files:**
- Modify: `server/app.py` (inside `create_app`, after the `cities` endpoint)
- Test: `tests/test_server.py`

**Acceptance Criteria:**
- [ ] `GET /api/rail-paths` returns the file content when present, 404 when absent.

**Verify:** `uv run pytest tests/test_server.py -q` → pass.

**Steps:**

- [ ] **Step 1: Write the failing tests** — follow the existing pattern in `tests/test_server.py` (`TestClient(create_app(tmp_path))`); append:

```python
def test_rail_paths_served(tmp_path):
    (tmp_path / "rail_paths.json").write_text(
        '{"attribution": "© OpenStreetMap contributors (ODbL)", "paths": {"a|b": [[0, 0], [1, 1]]}}',
        encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    body = client.get("/api/rail-paths").json()
    assert body["paths"]["a|b"] == [[0, 0], [1, 1]]


def test_rail_paths_404_when_missing(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/rail-paths").status_code == 404
```

(Adjust imports only if `tests/test_server.py` doesn't already import `TestClient` and `create_app` — it does.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — 404 assertion holds but the served test fails with 404.

- [ ] **Step 3: Implement** — in `server/app.py` after the `cities` endpoint:

```python
    @app.get("/api/rail-paths")
    def rail_paths() -> dict:
        path = data_dir / "rail_paths.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="No rail path data")
        return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/app.py tests/test_server.py
git commit -m "feat(server): serve rail_paths.json at /api/rail-paths"
```

---

## Task 6: web — geojson rework: rail-path lookup, delete corridors + chaikin

**Goal:** `legSegments` (and everything above it) consumes a `RailPathLookup`; corridors and chaikin are gone.

**Files:**
- Modify: `web/src/lib/geojson.ts`
- Delete: `web/src/lib/corridors.ts`, `web/src/lib/corridors.test.ts`
- Modify: `web/src/lib/geojson.test.ts` (drop corridor/chaikin cases, add lookup cases)

**Acceptance Criteria:**
- [ ] `legSegments(leg, stationsById, railPaths)`: every consecutive stop pair (nonstop leg = its single from→to pair) uses lookup geometry when present, straight line otherwise.
- [ ] Lookup geometry is stored oriented `idA→idB` (idA < idB); when the hop travels `idB→idA` the coords are reversed (non-mutating).
- [ ] `chaikin`, `corridorPath`, `CORRIDORS` and their tests no longer exist; `journeyLegPaths`, `segmentsGeoJSON`, `linesGeoJSON` all thread the new parameter.
- [ ] `railPaths = null` reproduces today's straight-line rendering exactly (minus corridors).

**Verify:** `cd web && npx vitest run src/lib/geojson.test.ts` → pass; `npx tsc -b` (via `npm run build`) → no type errors *in lib* (Map.tsx call sites are fixed in Task 7 — run the full build there).

**Steps:**

- [ ] **Step 1: Update tests** — in `web/src/lib/geojson.test.ts`: delete every test that imports or exercises `chaikin`, `corridorPath`, or corridor-following behavior; keep/adjust trunk-dedup and exact-vertex tests by passing `null` as the new third/fifth argument. Add:

```typescript
import { legSegments, journeyLegPaths, type RailPathLookup } from "./geojson";
import type { Leg, Station } from "./types";

const S = (id: string, lon: number, lat: number): [string, Station] =>
  [id, { id, name: id, lon, lat, country: "XX", has_reach: true }];
const byId = new Map<string, Station>([S("a", 0, 0), S("b", 1, 0), S("c", 2, 0)]);
const leg = (from: string, to: string, via: string[]): Leg =>
  ({ train: "T", dep: "", arr: "", from, to, via });

describe("legSegments with rail paths", () => {
  const railPaths: RailPathLookup = new Map([
    ["a|b", [[0, 0], [0.5, 0.4], [1, 0]]],
  ]);

  it("uses lookup geometry for a hop when present", () => {
    expect(legSegments(leg("a", "b", []), byId, railPaths)[0].coords)
      .toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
  });

  it("reverses geometry when the hop travels against key order", () => {
    expect(legSegments(leg("b", "a", []), byId, railPaths)[0].coords)
      .toEqual([[1, 0], [0.5, 0.4], [0, 0]]);
    // Original lookup entry must not be mutated by the reversal.
    expect(railPaths.get("a|b")![0]).toEqual([0, 0]);
  });

  it("falls back to a straight line for hops without geometry", () => {
    expect(legSegments(leg("b", "c", []), byId, railPaths)[0].coords)
      .toEqual([[1, 0], [2, 0]]);
  });

  it("splits a via-leg into per-hop segments, each with its own lookup", () => {
    const segments = legSegments(leg("a", "c", ["b"]), byId, railPaths);
    expect(segments.map((s) => s.key)).toEqual(["a|b", "b|c"]);
    expect(segments[0].coords).toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
    expect(segments[1].coords).toEqual([[1, 0], [2, 0]]);
  });

  it("journeyLegPaths threads geometry and keeps stops as exact vertices", () => {
    const journey = { trains: 1, duration_min: 60, legs: [leg("a", "c", ["b"])] };
    expect(journeyLegPaths(journey, byId, railPaths))
      .toEqual([[[0, 0], [0.5, 0.4], [1, 0], [2, 0]]]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/geojson.test.ts`
Expected: FAIL — `legSegments` doesn't accept a third argument / `RailPathLookup` not exported.

- [ ] **Step 3: Rework `geojson.ts`**

Remove `import { CORRIDORS, corridorPath } from "./corridors";` and the whole `chaikin` function. Replace `legSegments` with:

```typescript
/** Precomputed real-track geometry per physical hop, keyed by segmentKey and
 *  stored oriented idA→idB (idA < idB). Built by `ose paths` (backlog I). */
export type RailPathLookup = Map<string, [number, number][]>;

function hopCoords(
  a: { id: string; station: Station }, b: { id: string; station: Station },
  railPaths: RailPathLookup | null,
): [number, number][] {
  const geometry = railPaths?.get(segmentKey(a.id, b.id));
  if (geometry && geometry.length >= 2) {
    return a.id < b.id ? geometry : [...geometry].reverse();
  }
  return [[a.station.lon, a.station.lat], [b.station.lon, b.station.lat]];
}

export function legSegments(
  leg: Leg, stationsById: Map<string, Station>, railPaths: RailPathLookup | null,
): LegSegment[] {
  const stops = [leg.from, ...leg.via, leg.to]
    .map((id) => ({ id, station: stationsById.get(id) }))
    .filter((x): x is { id: string; station: Station } => x.station !== undefined);
  if (stops.length < 2) return [];
  const segments: LegSegment[] = [];
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    segments.push({ key: segmentKey(a.id, b.id), coords: hopCoords(a, b, railPaths) });
  }
  return segments;
}
```

Thread the parameter through (keep the existing doc comments, minus corridor/chaikin mentions):

```typescript
export function journeyLegPaths(
  j: Journey, stationsById: Map<string, Station>, railPaths: RailPathLookup | null,
): [number, number][][] {
  return j.legs
    .map((leg) => legSegments(leg, stationsById, railPaths))
    .filter((segments) => segments.length > 0)
    .map((segments) => segments.flatMap((s, i) => (i === 0 ? s.coords : s.coords.slice(1))));
}
```

`segmentsGeoJSON` and `linesGeoJSON` each gain a final `railPaths: RailPathLookup | null` parameter and pass it to their internal `legSegments` / `journeyLegPaths` calls. No other logic changes.

Then delete the corridor files:

```bash
git rm web/src/lib/corridors.ts web/src/lib/corridors.test.ts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/geojson.test.ts`
Expected: pass. (`npx vitest run` for the whole suite still fails in Map-adjacent files until Task 7 — expected; other lib suites must pass.)

- [ ] **Step 5: Commit**

```bash
git add -A web/src/lib
git commit -m "feat(web): reach lines consume precomputed rail-path geometry; retire corridors"
```

---

## Task 7: web — fetch + thread rail paths (types, api, App, Map)

**Goal:** The lookup is fetched once at startup, degrades to null on failure, and reaches every geometry consumer.

**Files:**
- Modify: `web/src/lib/types.ts`, `web/src/lib/api.ts`, `web/src/App.tsx`, `web/src/components/Map.tsx`

**Acceptance Criteria:**
- [ ] `api.getRailPaths()` hits `/api/rail-paths`; App stores `Map<string, [number,number][]> | null`, `null` on any fetch error (no user-facing error — straight lines are the documented fallback).
- [ ] `Map.tsx` receives `railPaths` as a prop; `syncData` and the rider effect re-run when it arrives, so lines upgrade from straight to real geometry post-load.
- [ ] Full web test suite and production build pass.

**Verify:** `cd web && npx vitest run && npm run build` → all green.

**Steps:**

- [ ] **Step 1: types.ts** — append:

```typescript
export interface RailPathsFile {
  attribution: string;
  paths: Record<string, [number, number][]>;
}
```

- [ ] **Step 2: api.ts** — add to the `api` object:

```typescript
  getRailPaths: () => get<RailPathsFile>("/api/rail-paths"),
```

and add `RailPathsFile` to the type import.

- [ ] **Step 3: App.tsx** — add state + fetch (import `RailPathLookup` from `./lib/geojson`):

```typescript
const [railPaths, setRailPaths] = useState<RailPathLookup | null>(null);
```

In the initial-load `useEffect` (alongside `getStations`/`getCities`):

```typescript
    api.getRailPaths()
      .then((r) => setRailPaths(new Map(Object.entries(r.paths))))
      .catch(() => setRailPaths(null)); // straight-line fallback, by design
```

Pass `railPaths={railPaths}` to `<MapView …>`.

- [ ] **Step 4: Map.tsx** — add `railPaths: RailPathLookup | null;` to `Props` (import the type from `../lib/geojson`). Update the three call sites:
  - in `syncData`: `linesGeoJSON(reach, byId, maxTrains, maxMinutes, railPaths)` and `segmentsGeoJSON(reach, byId, maxTrains, maxMinutes, railPaths)` (destructure `railPaths` from `propsRef.current`); add `props.railPaths` to the `useEffect(syncData, […])` dependency array.
  - in the rider effect (~line 461): `journeyLegPaths(journey, byId, propsRef.current.railPaths)`; add `props.railPaths` to that effect's dependency array.

- [ ] **Step 5: Verify**

Run: `cd web && npx vitest run && npm run build`
Expected: all tests pass, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add web/src
git commit -m "feat(web): fetch rail-path lookup and thread it to map + rider"
```

---

## Task 8: AE — target-mode chooser: no city entries, reachability ranking

**Goal:** Target-mode overlap popups can no longer change the origin, and rank stations by fewest trains from the current origin.

**Files:**
- Modify: `web/src/lib/overlap.ts`
- Modify: `web/src/components/Map.tsx` (`showOverlapChoice`)
- Modify: `web/src/index.css`
- Test: `web/src/lib/overlap.test.ts`

**Acceptance Criteria:**
- [ ] `reachableMinTrains(reach, maxTrains, maxMinutes)` → `Map<destId, fewest trains>` among journeys within BOTH filters (note: fewest trains, not the fastest journey's train count).
- [ ] `rankTargetChoices(choices, minTrainsById)` → reachable first (minTrains asc), then `nDest` desc, name, id; unreachable last with `minTrains: null`, same secondary ordering.
- [ ] In target mode (`armed === "to"`), the popup renders NO "(all stations)" city buttons; unreachable entries get class `unreachable`, a "not reachable" hint span, and remain clickable (existing `onStationClick` no-route handling shows the hint). Origin mode is byte-for-byte unchanged.

**Verify:** `cd web && npx vitest run src/lib/overlap.test.ts` → pass; full suite green.

**Steps:**

- [ ] **Step 1: Write the failing tests** (append to `web/src/lib/overlap.test.ts`)

```typescript
import { rankTargetChoices, reachableMinTrains, type StationChoice } from "./overlap";
import type { ReachFile } from "./types";

const choice = (id: string, name: string, nDest: number): StationChoice =>
  ({ pick: { type: "dest", id }, name, nDest });

describe("reachableMinTrains", () => {
  const reach = {
    origin: "o", computed_at: "", sample_date: "",
    destinations: [
      { id: "d1", direct_per_day: 1, journeys: [
        { trains: 2, duration_min: 100, legs: [] },
        { trains: 3, duration_min: 80, legs: [] },   // faster but more trains
      ]},
      { id: "d2", direct_per_day: 1, journeys: [
        { trains: 1, duration_min: 999, legs: [] },  // over the time filter
      ]},
    ],
  } as ReachFile;

  it("returns the FEWEST trains among journeys within both filters", () => {
    expect(reachableMinTrains(reach, 3, 200).get("d1")).toBe(2);
  });

  it("excludes destinations outside the time or trains filter", () => {
    expect(reachableMinTrains(reach, 3, 200).has("d2")).toBe(false);
    expect(reachableMinTrains(reach, 1, 200).has("d1")).toBe(false);
  });

  it("is empty without a reach", () => {
    expect(reachableMinTrains(null, 3, 200).size).toBe(0);
  });
});

describe("rankTargetChoices", () => {
  it("orders reachable by fewest trains, then size; unreachable last", () => {
    const ranked = rankTargetChoices(
      [choice("far", "Far", 90), choice("near", "Near", 10),
       choice("none", "None", 99), choice("big", "Big", 80)],
      new Map([["far", 2], ["near", 1], ["big", 1]]),
    );
    expect(ranked.map((c) => c.pick.id)).toEqual(["big", "near", "far", "none"]);
    expect(ranked[3].minTrains).toBeNull();
  });

  it("breaks full ties by name then id", () => {
    const ranked = rankTargetChoices(
      [choice("b", "Same", 5), choice("a", "Same", 5)],
      new Map([["a", 1], ["b", 1]]),
    );
    expect(ranked.map((c) => c.pick.id)).toEqual(["a", "b"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/overlap.test.ts`
Expected: FAIL — missing exports.

- [ ] **Step 3: Implement in `overlap.ts`** (append; add `import type { MaxTrains } from "./geojson";` and `import type { ReachFile } from "./types";`):

```typescript
export interface TargetChoice extends StationChoice {
  /** Fewest trains from the current origin under active filters; null = unreachable. */
  minTrains: number | null;
}

/** Fewest trains per destination among journeys within BOTH active filters.
 *  Deliberately not bestJourney(): that is the fastest journey, whose train
 *  count can exceed the minimum (backlog AE — "steps to reach"). */
export function reachableMinTrains(
  reach: ReachFile | null, maxTrains: MaxTrains, maxMinutes: number,
): Map<string, number> {
  const result = new Map<string, number>();
  if (!reach) return result;
  for (const d of reach.destinations) {
    const eligible = d.journeys.filter(
      (j) => j.trains <= maxTrains && j.duration_min <= maxMinutes);
    if (eligible.length) result.set(d.id, Math.min(...eligible.map((j) => j.trains)));
  }
  return result;
}

/** Target-mode ordering (backlog AE): reachable first by fewest trains, then
 *  connection count; unreachable last, muted but still selectable. */
export function rankTargetChoices(
  choices: StationChoice[], minTrainsById: Map<string, number>,
): TargetChoice[] {
  return choices
    .map((c) => ({ ...c, minTrains: minTrainsById.get(c.pick.id) ?? null }))
    .sort((a, b) => {
      if ((a.minTrains === null) !== (b.minTrains === null)) {
        return a.minTrains === null ? 1 : -1;
      }
      if (a.minTrains !== null && b.minTrains !== null && a.minTrains !== b.minTrains) {
        return a.minTrains - b.minTrains;
      }
      return b.nDest - a.nDest
        || a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
        || a.pick.id.localeCompare(b.pick.id);
    });
}
```

- [ ] **Step 4: Rework `showOverlapChoice` in Map.tsx** — replace the city-button loop and choice loop with a mode split (imports: `rankTargetChoices`, `reachableMinTrains`, `type TargetChoice` from `../lib/overlap`):

```typescript
      function showOverlapChoice(
        choices: ReturnType<typeof overlapStationChoices>, lngLat: maplibregl.LngLat,
      ) {
        const content = document.createElement("div");
        content.className = "overlap-station-popup";
        content.setAttribute("role", "group");
        content.setAttribute("aria-label", "Choose a station");
        const targeting = propsRef.current.armed === "to";
        if (!targeting) {
          // Origin mode keeps city union entries (bug AE: these buttons set the
          // ORIGIN, so they must never render while picking a target).
          const cityChoices = new Map<string, string[]>();
          for (const choice of choices) {
            const city = cityForStation(choice.pick.id, propsRef.current.cityGroups);
            if (city) cityChoices.set(city.city, city.memberIds);
          }
          for (const [city, memberIds] of [...cityChoices].sort(([a], [b]) => a.localeCompare(b))) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "overlap-station-popup-city";
            button.textContent = `${city} (all stations)`;
            button.setAttribute("aria-label", `Select all ${city} stations`);
            button.addEventListener("click", (event) => {
              event.stopPropagation();
              popup.remove();
              if (cityPopup.current === popup) cityPopup.current = null;
              propsRef.current.onSelectCityOrigin(city, memberIds);
            });
            content.append(button);
          }
        }
        const ordered: (StationChoice | TargetChoice)[] = targeting
          ? rankTargetChoices(choices, reachableMinTrains(
              propsRef.current.reach, propsRef.current.maxTrains,
              propsRef.current.maxMinutes))
          : choices;
        for (const choice of ordered) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = choice.name;
          button.setAttribute("aria-label", `Select ${choice.name}`);
          if (targeting && (choice as TargetChoice).minTrains === null) {
            button.classList.add("unreachable");
            button.setAttribute("aria-label",
              `Select ${choice.name} (not reachable with current filters)`);
            const hint = document.createElement("span");
            hint.className = "overlap-unreachable-hint";
            hint.textContent = "not reachable";
            button.append(hint);
          }
          button.addEventListener("click", (event) => {
            event.stopPropagation();
            popup.remove();
            if (cityPopup.current === popup) cityPopup.current = null;
            selectStation(choice.pick);
          });
          content.append(button);
        }
        const popup = new maplibregl.Popup({
          closeButton: false, closeOnClick: false, className: "overlap-station-map-popup",
        })
          .setLngLat(lngLat)
          .setDOMContent(content)
          .addTo(m);
        cityPopup.current = popup;
      }
```

(`StationChoice` type import comes from `../lib/overlap` too.)

- [ ] **Step 5: CSS** — append to `web/src/index.css` near the existing `.overlap-station-popup` rules:

```css
.overlap-station-popup button.unreachable { opacity: 0.55; }
.overlap-station-popup .overlap-unreachable-hint {
  font-size: 0.8em; font-style: italic; opacity: 0.8; margin-left: 0.4em;
}
```

- [ ] **Step 6: Verify**

Run: `cd web && npx vitest run && npm run build`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add web/src
git commit -m "fix(web): target chooser drops city entries and ranks by reachability (AE)"
```

---

## Task 9: end-to-end — real `ose paths` run, size check, full verification

**Goal:** Real geometry generated from the live dataset, everything green, ready for the user's visual pass.

**Files:**
- No new source files. Generated: `data/out/rail_paths.json`, `data/out/rail_paths_report.json`, `data/osm/*.osm.pbf` (cache — ensure `data/osm` is gitignored; check `.gitignore` covers it, add `data/osm/` if not).

**Acceptance Criteria:**
- [ ] `uv run ose paths` completes on the real data (first run downloads ~15–20 GB across ~20 country extracts; long — run in background, don't kill it).
- [ ] `rail_paths.json` exists; report shows paths ≫ failures (spot-check a few failures for legitimacy, e.g. UK/ferry oddities); file size measured — if > ~8 MB raw, flag for the encoded-polyline follow-up (spec §1), do NOT implement it now.
- [ ] `uv run pytest -q` all pass, `uv run ruff check .` clean, `cd web && npx vitest run` all pass, `npm run build` OK.
- [ ] Server smoke test: `uv run uvicorn server.app:app --port 8000` + `curl -s localhost:8000/api/rail-paths | head -c 300` shows attribution + paths.
- [ ] Report presented to the user for the human visual pass (paths visible, track-following, rider on track — closes the "paths not showing" report or surfaces its real cause). Ask the user to also confirm "© OpenStreetMap contributors" is visible in the map attribution control (ODbL, spec §2).

**Verify:** commands above, in order.

**Steps:**

- [ ] **Step 1:** Check `.gitignore` covers `data/osm/` (add if missing, commit with the run below).
- [ ] **Step 2:** Run `uv run ose paths` (background; expect the download to dominate wall time; verify each extract's size against Geofabrik's Content-Length — the code enforces this).
- [ ] **Step 3:** Inspect `data/out/rail_paths_report.json` summary; `du -h data/out/rail_paths.json`.
- [ ] **Step 4:** Full suites + build + server smoke test (commands in acceptance criteria).
- [ ] **Step 5:** Commit any `.gitignore` change; leave `data/out/*` generated artifacts uncommitted (user's standing call). Report results + ask the user to eyeball the map.

---

## Execution order & dependencies

- Tasks 1→2→3→4 are sequential (pipeline).
- Task 5 (server) is independent.
- Tasks 6→7 are sequential (web geometry); Task 8 (AE) is independent of 6/7.
- Task 9 last, after everything.
