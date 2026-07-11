# Veil Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 42-country Europe-only per-feature veil with a world-wide dissolved (single-MultiPolygon) veil built from Natural Earth 10m data via shapely, add a feathered edge line layer, remove the legend entry, and replace the per-country tooltip with a generic constant.

**Architecture:** A one-off `npx mapshaper` command produces `pipeline/assets/countries_world_10m.geojson` (~250 admin-0 features, only `ISO_A2_EH`). `build_coverage` uses shapely `unary_union` to dissolve non-covered features into a single MultiPolygon, emitting a one-feature FeatureCollection (ocean never veiled). The frontend drops its `covered == false` filter (source is now veil-only), adds a blurred `coverage-veil-edge` line layer for feathering, removes the legend entry, and exports a `VEIL_TOOLTIP` constant (no country name). Tests are updated to match the new single-feature output and the removed/changed exports.

**Tech Stack:** Python 3.14 (uv, pydantic, FastAPI, shapely), pytest; React + TypeScript + MapLibre GL, vitest, oxlint; npx mapshaper (one-off asset build).

## Global Constraints

- **Python uv-only.** Run everything through `uv run …`. Never invoke `python`/`pytest`/`ruff` directly.
- **Lint/format clean on touched files.** `uv run ruff check <files>` AND `uv run ruff format --check <files>` must both pass. Line length 100. Ruff lint selects `E, F, I, W`.
- **TDD.** Write the failing test first, watch it fail, implement minimally, watch it pass. Commit after every task with the exact commit command given.
- **Never run `ose fetch`.** Raw feed zips already exist in `data/raw/`.
- **Current baselines:** 136 pytest tests, 34 web tests. These counts must change ONLY by the deltas described in each task (tests added minus tests removed).
- **The user does visual checks.** Acceptance is at data/API/unit-test level only. Do not claim visual verification.
- **Subagent models:** opus or sonnet only, never haiku.
- **Exact tooltip copy:** `May be reachable by international trains from other countries, but we don't yet have data from this country's rail providers.`
- **The existing `countries_europe_50m.geojson` is untouched.** `geo.py` station→country assignment keeps using it. Two assets, two jobs.

---

## File Structure

**Create:**
- `pipeline/assets/countries_world_10m.geojson` — one-off mapshaper-built world asset (~250 admin-0 features, only `ISO_A2_EH`).

**Modify:**
- `pipeline/coverage.py` — new asset path constant, shapely-based dissolved veil, `COUNTRY_NAMES` deleted.
- `pipeline/compute.py` — no code change needed (import and call site remain valid).
- `pyproject.toml` — add `shapely` dependency.
- `tests/test_coverage.py` — rewrite for single-feature dissolved output, shapely point-in-polygon checks.
- `tests/test_server.py` — coverage endpoint test updated for single-feature output.
- `web/src/lib/coverage.ts` — `VEIL_LEGEND` deleted, `veilFilter()` deleted, `coverageTooltip(name)` replaced by `VEIL_TOOLTIP` constant.
- `web/src/lib/coverage.test.ts` — filter tests removed, tooltip constant asserted, precedence tests unchanged.
- `web/src/lib/types.ts` — `CoverageFeature.properties` simplified (no `name`, no `covered`, no `ISO_A2_EH`).
- `web/src/components/Map.tsx` — filter removed from fill layer, new `coverage-veil-edge` line layer, tooltip uses `VEIL_TOOLTIP`.
- `web/src/components/Legend.tsx` — veil legend entry removed.

---

## Task 1: World asset + pipeline dissolved veil

Implements spec §1 (one-off world asset) and §2 (shapely dissolved veil in `build_coverage`). The mapshaper command is run once to produce the committed asset. Then `pipeline/coverage.py` is reworked: `COUNTRY_NAMES` deleted, a new `WORLD_ASSET` constant points to the new file, and `build_coverage` uses shapely to union non-covered features into a single Feature. `shapely` is added as a dependency.

