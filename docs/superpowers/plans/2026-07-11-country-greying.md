# Country Greying Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it visually clear which European countries are not yet in our system by drawing a translucent grey veil over non-covered countries (with a hover tooltip and a legend line), driven entirely by the pipeline so adding a feed auto-un-greys its country on the next run.

**Architecture:** The pipeline emits `data/out/coverage.json` (a GeoJSON FeatureCollection of 42 European countries, each flagged `covered: true|false` from `feeds.toml`). The server exposes it verbatim at `GET /api/coverage`. The web app fetches it once on load, draws one `fill` layer below every station/line layer filtered to `covered == false`, adds a hover tooltip, and a legend line. All pure logic (filter expression, tooltip copy, hover precedence) lives in a unit-tested `web/src/lib/coverage.ts`.

**Tech Stack:** Python 3.14 (uv, pydantic, FastAPI), pytest; React + TypeScript + MapLibre GL, vitest, oxlint.

## Global Constraints

- **Python uv-only.** Run everything through `uv run …`. Never invoke `python`/`pytest`/`ruff` directly.
- **Lint/format clean on touched files.** `uv run ruff check <files>` AND `uv run ruff format --check <files>` must both pass. Line length 100. Ruff lint selects `E, F, I, W`.
- **TDD.** Write the failing test first, watch it fail, implement minimally, watch it pass. Commit after every task with the exact commit command given.
- **Never run `ose fetch`.** Raw feed zips already exist in `data/raw/` (7 zips). A full `uv run ose build` (~4 min) plus `uv run ose compute` runs exactly ONCE, in Task 4, to produce the real `coverage.json`. Tasks 1–3 use fixtures only.
- **Current baselines:** 1656 stations / 6057 trips / 129 pytest tests / 29 web tests. `feeds.toml` countries = {DE, FR, AT, CH, NL, ES, PL}. These counts must be unchanged after Task 4 (except pytest/web test counts, which grow by the new tests).
- **The user does visual checks.** Acceptance is at data/API/unit-test level only (see spec §Acceptance). Do not claim visual verification.
- **Subagent models:** opus or sonnet only, never haiku.
- **Exact legend copy:** `Grey countries: not yet in our system` (character-for-character).
- **Exact tooltip copy:** `<Name> — not yet in our system` (the dash is an em dash `—`, U+2014, surrounded by single spaces).

---

## File Structure

**Create:**
- `pipeline/coverage.py` — ISO2→name table, `build_coverage(covered, asset_path)`, `covered_from_feeds(feeds_path)`.
- `tests/test_coverage.py` — pipeline coverage tests (fixtures only).
- `web/src/lib/coverage.ts` — pure veil helpers (filter expression, tooltip copy, hover precedence, legend constant).
- `web/src/lib/coverage.test.ts` — vitest for the above.

**Modify:**
- `pipeline/compute.py` — write `data/out/coverage.json` in `compute_all` (it already owns `data/out`).
- `server/app.py` — add `GET /api/coverage`.
- `tests/test_server.py` — endpoint 200 + 404 tests.
- `web/src/lib/types.ts` — `CoverageFeature` / `CoverageCollection` types.
- `web/src/lib/api.ts` — `getCoverage()`.
- `web/src/components/Map.tsx` — coverage source + veil `fill` layer (below all layers) + hover tooltip; NO click handler on the veil.
- `web/src/components/Legend.tsx` — the legend line.

---

## Task 1: Pipeline `data/out/coverage.json` emission

Implements spec §1. The covered set is `{cfg.country for cfg in feeds.toml}`. The bundled asset `pipeline/assets/countries_europe_50m.geojson` has 42 features whose ONLY property is `ISO_A2_EH` (verified: no name property exists), so this task supplies display names via a hardcoded ISO2→name table. `compute_all` (which already writes `stations.json`, `meta.json`, and the reach files to `data/out`) writes `coverage.json`; the stale-reach pruning only globs `reach_*.json`, so `coverage.json` survives untouched.