**Files:**
- Create: `pipeline/assets/countries_world_10m.geojson`
- Modify: `pipeline/coverage.py`
- Modify: `pyproject.toml:6-11`
- Modify: `tests/test_coverage.py`
- Modify: `tests/test_server.py:50-56`

**Interfaces:**
- Consumes: `pipeline.config.load_feeds(path) -> dict[str, FeedConfig]` (each `FeedConfig` has a `.country: str`); `pipeline.geo.ASSET` (unchanged, still used by `geo.py` only).
- Produces:
  - `WORLD_ASSET: Path` — path to `pipeline/assets/countries_world_10m.geojson`.
  - `build_coverage(covered: set[str], asset_path: Path = WORLD_ASSET) -> dict` — returns a GeoJSON FeatureCollection with **one Feature** (MultiPolygon, empty `properties: {}`). The geometry is the shapely `unary_union` of all country polygons whose ISO code is NOT in `covered`. Ocean is never veiled.
  - `covered_from_feeds(feeds_path: Path) -> set[str]` — unchanged.
  - `compute_all` still writes `data/out/coverage.json`.

- [ ] **Step 1: Build the world asset with mapshaper**

Download the Natural Earth 10m admin-0 countries GeoJSON and run mapshaper to produce the simplified asset:

```bash
# Download NE 10m admin-0 (public domain, ~30 MB)
curl -L -o /tmp/ne_10m_admin_0_countries.geojson \
  "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"

# Simplify with mapshaper: keep only ISO_A2_EH, simplify 40% visvalingam,
# round coordinates to 4 decimals (~11 m)
npx -y mapshaper /tmp/ne_10m_admin_0_countries.geojson \
  -filter-fields ISO_A2_EH \
  -simplify visvalingam 40% keep-shapes \
  -o precision=0.0001 format=geojson \
  pipeline/assets/countries_world_10m.geojson
```

Expected: `pipeline/assets/countries_world_10m.geojson` exists, ≤ ~5 MB, with ~260 features each having only `ISO_A2_EH` in properties. Some features have `ISO_A2_EH: "-99"` (NE quirk for France/Norway); these are fine — the pipeline filters by code.

Verify:

```bash
uv run python -c "
import json, os
fc = json.load(open('pipeline/assets/countries_world_10m.geojson'))
feats = fc['features']
print(f'{len(feats)} features')
# Verify only ISO_A2_EH in properties
keys = {k for f in feats for k in f['properties']}
assert keys == {'ISO_A2_EH'}, keys
size_mb = os.path.getsize('pipeline/assets/countries_world_10m.geojson') / 1_000_000
print(f'{size_mb:.1f} MB')
assert size_mb <= 6, f'Too large: {size_mb} MB'
print('asset OK')
"
```

- [ ] **Step 2: Add shapely dependency**

In `pyproject.toml`, change the `dependencies` list from:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.8",
]
```

to:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.8",
    "shapely>=2.0",
]
```

Then sync the lock file:

```bash
uv sync
```

Expected: `uv sync` installs shapely and exits 0.

- [ ] **Step 3: Write the failing pipeline tests**

Replace the entire contents of `tests/test_coverage.py` with:

```python
import json
from datetime import date

from shapely.geometry import Point, shape

from pipeline.build import build
from pipeline.compute import compute_all
from pipeline.coverage import WORLD_ASSET, build_coverage, covered_from_feeds
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


def test_build_coverage_returns_single_feature_featurecollection():
    fc = build_coverage({"DE", "FR"})
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    feat = fc["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert feat["properties"] == {}


def test_veil_excludes_covered_country():
    """A point inside Germany (covered) must fall OUTSIDE the veil geometry."""
    fc = build_coverage({"DE"})
    veil = shape(fc["features"][0]["geometry"])
    berlin = Point(13.4, 52.5)
    assert not veil.contains(berlin)


def test_veil_includes_non_covered_country():
    """A point inside Italy (not covered) must fall INSIDE the veil geometry."""
    fc = build_coverage({"DE"})
    veil = shape(fc["features"][0]["geometry"])
    rome = Point(12.5, 41.9)
    assert veil.contains(rome)


def test_veil_excludes_ocean():
    """A point in the Atlantic Ocean must fall OUTSIDE the veil geometry."""
    fc = build_coverage(set())
    veil = shape(fc["features"][0]["geometry"])
    atlantic = Point(-30.0, 40.0)
    assert not veil.contains(atlantic)


def test_covered_from_feeds_reads_country_fields(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    assert covered_from_feeds(feeds_toml) == {"LA", "BO"}


def test_compute_writes_coverage_json_single_feature(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    countries_toml, names_toml = empty_overrides(tmp_path)
    graph = tmp_path / "graph"
    out = tmp_path / "out"
    build(
        raw,
        graph,
        feeds_toml,
        None,
        date(2026, 7, 14),
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(graph, out, workers=1, feeds_path=feeds_toml)
    cov = json.loads((out / "coverage.json").read_text())
    assert cov["type"] == "FeatureCollection"
    assert len(cov["features"]) == 1
    assert cov["features"][0]["properties"] == {}
    # coverage.json is not a reach_*.json file, so the stale-reach prune leaves it.
    assert (out / "coverage.json").exists()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_coverage.py -q`
Expected: FAIL — `ImportError: cannot import name 'WORLD_ASSET' from 'pipeline.coverage'` (collection error).

- [ ] **Step 5: Rewrite `pipeline/coverage.py`**

Replace the entire contents of `pipeline/coverage.py` with:

```python
"""`coverage.json` emission: dissolve non-covered country polygons into a single
veil MultiPolygon that covers all land except covered countries.

World asset provenance: pipeline/assets/countries_world_10m.geojson is derived
from ne_10m_admin_0_countries.geojson (Natural Earth, public domain):
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson

Built one-off with:
  npx -y mapshaper ne_10m_admin_0_countries.geojson \\
    -filter-fields ISO_A2_EH \\
    -simplify visvalingam 40% keep-shapes \\
    -o precision=0.0001 format=geojson \\
    pipeline/assets/countries_world_10m.geojson

Properties reduced to ISO_A2_EH, simplified to 40% retention (visvalingam, keep-shapes),
coordinates rounded to 4 decimals (~11 m). The existing
countries_europe_50m.geojson is untouched — geo.py station->country assignment
keeps using it.
"""

import json
from pathlib import Path

from shapely import unary_union
from shapely.geometry import shape

from pipeline.config import load_feeds

WORLD_ASSET = Path(__file__).parent / "assets" / "countries_world_10m.geojson"


def build_coverage(covered: set[str], asset_path: Path = WORLD_ASSET) -> dict:
    """GeoJSON FeatureCollection with one Feature: a dissolved MultiPolygon of
    every country NOT in `covered`. Ocean is never veiled. Returns a single-
    feature FeatureCollection with empty properties."""
    fc = json.loads(asset_path.read_text(encoding="utf-8"))
    non_covered_geoms = []
    for f in fc["features"]:
        iso = f["properties"].get("ISO_A2_EH")
        if not iso or iso == "-99" or iso in covered:
            continue
        non_covered_geoms.append(shape(f["geometry"]))
    if not non_covered_geoms:
        return {"type": "FeatureCollection", "features": []}
    dissolved = unary_union(non_covered_geoms)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(json.dumps(dissolved.__geo_interface__)),
                "properties": {},
            }
        ],
    }


def covered_from_feeds(feeds_path: Path) -> set[str]:
    """The set of `country` fields declared across all feeds in a feeds.toml."""
    return {cfg.country for cfg in load_feeds(feeds_path).values()}
```