**Files:**
- Create: `pipeline/coverage.py`
- Create: `tests/test_coverage.py`
- Modify: `pipeline/compute.py`

**Interfaces:**
- Consumes: `pipeline.geo.ASSET` (Path to the bundled geojson); `pipeline.config.load_feeds(path) -> dict[str, FeedConfig]` (each `FeedConfig` has a `.country: str`).
- Produces:
  - `build_coverage(covered: set[str], asset_path: Path = ASSET) -> dict` — returns a GeoJSON `FeatureCollection`; each feature keeps its original `geometry`, and `properties = {"ISO_A2_EH": str, "name": str, "covered": bool}`. Always 42 features.
  - `covered_from_feeds(feeds_path: Path) -> set[str]` — the set of `country` fields declared in a feeds.toml.
  - `COUNTRY_NAMES: dict[str, str]` — ISO2 → English display name for all 42 asset codes.
  - `compute_all(graph_dir, out_dir, workers=None, feeds_path=Path("feeds.toml"))` now also writes `out_dir/coverage.json`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_coverage.py`:

```python
import json
from datetime import date

from pipeline.build import build
from pipeline.compute import compute_all
from pipeline.coverage import COUNTRY_NAMES, build_coverage, covered_from_feeds
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


def test_build_coverage_flags_only_covered_countries():
    fc = build_coverage({"DE", "FR"})
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 42
    covered = {
        f["properties"]["ISO_A2_EH"] for f in fc["features"] if f["properties"]["covered"]
    }
    assert covered == {"DE", "FR"}


def test_build_coverage_carries_name_and_geometry_on_every_feature():
    fc = build_coverage(set())
    for f in fc["features"]:
        assert f["properties"]["name"]
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
    de = next(f for f in fc["features"] if f["properties"]["ISO_A2_EH"] == "DE")
    assert de["properties"]["name"] == "Germany"
    assert de["properties"]["covered"] is False


def test_country_names_covers_every_asset_iso():
    fc = build_coverage(set())
    for f in fc["features"]:
        assert f["properties"]["ISO_A2_EH"] in COUNTRY_NAMES