- [ ] **Step 6: Verify `pipeline/compute.py` needs no change**

In `pipeline/compute.py`, the import on line 19 reads:

```python
from pipeline.coverage import build_coverage, covered_from_feeds
```

This import stays the same — `build_coverage` and `covered_from_feeds` are still the exported names. The call site at line 134-135 (`build_coverage(covered)`) now defaults `asset_path` to `WORLD_ASSET` instead of the old Europe-only `ASSET`, which is the correct behavior. No code change in `compute.py`.

- [ ] **Step 7: Update `tests/test_server.py` for single-feature output**

In `tests/test_server.py`, replace the `test_coverage_endpoint` function (lines 50-56) from:

```python
def test_coverage_endpoint(client):
    r = client.get("/api/coverage")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 42
    assert all("name" in f["properties"] for f in fc["features"])
```

to:

```python
def test_coverage_endpoint(client):
    r = client.get("/api/coverage")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"] == {}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_coverage.py tests/test_server.py -q`
Expected: PASS — 6 coverage tests + all server tests green.

- [ ] **Step 9: Run the full pipeline suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: PASS — 137 tests (136 baseline − 5 old coverage tests + 6 new coverage tests).

- [ ] **Step 10: Lint and format the touched files**

Run: `uv run ruff check pipeline/coverage.py tests/test_coverage.py tests/test_server.py && uv run ruff format --check pipeline/coverage.py tests/test_coverage.py tests/test_server.py`
Expected: `All checks passed!` and no files listed as needing reformatting.
If `ruff format --check` reports a file, run `uv run ruff format <that file>` and re-run the check.

- [ ] **Step 11: Commit**

```bash
git add pipeline/assets/countries_world_10m.geojson pipeline/coverage.py pyproject.toml uv.lock tests/test_coverage.py tests/test_server.py
git commit -m "feat: world-wide dissolved veil via shapely + NE 10m asset"
```

---

## Task 2: Frontend — filter removed, feathered edge, tooltip constant, legend entry removed

Implements spec §3 and §4 (frontend and test changes). The `coverage-veil` fill layer drops its `covered == false` filter (the source now contains only veil geometry). A new `coverage-veil-edge` line layer adds feathered edges. `VEIL_LEGEND` and `veilFilter()` and `coverageTooltip(name)` are deleted; `VEIL_TOOLTIP` is the new export. The legend veil entry is removed. Tests are updated: filter tests removed, tooltip constant asserted, precedence tests kept.

**Files:**
- Modify: `web/src/lib/coverage.ts`
- Modify: `web/src/lib/coverage.test.ts`
- Modify: `web/src/lib/types.ts:14-22`
- Modify: `web/src/components/Map.tsx:7,48-57,96-106`
- Modify: `web/src/components/Legend.tsx`

**Interfaces:**
- Consumes: `GET /api/coverage` (Task 1) → a FeatureCollection with one Feature (MultiPolygon, empty properties).
- Produces (from `web/src/lib/coverage.ts`):
  - `VEIL_TOOLTIP: string` — the exact generic tooltip copy.
  - `showVeilTooltip(stationHitCount: number): boolean` — unchanged.

- [ ] **Step 1: Write the failing web tests**

Replace the entire contents of `web/src/lib/coverage.test.ts` with:

```ts
import { describe, expect, it } from "vitest";
import { VEIL_TOOLTIP, showVeilTooltip } from "./coverage";

describe("VEIL_TOOLTIP", () => {
  it("is the exact approved copy", () => {
    expect(VEIL_TOOLTIP).toBe(
      "May be reachable by international trains from other countries, but we don't yet have data from this country's rail providers.",
    );
  });
});

describe("showVeilTooltip", () => {
  it("shows when nothing selectable is under the cursor", () => {
    expect(showVeilTooltip(0)).toBe(true);
  });

  it("hides when a station or dot is under the cursor", () => {
    expect(showVeilTooltip(1)).toBe(false);
    expect(showVeilTooltip(3)).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/coverage.test.ts`
Expected: FAIL — `VEIL_TOOLTIP` is not exported from `./coverage` (the current module exports `VEIL_LEGEND`, `veilFilter`, `coverageTooltip`, `showVeilTooltip`).

- [ ] **Step 3: Rewrite `web/src/lib/coverage.ts`**

Replace the entire contents of `web/src/lib/coverage.ts` with:

```ts
// Pure helpers for the country-coverage veil.
// Spec: docs/superpowers/specs/2026-07-11-veil-rework-design.md §3.
// The veil source is now a single dissolved MultiPolygon (no per-country
// features), so the old filter and per-country tooltip are gone. The tooltip
// is a generic constant; the legend entry is removed (tooltip is the only
// explanation).

// Generic tooltip shown on hover over the veil (spec §3, exact copy).
export const VEIL_TOOLTIP =
  "May be reachable by international trains from other countries, but we don't yet have data from this country's rail providers.";

// Hover precedence: the veil tooltip appears only when no station/dot feature is
// under the cursor, so it never competes with the click-selection layers
// (pickfeature.ts precedence stays untouched). `stationHitCount` is the number of
// reach-dots/all-stations features MapLibre reports under the cursor.
export function showVeilTooltip(stationHitCount: number): boolean {
  return stationHitCount === 0;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/coverage.test.ts`
Expected: PASS — 3 passed (1 tooltip constant + 2 precedence tests).

- [ ] **Step 5: Simplify coverage types**

In `web/src/lib/types.ts`, replace lines 14-22 (the `CoverageFeature` and `CoverageCollection` interfaces) from:

```ts
export interface CoverageFeature {
  type: "Feature";
  geometry: unknown;
  properties: { ISO_A2_EH: string; name: string; covered: boolean };
}
export interface CoverageCollection {
  type: "FeatureCollection";
  features: CoverageFeature[];
}
```

to:

```ts
export interface CoverageFeature {
  type: "Feature";
  geometry: unknown;
  properties: Record<string, never>;
}
export interface CoverageCollection {
  type: "FeatureCollection";
  features: CoverageFeature[];
}
```

- [ ] **Step 6: Update `Map.tsx` — remove filter, add edge layer, update tooltip**

In `web/src/components/Map.tsx`, make the following changes:

(a) Change the import on line 7 from:

```ts
import { coverageTooltip, showVeilTooltip, veilFilter } from "../lib/coverage";
```

to:

```ts
import { VEIL_TOOLTIP, showVeilTooltip } from "../lib/coverage";
```

(b) Replace the `coverage-veil` layer definition (lines 48-57) from:

```ts
      m.addLayer(
        {
          id: "coverage-veil",
          type: "fill",
          source: "coverage",
          filter: veilFilter() as never,
          paint: { "fill-color": "#6b7280", "fill-opacity": 0.25 },
        },
        "all-stations",
      );
```

to:

```ts
      m.addLayer(
        {
          id: "coverage-veil",
          type: "fill",
          source: "coverage",
          paint: { "fill-color": "#6b7280", "fill-opacity": 0.25 },
        },
        "all-stations",
      );
      m.addLayer(
        {
          id: "coverage-veil-edge",
          type: "line",
          source: "coverage",
          paint: {
            "line-color": "#6b7280",
            "line-width": 2.5,
            "line-blur": 3,
            "line-opacity": 0.2,
          },
        },
        "all-stations",
      );
```

(c) Replace the tooltip handler (lines 96-106) from:

```ts
      const veilPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      m.on("mousemove", "coverage-veil", (e) => {
        const stationHits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS }).length;
        const name = e.features?.[0]?.properties?.name as string | undefined;
        if (!showVeilTooltip(stationHits) || !name) {
          veilPopup.remove();
          return;
        }
        veilPopup.setLngLat(e.lngLat).setText(coverageTooltip(name)).addTo(m);
      });
      m.on("mouseleave", "coverage-veil", () => veilPopup.remove());
```