def test_covered_from_feeds_reads_country_fields(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    assert covered_from_feeds(feeds_toml) == {"LA", "BO"}


def test_compute_writes_coverage_json_that_survives_pruning(tmp_path):
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
    assert len(cov["features"]) == 42
    # LA/BO are fixture pseudo-codes absent from the asset, so nothing is covered.
    assert not any(f["properties"]["covered"] for f in cov["features"])
    # coverage.json is not a reach_*.json file, so the stale-reach prune leaves it.
    assert (out / "coverage.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coverage.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.coverage'` (collection error).

- [ ] **Step 3: Create `pipeline/coverage.py`**

```python
"""`coverage.json` emission: turn the bundled Natural Earth country subset into a
GeoJSON FeatureCollection flagged with which countries are in our system.

The bundled asset (pipeline/assets/countries_europe_50m.geojson) carries only an
ISO_A2_EH property per feature (no display name), so display names come from the
COUNTRY_NAMES table below. "Covered" means a feed in feeds.toml declares that
country; see docs/superpowers/specs/2026-07-11-country-greying-design.md.
"""

import json
from pathlib import Path

from pipeline.config import load_feeds
from pipeline.geo import ASSET

# English display names for every ISO_A2_EH code present in the bundled asset
# (42 features). Verified against the asset's code set on 2026-07-11.
COUNTRY_NAMES: dict[str, str] = {
    "AD": "Andorra",
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BY": "Belarus",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SM": "San Marino",
    "TR": "Turkey",
    "UA": "Ukraine",
    "XK": "Kosovo",
}


def build_coverage(covered: set[str], asset_path: Path = ASSET) -> dict:
    """GeoJSON FeatureCollection: one feature per bundled country, geometry kept,
    properties reduced to {ISO_A2_EH, name, covered}. `covered` is True when the
    feature's ISO code is in `covered`."""
    fc = json.loads(asset_path.read_text(encoding="utf-8"))
    features = []
    for f in fc["features"]:
        iso = f["properties"]["ISO_A2_EH"]
        features.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "ISO_A2_EH": iso,
                    "name": COUNTRY_NAMES.get(iso, iso),
                    "covered": iso in covered,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def covered_from_feeds(feeds_path: Path) -> set[str]:
    """The set of `country` fields declared across all feeds in a feeds.toml."""
    return {cfg.country for cfg in load_feeds(feeds_path).values()}
```

- [ ] **Step 4: Wire `compute_all` to write `coverage.json`**

In `pipeline/compute.py`, add the import near the existing pipeline imports (after `from pipeline.models import ...`):

```python
from pipeline.coverage import build_coverage, covered_from_feeds
```

Change the `compute_all` signature line from:

```python
def compute_all(graph_dir: Path, out_dir: Path, workers: int | None = None) -> None:
```

to:

```python
def compute_all(
    graph_dir: Path,
    out_dir: Path,
    workers: int | None = None,
    feeds_path: Path = Path("feeds.toml"),
) -> None:
```

At the very END of `compute_all` (immediately after the block that writes `meta.json`), append:

```python
    covered = covered_from_feeds(feeds_path) if feeds_path.exists() else set()
    (out_dir / "coverage.json").write_text(
        json.dumps(build_coverage(covered), ensure_ascii=False)
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_coverage.py -q`
Expected: PASS — 5 passed.

- [ ] **Step 6: Run the full pipeline suite to confirm no regressions**

Run: `uv run pytest tests/test_build.py tests/test_coverage.py -q`
Expected: PASS (existing build tests + 5 new coverage tests all green).

- [ ] **Step 7: Lint and format the touched files**

Run: `uv run ruff check pipeline/coverage.py pipeline/compute.py tests/test_coverage.py && uv run ruff format --check pipeline/coverage.py pipeline/compute.py tests/test_coverage.py`
Expected: `All checks passed!` and no files listed as needing reformatting.
If `ruff format --check` reports a file, run `uv run ruff format <that file>` and re-run the check.

- [ ] **Step 8: Commit**

```bash
git add pipeline/coverage.py pipeline/compute.py tests/test_coverage.py
git commit -m "feat: emit data/out/coverage.json from compute (country greying)"
```

---

## Task 2: Server `GET /api/coverage`

Implements spec §2. Serves `data/out/coverage.json` verbatim, mirroring the existing `reach` endpoint's missing-file behavior: 404 when the pipeline has not produced the file. (Spec §2 says "GET /coverage"; every existing endpoint lives under `/api/*` and the web dev proxy only forwards `/api`, so this is implemented as `GET /api/coverage` — see the code-reality note at the end of this plan.)

**Files:**
- Modify: `server/app.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: `data_dir / "coverage.json"` as written by Task 1's `compute_all`.
- Produces: `GET /api/coverage` → 200 with the FeatureCollection JSON; 404 (`HTTPException`) when the file is absent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py` (the file already imports `TestClient`, `create_app`, and defines the module-scoped `client` fixture whose pipeline run now produces `coverage.json`):

```python
def test_coverage_endpoint(client):
    r = client.get("/api/coverage")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 42
    assert all("name" in f["properties"] for f in fc["features"])


def test_coverage_404_when_absent(tmp_path):
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/api/coverage").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py::test_coverage_endpoint tests/test_server.py::test_coverage_404_when_absent -v`
Expected: `test_coverage_endpoint` FAILS with a 404 (route not defined yet, FastAPI returns 404 for unknown paths) — assertion on `status_code == 200` fails; `test_coverage_404_when_absent` may pass incidentally (unknown route is also 404). Both must pass only after the route exists and returns the file/404 deliberately.

- [ ] **Step 3: Add the endpoint**

In `server/app.py`, inside `create_app`, add this route immediately after the existing `@app.get("/api/meta")` block (before `return app`):

```python
    @app.get("/api/coverage")
    def coverage() -> dict:
        path = data_dir / "coverage.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="No coverage data")
        return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS (all existing server tests + the 2 new coverage tests green).

- [ ] **Step 5: Lint and format the touched files**

Run: `uv run ruff check server/app.py tests/test_server.py && uv run ruff format --check server/app.py tests/test_server.py`
Expected: `All checks passed!` and no reformatting needed.

- [ ] **Step 6: Commit**

```bash
git add server/app.py tests/test_server.py
git commit -m "feat: serve GET /api/coverage from data/out/coverage.json"
```

---

## Task 3: Web veil layer, tooltip, legend

Implements spec §3. Adds one geojson source, one `fill` layer inserted BELOW every existing station/line layer (filter `covered == false`), a hover tooltip, and a legend line. All pure logic lives in `web/src/lib/coverage.ts` with unit tests. The veil gets NO click handler and the tooltip is suppressed whenever a station/dot feature is under the cursor, so the click-selection precedence in `web/src/lib/pickfeature.ts` is untouched.

**Files:**
- Create: `web/src/lib/coverage.ts`
- Create: `web/src/lib/coverage.test.ts`
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/components/Legend.tsx`

**Interfaces:**
- Consumes: `GET /api/coverage` (Task 2) → a FeatureCollection whose feature `properties` are `{ISO_A2_EH: string, name: string, covered: boolean}`.
- Produces (from `web/src/lib/coverage.ts`):
  - `VEIL_LEGEND: string` — the exact legend copy.
  - `veilFilter(): ["==", ["get", "covered"], false]` — MapLibre filter for the veil layer.
  - `coverageTooltip(name: string): string` — `"<name> — not yet in our system"`.
  - `showVeilTooltip(stationHitCount: number): boolean` — true only when no station/dot feature is under the cursor.

- [ ] **Step 1: Write the failing web tests**

Create `web/src/lib/coverage.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { VEIL_LEGEND, coverageTooltip, showVeilTooltip, veilFilter } from "./coverage";

describe("veilFilter", () => {
  it("matches only non-covered countries", () => {
    expect(veilFilter()).toEqual(["==", ["get", "covered"], false]);
  });
});

describe("coverageTooltip", () => {
  it("formats the not-yet-in-system tooltip", () => {
    expect(coverageTooltip("Italy")).toBe("Italy — not yet in our system");
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

describe("VEIL_LEGEND", () => {
  it("is the exact approved copy", () => {
    expect(VEIL_LEGEND).toBe("Grey countries: not yet in our system");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/coverage.test.ts`
Expected: FAIL — cannot resolve `./coverage` (module does not exist).

- [ ] **Step 3: Create `web/src/lib/coverage.ts`**

```ts
// Pure helpers for the country-coverage veil.
// Spec: docs/superpowers/specs/2026-07-11-country-greying-design.md §3.
// Kept out of Map.tsx so the filter expression, tooltip copy, and hover-precedence
// rule are unit-testable without a live map.

// Exact legend copy (spec §3). Defined here so the wording is asserted in one place.
export const VEIL_LEGEND = "Grey countries: not yet in our system";

// MapLibre fill-layer filter: show the veil only over non-covered countries.
export type VeilFilter = ["==", ["get", "covered"], boolean];
export function veilFilter(): VeilFilter {
  return ["==", ["get", "covered"], false];
}

// Tooltip text for a hovered grey country (spec §3, exact copy; em dash U+2014).
export function coverageTooltip(name: string): string {
  return `${name} — not yet in our system`;
}

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
Expected: PASS — 5 passed.

- [ ] **Step 5: Add the coverage types**

Append to `web/src/lib/types.ts`:

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

- [ ] **Step 6: Add `getCoverage` to the api client**

In `web/src/lib/api.ts`, change the import line from:

```ts
import type { Meta, ReachFile, Station } from "./types";
```

to:

```ts
import type { CoverageCollection, Meta, ReachFile, Station } from "./types";
```

and add this entry to the `api` object (after `getMeta`):

```ts
  getCoverage: () => get<CoverageCollection>("/api/coverage"),
```

- [ ] **Step 7: Add the veil source, layer, fetch, and tooltip to `Map.tsx`**

In `web/src/components/Map.tsx`:

(a) Add these imports after the existing `import { pickFeature } from "../lib/pickfeature";` line:

```ts
import { coverageTooltip, showVeilTooltip, veilFilter } from "../lib/coverage";
import { api } from "../lib/api";
```

(b) Inside the `m.on("load", () => { … })` handler, add the coverage source alongside the other `addSource` calls (right after `m.addSource("reach-dots", …)`):

```ts
      m.addSource("coverage", { type: "geojson", data: EMPTY as never });
```

(c) Still inside the load handler, AFTER the `m.addLayer({ id: "all-stations", … })` block has run (so the `beforeId` target exists), add the veil `fill` layer inserted BELOW `all-stations`. Place this immediately after the closing `});` of the `all-stations` layer definition:

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

(d) Fetch the coverage geojson once on load. Add this right after the `map.current = m;` line (near the end of the load handler):

```ts
      api
        .getCoverage()
        .then((fc) =>
          (m.getSource("coverage") as maplibregl.GeoJSONSource).setData(fc as never),
        )
        .catch(() => {
          // Veil is decorative; a missing coverage.json (404) just means no veil.
        });