to:

```ts
      const veilPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      m.on("mousemove", "coverage-veil", (e) => {
        const stationHits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS }).length;
        if (!showVeilTooltip(stationHits)) {
          veilPopup.remove();
          return;
        }
        veilPopup.setLngLat(e.lngLat).setText(VEIL_TOOLTIP).addTo(m);
      });
      m.on("mouseleave", "coverage-veil", () => veilPopup.remove());
```

- [ ] **Step 7: Remove veil entry from Legend**

Replace the entire contents of `web/src/components/Legend.tsx` with:

```tsx
import { BUCKET_COLORS, BUCKET_LABELS } from "../lib/colors";

export default function Legend() {
  return (
    <div className="legend">
      {BUCKET_COLORS.map((c, i) => (
        <span key={c}>
          <i style={{ background: c }} /> {BUCKET_LABELS[i]}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 8: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 34 baseline − 5 old coverage tests + 3 new coverage tests = 32 passed.

- [ ] **Step 9: Type-check and lint the web app**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors on the changed files.

- [ ] **Step 10: Commit**

```bash
git add web/src/lib/coverage.ts web/src/lib/coverage.test.ts web/src/lib/types.ts web/src/components/Map.tsx web/src/components/Legend.tsx
git commit -m "feat: dissolved veil with feathered edge, generic tooltip, legend entry removed"
```

---

## Task 3: Full verification

Runs the full pipeline and all acceptance checks against real data. This is the ONE place the full pipeline runs. Never run `ose fetch`; the raw zips already exist.

**Files:** none created or modified. This task runs the pipeline and verification commands only.

- [ ] **Step 1: Build the real graph**

Run: `uv run ose build`
Expected: ends with `graph: 1656 stations, 6057 trips -> data/graph`. If station/trip counts differ, STOP — the baseline changed and the plan's assumptions must be re-checked.

- [ ] **Step 2: Compute reachability + emit coverage.json**

Run: `uv run ose compute`
Expected: prints reach file lines, exits 0. Writes `data/out/coverage.json` among others. (CPU-heavy, may run several minutes.)

- [ ] **Step 3: Verify coverage.json is single-feature dissolved veil**

Run:

```bash
uv run python -c "
import json
from shapely.geometry import Point, shape
cov = json.load(open('data/out/coverage.json'))
assert cov['type'] == 'FeatureCollection'
assert len(cov['features']) == 1, f'Expected 1 feature, got {len(cov[\"features\"])}'
feat = cov['features'][0]
assert feat['properties'] == {}
veil = shape(feat['geometry'])
# Berlin (DE, covered) should be outside the veil
assert not veil.contains(Point(13.4, 52.5)), 'Berlin should not be veiled (DE is covered)'
# Rome (IT, not covered) should be inside the veil
assert veil.contains(Point(12.5, 41.9)), 'Rome should be veiled (IT is not covered)'
# Atlantic ocean should be outside the veil
assert not veil.contains(Point(-30.0, 40.0)), 'Ocean should not be veiled'
print('coverage.json OK: single dissolved feature, point-in-polygon checks pass')
"
```

Expected: `coverage.json OK: single dissolved feature, point-in-polygon checks pass`.

- [ ] **Step 4: Verify station/trip counts unchanged (baseline 1656/6057)**

Run:

```bash
uv run python -c "
import json
print('stations', len(json.load(open('data/out/stations.json'))['stations']))
print('trips', len(json.load(open('data/graph/trips.json'))['trips']))
"
```

Expected: `stations 1656` and `trips 6057`.

- [ ] **Step 5: Verify the endpoint 200/404**

Run:

```bash
uv run python -c "
from pathlib import Path
from fastapi.testclient import TestClient
from server.app import create_app
c = TestClient(create_app(Path('data/out')))
r = c.get('/api/coverage')
assert r.status_code == 200, r.status_code
fc = r.json()
assert fc['type'] == 'FeatureCollection'
assert len(fc['features']) == 1
assert fc['features'][0]['properties'] == {}
empty = TestClient(create_app(Path('/nonexistent')))
assert empty.get('/api/coverage').status_code == 404
print('endpoint OK: 200 with 1 dissolved feature, 404 when absent')
"
```

Expected: `endpoint OK: 200 with 1 dissolved feature, 404 when absent`.

- [ ] **Step 6: Run the full pytest suite**

Run: `uv run pytest -q`
Expected: PASS — 137 tests (136 baseline + 1 net new).

- [ ] **Step 7: Ruff clean across all touched files**

Run: `uv run ruff check pipeline/coverage.py tests/test_coverage.py tests/test_server.py && uv run ruff format --check pipeline/coverage.py tests/test_coverage.py tests/test_server.py`
Expected: `All checks passed!` and no reformatting needed.

- [ ] **Step 8: Run the full web suite + lint**

Run: `cd web && npm test && npx tsc -b && npm run lint`
Expected: 32 web tests passed; `tsc` exits 0; oxlint reports no errors.

- [ ] **Step 9: Confirm no new click handler on the veil**

Run: `grep -n "coverage-veil" web/src/components/Map.tsx`
Expected: matches for `addLayer` definitions (coverage-veil fill and coverage-veil-edge line), `mousemove` handler, `mouseleave` handler — NO `m.on("click", "coverage-veil"` line. Confirm `CLICK_LAYERS` is unchanged:

Run: `grep -n "CLICK_LAYERS" web/src/components/Map.tsx`
Expected: `const CLICK_LAYERS = ["reach-dots", "all-stations"];` — unchanged.

- [ ] **Step 10: Confirm `countries_europe_50m.geojson` is unchanged**

Run: `git diff HEAD -- pipeline/assets/countries_europe_50m.geojson`
Expected: empty (no diff). The 50m Europe asset is untouched.

---

## Self-Review

Checked the completed plan against `docs/superpowers/specs/2026-07-11-veil-rework-design.md`:

**Spec coverage:**
- §1 New world asset (one-off, committed, mapshaper from NE 10m, ISO_A2_EH only, simplified 40% visvalingam keep-shapes, 4 decimal coordinates, ≤ 5 MB, provenance in coverage.py docstring, existing 50m asset untouched) → Task 1 Steps 1, 5. ✓
- §2 Pipeline dissolved veil (shapely unary_union, single Feature, empty properties, COUNTRY_NAMES deleted, shapely added, coverage.json unchanged path/endpoint) → Task 1 Steps 2-8. ✓
- §3 Frontend (filter removed, VEIL_TOOLTIP constant, feathered coverage-veil-edge line layer with line-color #6b7280 / line-width ~2.5 / line-blur ~3 / line-opacity ~0.2, VEIL_LEGEND deleted, Legend entry removed) → Task 2. ✓
- §4 Testing (tooltip constant asserted, filter tests removed, precedence tests unchanged, pipeline: single-feature FeatureCollection, point-in-polygon for covered/non-covered/ocean) → Task 1 Step 3, Task 2 Step 1. ✓
- Out of scope (no OSM boundaries, no station→country changes) → nothing in the plan touches these. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step has complete code. ✓

**Type consistency:** `WORLD_ASSET` / `build_coverage` / `covered_from_feeds` names identical across Task 1 tests, implementation, and Task 3 verification. `VEIL_TOOLTIP` / `showVeilTooltip` identical between coverage.ts, coverage.test.ts, and Map.tsx. `CoverageFeature.properties` is `Record<string, never>` in types.ts, matching empty `{}` from pipeline. `CLICK_LAYERS` referenced but never mutated. ✓