```

(e) Add the hover tooltip. Add this after the existing `for (const layer of ["all-stations", "reach-dots"]) { … }` cursor block (still inside the load handler):

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

Do NOT add `"coverage-veil"` to `CLICK_LAYERS` and do NOT register any `m.on("click", "coverage-veil", …)`. The click handler must keep querying only `CLICK_LAYERS = ["reach-dots", "all-stations"]`, so the veil is never clickable and selection precedence is unchanged.

- [ ] **Step 8: Add the legend line to `Legend.tsx`**

Replace the entire contents of `web/src/components/Legend.tsx` with:

```tsx
import { BUCKET_COLORS, BUCKET_LABELS } from "../lib/colors";
import { VEIL_LEGEND } from "../lib/coverage";

export default function Legend() {
  return (
    <div className="legend">
      {BUCKET_COLORS.map((c, i) => (
        <span key={c}>
          <i style={{ background: c }} /> {BUCKET_LABELS[i]}
        </span>
      ))}
      <span>
        <i style={{ background: "#6b7280", opacity: 0.25 }} /> {VEIL_LEGEND}
      </span>
    </div>
  );
}
```

- [ ] **Step 9: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 29 existing + 5 new coverage tests = 34 passed.

- [ ] **Step 10: Type-check and lint the web app**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors on the changed files.

- [ ] **Step 11: Commit**

```bash
git add web/src/lib/coverage.ts web/src/lib/coverage.test.ts web/src/lib/types.ts web/src/lib/api.ts web/src/components/Map.tsx web/src/components/Legend.tsx
git commit -m "feat: grey non-covered countries with veil layer, tooltip, legend"
```

---

## Task 4: Real pipeline run + acceptance checks

Implements the spec §Acceptance checks against real data. This is the ONE place the full pipeline runs. Never run `ose fetch`; the raw zips already exist. Everything else is data/API/unit verification — the user does the visual checks.

**Files:** none created or modified. This task runs the pipeline and verification commands only.

- [ ] **Step 1: Build the real graph (~4 min, foreground)**

Run: `uv run ose build`
Expected: ends with `graph: 1656 stations, 6057 trips -> data/graph`. If station/trip counts differ from 1656/6057, STOP — the baseline changed and the plan's assumptions must be re-checked before continuing.

- [ ] **Step 2: Compute reachability + emit coverage.json**

Run: `uv run ose compute`
Expected: prints many `reach_<id>.json: N destinations` lines, possibly some `pruned stale …` lines, then exits 0. It writes `data/out/stations.json`, `data/out/meta.json`, the reach files, and `data/out/coverage.json`. (This is CPU-heavy and may run several minutes; it may be run in the background — wait for it to finish before Step 3.)

- [ ] **Step 3: Verify coverage.json content (spec Acceptance #1)**

Run:

```bash
uv run python -c "
import json
cov = json.load(open('data/out/coverage.json'))
feats = cov['features']
assert cov['type'] == 'FeatureCollection'
assert len(feats) == 42, len(feats)
covered = {f['properties']['ISO_A2_EH'] for f in feats if f['properties']['covered']}
assert covered == {'DE', 'FR', 'AT', 'CH', 'NL', 'ES', 'PL'}, covered
assert all(f['properties']['name'] for f in feats)
print('coverage OK:', sorted(covered))
"
```

Expected: `coverage OK: ['AT', 'CH', 'DE', 'ES', 'FR', 'NL', 'PL']`. If the assertion trips, STOP and investigate (mismatch between feeds.toml countries and the emitted `covered` flags).

- [ ] **Step 4: Verify station/trip counts unchanged (baseline 1656/6057)**

Run:

```bash
uv run python -c "
import json
print('stations', len(json.load(open('data/out/stations.json'))['stations']))
print('trips', len(json.load(open('data/graph/trips.json'))['trips']))
"
```

Expected: `stations 1656` and `trips 6057`. Any deviation means the pipeline change had an unintended side effect — STOP and investigate.

- [ ] **Step 5: Verify the endpoint 200/404 (spec Acceptance #2)**

Run:

```bash
uv run python -c "
from pathlib import Path
from fastapi.testclient import TestClient
from server.app import create_app
c = TestClient(create_app(Path('data/out')))
r = c.get('/api/coverage')
assert r.status_code == 200, r.status_code
assert r.json()['type'] == 'FeatureCollection'
assert len(r.json()['features']) == 42
empty = TestClient(create_app(Path('/nonexistent')))
assert empty.get('/api/coverage').status_code == 404
print('endpoint OK: 200 with 42 features, 404 when absent')
"
```

Expected: `endpoint OK: 200 with 42 features, 404 when absent`.

- [ ] **Step 6: Run the full pytest suite (spec Acceptance #3)**

Run: `uv run pytest -q`
Expected: PASS — 129 baseline + 7 new (5 coverage + 2 server) = 136 passed.

- [ ] **Step 7: Ruff clean across all touched files (spec Acceptance #3)**

Run: `uv run ruff check pipeline/coverage.py pipeline/compute.py server/app.py tests/test_coverage.py tests/test_server.py && uv run ruff format --check pipeline/coverage.py pipeline/compute.py server/app.py tests/test_coverage.py tests/test_server.py`
Expected: `All checks passed!` and no reformatting needed.

- [ ] **Step 8: Run the full web suite + lint (spec Acceptance #3)**

Run: `cd web && npm test && npx tsc -b && npm run lint`
Expected: 34 web tests passed; `tsc` exits 0; oxlint reports no errors.

- [ ] **Step 9: Confirm no new click handler on the veil (spec Acceptance #4)**

Run: `grep -n "coverage-veil" web/src/components/Map.tsx`
Expected: the only matches are the `addLayer` definition, the `mousemove` handler, and the `mouseleave` handler — NO `m.on("click", "coverage-veil"` line, and `CLICK_LAYERS` still equals `["reach-dots", "all-stations"]`. Confirm by also running: `grep -n "CLICK_LAYERS" web/src/components/Map.tsx` (the constant must be unchanged).

- [ ] **Step 10: Commit any regenerated data artifacts (if tracked)**

Run: `git status --short`
- If `data/out/coverage.json` (or other `data/out` artifacts) show as changed AND `data/out` is tracked in this repo, commit them:

```bash
git add data/out/coverage.json
git commit -m "chore: regenerate coverage.json from real pipeline run"
```

- If `git status` shows those paths are ignored/untracked (data is git-ignored), skip the commit — the run only needed to produce and verify the artifact. Do NOT force-add ignored files.

---

## Self-Review

Checked the completed plan against `docs/superpowers/specs/2026-07-11-country-greying-design.md`:

**Spec coverage:**
- §1 Pipeline `coverage.json` (source polygons, covered set from feeds.toml, geometry+ISO+name+covered, compute stage owns it, survives pruning, TDD with fixtures) → Task 1. ✓
- §2 Server `GET /coverage` (serve verbatim, 404 when absent) → Task 2 (as `/api/coverage`, see correction). ✓
- §3 Web (one fetch on load, one source, one fill layer below all layers filtered `covered==false`, grey fill-opacity 0.25, hover tooltip exact copy, veil no click handler + suppressed when station/dot under cursor, legend line exact copy, pure logic in coverage.ts with tests) → Task 3. ✓
- §Acceptance #1 (coverage.json content) → Task 4 Step 3. #2 (200/404) → Task 4 Step 5 + Task 2. #3 (unit/pytest/web/ruff green) → Task 4 Steps 6-8. #4 (no new click handler) → Task 4 Step 9. ✓
- §Out of scope (no partial states, no styling polish, no geo.py changes, no new feeds) → nothing in the plan touches these. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step has complete code. ✓

**Type consistency:** `build_coverage`/`covered_from_feeds`/`COUNTRY_NAMES` names identical across Tasks 1, 2, 4. Feature `properties` keys `{ISO_A2_EH, name, covered}` identical in pipeline (Task 1), types (Task 3), and tests. `veilFilter`/`coverageTooltip`/`showVeilTooltip`/`VEIL_LEGEND` identical between coverage.ts, its test, Map.tsx, and Legend.tsx. `CLICK_LAYERS` referenced but never mutated. ✓

## Code-reality corrections to the spec's assumptions

1. **The asset has NO name property.** `pipeline/assets/countries_europe_50m.geojson` (42 features) exposes only `ISO_A2_EH`; there is no display-name key to "carry through" as spec §1 assumed. The plan supplies names via a hardcoded `COUNTRY_NAMES` ISO2→name table in `pipeline/coverage.py` (all 42 codes covered, asserted by a test).
2. **Endpoint path is `/api/coverage`, not `/coverage`.** Spec §2 wrote "GET /coverage", but every existing endpoint is under `/api/*` and the web dev proxy (`web/vite.config.ts`) only forwards `/api`. Implemented as `GET /api/coverage` for consistency and so the web fetch is proxied.
3. **Missing-file behavior mirrors the `reach` endpoint (404), not `stations.json`.** Spec §2 referenced the "stations.json FileResponse/caching pattern", but `server/app.py` has no FileResponse and `stations.json` returns 503 via `_read`. The `reach` endpoint is the real precedent for the spec-required 404-on-absent, so `/api/coverage` follows it (check `path.exists()`, else `HTTPException(404)`).
4. **The legend line lives in `Legend.tsx`, not the App status-bar.** Spec §3 said "Legend line (status bar)", but the App status-bar renders only when an origin is selected (`{origin && …}`), while the veil is always visible. The always-rendered `Legend` component is the correct home; the exact copy is tied to the tested `VEIL_LEGEND` constant.
5. **`compute` owns `data/out`, confirmed.** `compute_all` already writes `stations.json`, `meta.json`, and the reach files; `coverage.json` is added there. The stale-reach prune globs only `reach_*.json`, so `coverage.json` survives untouched (asserted by a fixture test).
