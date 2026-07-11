# Dots & Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the 1651 grey station dots visual hierarchy (size ∝ connectivity), highlight capital cities with star icons, and cluster tightly-packed dots into clickable bubbles with pick-list popups.

**Architecture:** Three layers of work: (1) the Python pipeline learns `n_dest` and `is_capital` on every `Station`, driven by reach file counts and a new hand-curated `capitals.toml`; (2) new frontend pure helpers in `web/src/lib/dots.ts` build MapLibre expressions and sorting logic, with `pickfeature.ts` gaining capital-star precedence; (3) `Map.tsx` wires sized dots, a `capital-stars` symbol layer with a canvas-drawn star icon, MapLibre-native clustering on `all-stations`, and a cluster-click popup — with click ordering: cluster > pickFeature > empty.

**Tech Stack:** Python (Pydantic, tomllib, pytest), TypeScript/React (MapLibre GL JS, vitest, oxlint). uv-only Python, npm-only web.

## Global Constraints

- **Python:** `uv run` only — never bare `python` or `pip`. Ruff must stay clean (`uv run ruff check`).
- **Web:** All npm/vitest/tsc commands run from `web/`.
- **Never use `ose fetch`** — data comes from existing `data/out/` or fixture builds.
- **TDD.** Write the failing test first, watch it fail, implement minimally, watch it pass.
- **Current baselines:** 136 pytest tests, 38 web tests (8 test files). Deltas stated per task.
- **The user does visual checks.** Do not claim visual verification or take screenshots.
- **Subagent models:** opus or sonnet only, never haiku.
- **Verification commands (Python):**
  - `uv run pytest` — expected count noted per task
  - `uv run ruff check` — must report no errors
- **Verification commands (Web, run from `web/`):**
  - `npm test` (vitest) — expected count noted per task
  - `npx tsc -b` — must exit 0 with no output
  - `npm run lint` (oxlint) — must report no errors

---

## File Structure

**Create:**
- `capitals.toml` — curated `[capitals]` table: ISO country code → exact canonical station name.
- `pipeline/capitals.py` — loads `capitals.toml`, resolves against station list, returns set of capital station ids + warnings.
- `web/src/lib/dots.ts` — pure helpers: `dotRadiusExpression()`, `clusterRadiusExpression()`, `sortForClusterList()`, `drawStarIcon()`.
- `web/src/lib/dots.test.ts` — unit tests for all `dots.ts` exports.

**Modify:**
- `pipeline/models.py:4-10` — add `n_dest: int = 0` and `is_capital: bool = False` to `Station`.
- `pipeline/compute.py:111-126` — set `n_dest` on each station; load capitals and set `is_capital`.
- `tests/test_compute.py` — add tests for `n_dest` and `is_capital`.
- `tests/test_server.py:33-36` — assert `n_dest`/`is_capital` pass through.
- `web/src/lib/types.ts:1-3` — add `n_dest: number` and `is_capital: boolean` to `Station`.
- `web/src/lib/pickfeature.ts:15-21` — add `capital-stars` layer with precedence after `reach-dots`, before `all-stations`.
- `web/src/lib/pickfeature.test.ts` — add capital-stars precedence tests.
- `web/src/components/Map.tsx` — sized dots, capitals source/layer, clustering, cluster-click popup, click-handler ordering.

---

## Task 1: Pipeline — `n_dest`, `capitals.toml`, `is_capital`, warnings, tests

Adds `n_dest` and `is_capital` fields to the `Station` model, creates `capitals.toml`, writes a `capitals.py` loader, wires both into `compute_all`, and tests everything. Includes a cheap patch script to back-fill `n_dest`/`is_capital` into the live `data/out/stations.json` without a full recompute.

**Files:**
- Modify: `pipeline/models.py:4-10`
- Create: `capitals.toml`
- Create: `pipeline/capitals.py`
- Modify: `pipeline/compute.py:78-126`
- Modify: `tests/test_compute.py`
- Modify: `tests/test_server.py:33-36`

**Interfaces:**
- Consumes: `pipeline.models.Station`, `pipeline.config.load_feeds` (TOML loading pattern), `station_aliases.toml` (curation pattern).
- Produces:
  - `Station.n_dest: int` (default 0) — number of destinations reachable from this station.
  - `Station.is_capital: bool` (default False) — whether this station is a capital in `capitals.toml`.
  - `load_capitals(path: Path, stations: list[Station]) -> tuple[set[str], list[str]]` — returns (capital station ids, warning messages for unmatched entries).

**Pytest delta:** 136 → 140 (+4 new tests).

- [ ] **Step 1: Add `n_dest` and `is_capital` to the Station model**

In `pipeline/models.py`, add two fields to `Station` after `has_reach`:

```python
class Station(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    country: str
    has_reach: bool = False
    n_dest: int = 0
    is_capital: bool = False
```

- [ ] **Step 2: Create `capitals.toml`**

Create `capitals.toml` in the repo root (next to `station_aliases.toml`):

```toml
# Capital cities: ISO 2-letter country code → exact canonical station name.
# Matched by exact name AND country during `ose compute`; an entry that matches
# no station logs a warning and is skipped (never fails the build).
# Edit taste here — the pipeline just flags `is_capital: true`.
[capitals]
DE = "Berlin Hbf"
FR = "Paris Gare du Nord"
AT = "Wien Hbf"
NL = "Amsterdam Centraal"
ES = "Madrid-Puerta de Atocha-Almudena Grandes"
PL = "Warszawa Centralna"
CH = "Bern"
BE = "Bruxelles Midi"
CZ = "Praha hl.n."
```

- [ ] **Step 3: Create `pipeline/capitals.py`**

Create `pipeline/capitals.py`:

```python
"""Load capitals.toml and resolve against a station list."""

import logging
import tomllib
from pathlib import Path

from pipeline.models import Station

log = logging.getLogger(__name__)


def load_capitals(
    path: Path, stations: list[Station]
) -> tuple[set[str], list[str]]:
    """Return (set of capital station ids, list of warning messages).

    Each ``[capitals]`` entry is matched by exact name AND country.
    Unmatched entries produce a warning but never fail the build.
    """
    if not path.exists():
        return set(), []

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table = raw.get("capitals", {})

    by_country_name: dict[tuple[str, str], str] = {}
    for s in stations:
        by_country_name[(s.country, s.name)] = s.id

    capital_ids: set[str] = set()
    warnings: list[str] = []
    for country, name in table.items():
        key = (country.upper(), name)
        sid = by_country_name.get(key)
        if sid:
            capital_ids.add(sid)
        else:
            msg = f"capitals.toml: no station matches {country}={name!r}"
            log.warning(msg)
            warnings.append(msg)

    return capital_ids, warnings
```

- [ ] **Step 4: Wire `n_dest` and `is_capital` into `compute_all`**

In `pipeline/compute.py`, make two changes:

(a) Add the import. After the existing imports at the top of the file, add:

```python
from pipeline.capitals import load_capitals
```

(b) Replace the station-writing block (lines 111–126). Replace from `written: set[str] = set()` through the `stations.json` write:

```python
    capital_ids, cap_warnings = load_capitals(
        Path("capitals.toml"), stations
    )
    for w in cap_warnings:
        print(w)

    written: set[str] = set()
    for station in stations:
        n = results[station.id]
        station.n_dest = n
        if n:
            station.has_reach = True
            written.add(f"reach_{station.id}.json")
            print(f"reach_{station.id}.json: {n} destinations")
        if station.id in capital_ids:
            station.is_capital = True

    for path in out_dir.glob("reach_*.json"):
        if path.name not in written:
            path.unlink()
            print(f"pruned stale {path.name}")

    (out_dir / "stations.json").write_text(
        json.dumps({"stations": [s.model_dump() for s in stations]}, ensure_ascii=False)
    )
```

- [ ] **Step 5: Write the failing tests**

In `tests/test_compute.py`, add the following. First add the import at the top:

```python
from pipeline.capitals import load_capitals
```

Then add these four test functions at the end of the file:

```python
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


def test_compute_all_sets_is_capital(tmp_path):
    """is_capital is set for stations matching capitals.toml entries."""
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
```

- [ ] **Step 6: Run tests to verify the new ones pass**

Run: `uv run pytest tests/test_compute.py -v -k "n_dest or is_capital or load_capitals"`
Expected: PASS — 4 new tests pass.

- [ ] **Step 7: Run the full pytest suite**

Run: `uv run pytest`
Expected: PASS — 140 tests (136 baseline + 4 new). All existing tests still pass because `n_dest=0` and `is_capital=False` defaults are backward-compatible.

- [ ] **Step 8: Verify the server passes through `n_dest` and `is_capital`**

In `tests/test_server.py`, update `test_stations_endpoint` to also check the new fields. Replace the function:

```python
def test_stations_endpoint(client):
    stations = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in stations} == {"1111111", "2222222", "3333333", "4444444"}
    alpha = next(s for s in stations if s["id"] == "1111111")
    assert "n_dest" in alpha
    assert "is_capital" in alpha
```

- [ ] **Step 9: Run pytest again to confirm server test passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS — server uses `model_dump()` which includes the new fields automatically.

- [ ] **Step 10: Ruff check**

Run: `uv run ruff check`
Expected: no errors.

- [ ] **Step 11: Cheap patch script — back-fill `n_dest`/`is_capital` into live `data/out/stations.json`**

Run the following one-liner from the repo root to patch the live data without a full recompute. This reads existing `reach_*.json` files to count destinations per origin and resolves `capitals.toml`:

```bash
uv run python -c "
import json, tomllib
from pathlib import Path

out = Path('data/out')
stations = json.loads((out / 'stations.json').read_text())

# Count destinations per origin from existing reach files
n_dest = {}
for p in out.glob('reach_*.json'):
    r = json.loads(p.read_text())
    n_dest[r['origin']] = len(r['destinations'])

# Load capitals
caps_path = Path('capitals.toml')
cap_ids = set()
if caps_path.exists():
    raw = tomllib.loads(caps_path.read_text())
    by_cn = {(s['country'], s['name']): s['id'] for s in stations['stations']}
    for country, name in raw.get('capitals', {}).items():
        sid = by_cn.get((country.upper(), name))
        if sid:
            cap_ids.add(sid)
        else:
            print(f'WARNING: no match for {country}={name!r}')

# Patch
for s in stations['stations']:
    s['n_dest'] = n_dest.get(s['id'], 0)
    s['is_capital'] = s['id'] in cap_ids

(out / 'stations.json').write_text(json.dumps(stations, ensure_ascii=False))
print(f'Patched {len(stations[\"stations\"])} stations: '
      f'{sum(1 for s in stations[\"stations\"] if s[\"n_dest\"] > 0)} with reach, '
      f'{len(cap_ids)} capitals')
"
```

Expected output: `Patched 1656 stations: 1651 with reach, 9 capitals`

- [ ] **Step 12: Commit**

```bash
git add pipeline/models.py pipeline/capitals.py pipeline/compute.py capitals.toml tests/test_compute.py tests/test_server.py
git commit -m "feat: add n_dest and is_capital to Station (pipeline + capitals.toml)"
```

---

## Task 2: Web lib — `dots.ts` helpers, `pickfeature` capital-stars precedence, `types.ts`, tests (TDD)

Creates `web/src/lib/dots.ts` with pure helpers for dot radius expressions, cluster radius, cluster-list sorting, and canvas star drawing. Updates `pickfeature.ts` for capital-stars layer precedence. Updates `types.ts` with new Station fields. All test-first.

**Files:**
- Modify: `web/src/lib/types.ts:1-3`
- Create: `web/src/lib/dots.ts`
- Create: `web/src/lib/dots.test.ts`
- Modify: `web/src/lib/pickfeature.ts:1-21`
- Modify: `web/src/lib/pickfeature.test.ts`

**Interfaces:**
- Consumes: `Station` type from `web/src/lib/types.ts` (needs `n_dest`, `is_capital`).
- Produces:
  - `dotRadiusExpression() -> ExpressionSpecification` — sqrt-scaled `circle-radius` from 2.5 (n_dest=0) to 8 (n_dest≥400).
  - `clusterRadiusExpression() -> ExpressionSpecification` — `circle-radius` scaled by `point_count`.
  - `sortForClusterList(stations: { name: string; n_dest: number; id: string }[]) -> { name: string; n_dest: number; id: string }[]` — descending `n_dest`, then ascending `name`.
  - `drawStarIcon(size: number) -> HTMLCanvasElement` — 5-point star on a canvas, grey fill, white outline.
  - `pickFeature` updated: precedence is `reach-dots` > `capital-stars` > `all-stations`.

**Vitest delta:** 38 → 51 (+13 new tests: 8 in dots.test.ts, 5 in pickfeature.test.ts).

- [ ] **Step 1: Update `types.ts` — add `n_dest` and `is_capital` to `Station`**

In `web/src/lib/types.ts`, replace the `Station` interface:

```ts
export interface Station {
  id: string; name: string; lat: number; lon: number; country: string; has_reach: boolean;
  n_dest: number; is_capital: boolean;
}
```

- [ ] **Step 2: Write the failing `dots.test.ts`**

Create `web/src/lib/dots.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { dotRadiusExpression, clusterRadiusExpression, sortForClusterList, drawStarIcon } from "./dots";

describe("dotRadiusExpression", () => {
  it("returns a MapLibre expression array", () => {
    const expr = dotRadiusExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("interpolate");
  });

  it("maps n_dest 0 to radius 2.5", () => {
    const expr = dotRadiusExpression();
    // Expression structure: ["interpolate", ["linear"], input, 0, 2.5, sqrt(400), 8]
    const stops = expr.slice(3); // after interpolation type + input
    expect(stops[0]).toBe(0);
    expect(stops[1]).toBe(2.5);
  });

  it("maps n_dest >= 400 to radius 8", () => {
    const expr = dotRadiusExpression();
    const stops = expr.slice(3);
    expect(stops[stops.length - 1]).toBe(8);
  });
});

describe("clusterRadiusExpression", () => {
  it("returns a step expression", () => {
    const expr = clusterRadiusExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("step");
  });
});

describe("sortForClusterList", () => {
  it("sorts by n_dest descending", () => {
    const input = [
      { name: "A", n_dest: 10, id: "1" },
      { name: "B", n_dest: 50, id: "2" },
      { name: "C", n_dest: 30, id: "3" },
    ];
    const sorted = sortForClusterList(input);
    expect(sorted.map((s) => s.id)).toEqual(["2", "3", "1"]);
  });

  it("breaks n_dest ties by name ascending", () => {
    const input = [
      { name: "Zürich", n_dest: 100, id: "1" },
      { name: "Bern", n_dest: 100, id: "2" },
    ];
    const sorted = sortForClusterList(input);
    expect(sorted.map((s) => s.id)).toEqual(["2", "1"]);
  });

  it("returns a new array without mutating the input", () => {
    const input = [
      { name: "A", n_dest: 10, id: "1" },
      { name: "B", n_dest: 20, id: "2" },
    ];
    const original = [...input];
    sortForClusterList(input);
    expect(input).toEqual(original);
  });
});

describe("drawStarIcon", () => {
  it("returns an HTMLCanvasElement of the requested size", () => {
    const canvas = drawStarIcon(30);
    expect(canvas).toBeInstanceOf(HTMLCanvasElement);
    expect(canvas.width).toBe(30);
    expect(canvas.height).toBe(30);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/dots.test.ts`
Expected: FAIL — `Cannot find module './dots'`.

- [ ] **Step 4: Write the `dots.ts` implementation**

Create `web/src/lib/dots.ts`:

```ts
// Pure helpers for dot sizing, cluster rendering, and star icons.
// Spec: docs/superpowers/specs/2026-07-11-dots-clustering-design.md §2–4.

import type { ExpressionSpecification } from "maplibre-gl";

/**
 * Data-driven circle-radius for the grey all-stations layer.
 * sqrt scale from 2.5px (n_dest=0) to 8px, clamped at n_dest=400.
 * sqrt(0)=0, sqrt(400)=20 — we interpolate linearly in sqrt-space.
 */
export function dotRadiusExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["max", ["get", "n_dest"], 0]],
    0, 2.5,
    Math.sqrt(400), 8,
  ] as ExpressionSpecification;
}

/**
 * circle-radius for station-clusters bubble, scaled by point_count.
 */
export function clusterRadiusExpression(): ExpressionSpecification {
  return [
    "step",
    ["get", "point_count"],
    15,   // default (2+)
    5, 18,
    10, 22,
    25, 26,
  ] as ExpressionSpecification;
}

/**
 * Sort stations for the cluster pick-list popup:
 * descending n_dest, then ascending name for ties.
 * Returns a new sorted array (does not mutate).
 */
export function sortForClusterList<T extends { name: string; n_dest: number }>(
  stations: T[],
): T[] {
  return [...stations].sort((a, b) =>
    b.n_dest - a.n_dest || a.name.localeCompare(b.name),
  );
}

/**
 * Draw a 5-point star on a canvas for use with map.addImage().
 * Grey fill (#9ca3af) matching the dot palette, subtle white outline.
 */
export function drawStarIcon(size: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 1;
  const innerR = outerR * 0.4;
  const points = 5;

  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (Math.PI / points) * i - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = "#9ca3af";
  ctx.fill();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  return canvas;
}
```

- [ ] **Step 5: Run dots tests to verify they pass**

Run: `cd web && npx vitest run src/lib/dots.test.ts`
Expected: PASS — 8 tests passed.

- [ ] **Step 6: Write the failing pickfeature tests for capital-stars precedence**

Append to `web/src/lib/pickfeature.test.ts`, inside the existing `describe("pickFeature", ...)` block, add these tests after the existing `it("ignores unrelated layers", ...)`:

```ts
  it("picks a capital-star as origin when only capital-stars is hit", () => {
    expect(pickFeature([{ layer: "capital-stars", id: "CAP1" }]))
      .toEqual({ type: "origin", id: "CAP1" });
  });

  it("prefers reach-dots over capital-stars", () => {
    expect(pickFeature([
      { layer: "capital-stars", id: "CAP1" },
      { layer: "reach-dots", id: "DEST1" },
    ])).toEqual({ type: "dest", id: "DEST1" });
  });

  it("prefers capital-stars over all-stations", () => {
    expect(pickFeature([
      { layer: "all-stations", id: "ALL1" },
      { layer: "capital-stars", id: "CAP1" },
    ])).toEqual({ type: "origin", id: "CAP1" });
  });

  it("prefers reach-dots over capital-stars over all-stations when all three hit", () => {
    expect(pickFeature([
      { layer: "all-stations", id: "ALL1" },
      { layer: "capital-stars", id: "CAP1" },
      { layer: "reach-dots", id: "DEST1" },
    ])).toEqual({ type: "dest", id: "DEST1" });
  });

  it("handles capital-stars among unrelated layers", () => {
    expect(pickFeature([
      { layer: "background", id: "x" },
      { layer: "capital-stars", id: "CAP1" },
    ])).toEqual({ type: "origin", id: "CAP1" });
  });
```

- [ ] **Step 7: Run pickfeature tests to verify the new ones fail**

Run: `cd web && npx vitest run src/lib/pickfeature.test.ts`
Expected: FAIL — `capital-stars` layer not handled in `pickFeature`, so the new tests fail.

- [ ] **Step 8: Update `pickfeature.ts` — add capital-stars precedence**

Replace the `pickFeature` function in `web/src/lib/pickfeature.ts`:

```ts
/**
 * Decide which selection a map click represents when multiple layers can be
 * hit at the same point. Precedence: reach-dots (dest) > capital-stars (origin)
 * > all-stations (origin).
 */
export function pickFeature(hits: FeatureHit[]): FeaturePick | null {
  const dest = hits.find((h) => h.layer === "reach-dots");
  if (dest) return { type: "dest", id: dest.id };
  const capital = hits.find((h) => h.layer === "capital-stars");
  if (capital) return { type: "origin", id: capital.id };
  const origin = hits.find((h) => h.layer === "all-stations");
  if (origin) return { type: "origin", id: origin.id };
  return null;
}
```

- [ ] **Step 9: Run pickfeature tests to verify all pass**

Run: `cd web && npx vitest run src/lib/pickfeature.test.ts`
Expected: PASS — 11 tests (6 existing + 5 new).

- [ ] **Step 10: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 51 tests (38 baseline + 8 dots + 5 pickfeature).

- [ ] **Step 11: Type-check and lint**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors.

- [ ] **Step 12: Commit**

```bash
git add web/src/lib/dots.ts web/src/lib/dots.test.ts web/src/lib/pickfeature.ts web/src/lib/pickfeature.test.ts web/src/lib/types.ts
git commit -m "feat: dots.ts helpers + pickfeature capital-stars precedence + types"
```

---

## Task 3: Map.tsx wiring — sized dots, capital stars, clustering, pick-list popup, click ordering

Wires everything from Tasks 1–2 into `Map.tsx`: data-driven dot sizes on `all-stations`, a `capitals` GeoJSON source + `capital-stars` symbol layer with canvas star `addImage`, MapLibre native clustering on `all-stations` with cluster bubble + count layers, a cluster-click popup with sorted pick-list, and click-handler ordering: cluster > pickFeature > empty.

**Files:**
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/index.css`

**Interfaces:**
- Consumes:
  - `dotRadiusExpression()` from `web/src/lib/dots.ts` (Task 2).
  - `clusterRadiusExpression()` from `web/src/lib/dots.ts` (Task 2).
  - `sortForClusterList(stations)` from `web/src/lib/dots.ts` (Task 2).
  - `drawStarIcon(size: number)` from `web/src/lib/dots.ts` (Task 2).
  - `pickFeature(hits)` from `web/src/lib/pickfeature.ts` (Task 2, updated).
  - `Station.n_dest`, `Station.is_capital` from `web/src/lib/types.ts` (Task 2).
- Produces: Fully wired map with sized dots, star capitals, clustering, and click handler.

**Vitest delta:** 51 → 51 (no new unit tests — Map.tsx is integration; user does visual checks).

- [ ] **Step 1: Add imports to `Map.tsx`**

In `web/src/components/Map.tsx`, replace the import block (lines 1–9) with:

```ts
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { destinationsGeoJSON, linesGeoJSON, type MaxTrains } from "../lib/geojson";
import { BUCKET_COLORS } from "../lib/colors";
import { baseLineOpacity, selectedLineFilter } from "../lib/highlight";
import { pickFeature } from "../lib/pickfeature";
import { veilTooltip, showVeilTooltip } from "../lib/coverage";
import { api } from "../lib/api";
import { dotRadiusExpression, clusterRadiusExpression, sortForClusterList, drawStarIcon } from "../lib/dots";
import type { ReachFile, Station } from "../lib/types";
```

- [ ] **Step 2: Update `CLICK_LAYERS` to include `capital-stars`**

Replace the `CLICK_LAYERS` line:

```ts
const CLICK_LAYERS = ["reach-dots", "capital-stars", "all-stations"];
```

- [ ] **Step 3: Replace the `all-stations` source with clustering enabled**

In the `m.on("load", ...)` callback, replace the `m.addSource("all-stations", ...)` line:

```ts
      m.addSource("all-stations", {
        type: "geojson",
        data: EMPTY as never,
        cluster: true,
        clusterRadius: 30,
        clusterMaxZoom: 7,
      });
```

- [ ] **Step 4: Add the capitals source**

After the existing `m.addSource("coverage", ...)`, add:

```ts
      m.addSource("capitals", { type: "geojson", data: EMPTY as never });
```

- [ ] **Step 5: Replace the `all-stations` layer with data-driven radius and add cluster layers**

Replace the existing `m.addLayer({ id: "all-stations", ... })`:

```ts
      m.addLayer({
        id: "all-stations", type: "circle", source: "all-stations",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-radius": dotRadiusExpression() as never,
          "circle-color": "#9ca3af", "circle-opacity": 0.7,
        },
      });
      m.addLayer({
        id: "station-clusters", type: "circle", source: "all-stations",
        filter: ["has", "point_count"],
        paint: {
          "circle-radius": clusterRadiusExpression() as never,
          "circle-color": "#9ca3af", "circle-opacity": 0.6,
        },
      });
      m.addLayer({
        id: "station-cluster-count", type: "symbol", source: "all-stations",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 11,
        },
        paint: { "text-color": "#ffffff" },
      });
```

- [ ] **Step 6: Add the `capital-stars` layer and register the star image**

After the `reach-dots` layer (the existing `m.addLayer({ id: "reach-dots", ... })` block), add:

```ts
      m.addImage("star-icon", drawStarIcon(30), { pixelRatio: 2 });
      m.addLayer({
        id: "capital-stars", type: "symbol", source: "capitals",
        layout: {
          "icon-image": "star-icon",
          "icon-size": 0.5,
          "icon-allow-overlap": true,
        },
      });
```

- [ ] **Step 7: Replace the click handler with cluster > pickFeature > empty ordering**

Replace the entire `m.on("click", ...)` handler block with:

```ts
      const clusterPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: true });
      m.on("click", (e) => {
        // 1. Cluster click — highest priority
        const clusterHits = m.queryRenderedFeatures(e.point, { layers: ["station-clusters"] });
        if (clusterHits.length) {
          const clusterId = clusterHits[0].properties!.cluster_id as number;
          const src = m.getSource("all-stations") as maplibregl.GeoJSONSource;
          src.getClusterLeaves(clusterId, 25, 0).then((leaves) => {
            const members = leaves.map((f) => ({
              id: f.properties!.id as string,
              name: f.properties!.name as string,
              n_dest: (f.properties!.n_dest as number) || 0,
            }));
            const sorted = sortForClusterList(members);
            const container = document.createElement("div");
            container.className = "cluster-popup";
            const ul = document.createElement("ul");
            for (const s of sorted) {
              const li = document.createElement("li");
              const btn = document.createElement("button");
              btn.textContent = s.name;
              btn.addEventListener("click", () => {
                propsRef.current.onSelectOrigin(s.id);
                clusterPopup.remove();
              });
              li.appendChild(btn);
              ul.appendChild(li);
            }
            container.appendChild(ul);
            clusterPopup.setLngLat(e.lngLat).setDOMContent(container).addTo(m);
          });
          return;
        }

        // 2. pickFeature — reach-dots > capital-stars > all-stations
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS })
          .map((f) => ({ layer: f.layer.id, id: f.properties!.id as string }));
        const pick = pickFeature(hits);
        if (!pick) {
          propsRef.current.onEmptyClick();
          return;
        }
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
      });
```

- [ ] **Step 8: Add cursor handlers for new interactive layers**

Replace the existing cursor-handler loop:

```ts
      for (const layer of ["all-stations", "reach-dots", "capital-stars", "station-clusters"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
```

- [ ] **Step 9: Update `syncData` to include `n_dest` in features, filter out capitals, and set capitals source**

Replace the `syncData` function body with:

```ts
  function syncData() {
    const m = map.current;
    if (!m) return;
    const { stations, reach, maxTrains, maxMinutes } = propsRef.current;
    const byId = new Map(stations.map((s) => [s.id, s]));

    const nonCapitals = stations.filter((s) => s.has_reach && !s.is_capital);
    (m.getSource("all-stations") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: nonCapitals.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, n_dest: s.n_dest },
      })),
    });

    const capitalStations = stations.filter((s) => s.is_capital);
    (m.getSource("capitals") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: capitalStations.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, n_dest: s.n_dest },
      })),
    });

    (m.getSource("reach-lines") as maplibregl.GeoJSONSource).setData(
      reach ? (linesGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    (m.getSource("reach-dots") as maplibregl.GeoJSONSource).setData(
      reach ? (destinationsGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    const origin = reach && byId.get(reach.origin);
    if (origin) m.easeTo({ center: [origin.lon, origin.lat], zoom: 5 });
  }
```

- [ ] **Step 10: Add CSS for the cluster popup**

In `web/src/index.css`, add at the end of the file:

```css
.cluster-popup ul { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow-y: auto; }
.cluster-popup li + li { border-top: 1px solid #e5e7eb; }
.cluster-popup button {
  display: block; width: 100%; padding: 6px 10px; border: 0; background: none;
  text-align: left; font-size: 13px; cursor: pointer;
}
.cluster-popup button:hover { background: #f3f4f6; }
```

- [ ] **Step 11: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 51 tests (unchanged from Task 2).

- [ ] **Step 12: Type-check and lint**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors.

- [ ] **Step 13: Manual visual check**

Start the dev server and verify in the browser:
- Grey dots have varying sizes (large for Berlin, small for tiny stations).
- 9 capital stars are visible (Berlin, Wien, Paris, Amsterdam, Madrid, Warsaw, Bern, Brussels, Prague).
- Zoomed out: small dots cluster into grey bubbles with counts.
- Click a cluster bubble → popup with station names sorted by connectivity.
- Click a name in the popup → selects as origin.
- Click a star → selects as origin.
- Click a colored reach-dot on top of a star → selects as destination.
- Zoom past z7.5 → clusters dissolve.

Run: `cd web && npm run dev`

- [ ] **Step 14: Commit**

```bash
git add web/src/components/Map.tsx web/src/index.css
git commit -m "feat: sized dots, capital stars, clustering + pick-list popup"
```

---

## Self-Review

Checked the completed plan against `docs/superpowers/specs/2026-07-11-dots-clustering-design.md`:

**Spec coverage:**
- §1 Pipeline `n_dest` + `is_capital`: `Station` model gains `n_dest: int` (default 0) and `is_capital: bool` (default False) → Task 1 Steps 1, 4. `compute_all` writes `n_dest` from `results[station.id]` → Task 1 Step 4. `capitals.toml` as curated file → Task 1 Step 2. `load_capitals` matches on exact name AND country, warns on unmatched → Task 1 Step 3. Seed with 9 verified stations → Task 1 Step 2. ✓
- §2 Sized dots: data-driven `circle-radius` with sqrt scale 2.5→8 clamped at 400 → Task 2 `dotRadiusExpression()` + Task 3 Step 5. Reach-dots stay fixed-size → unchanged `reach-dots` layer. ✓
- §3 Capital stars: capitals excluded from `all-stations` source → Task 3 Step 9 filters `!s.is_capital`. `capital-stars` symbol layer fed by `capitals` source → Task 3 Steps 4, 6. Canvas-drawn star via `addImage` → Task 2 `drawStarIcon` + Task 3 Step 6. Stars never clustered (separate source) and always visible → separate `capitals` source, no clustering. Click star → selects origin → `pickFeature` returns `{ type: "origin" }` for `capital-stars` → Task 2 Step 8. Precedence `reach-dots > capital-stars > all-stations` → Task 2 Step 8. When reach active, capital also appears as colored destination dot on top (reach-dots wins click) → existing `reach-dots` layer + precedence. ✓
- §4 Clustering: `all-stations` source enables clustering `clusterRadius: 30`, `clusterMaxZoom: 7` → Task 3 Step 3. `station-clusters` layer (grey bubble, radius by `point_count`) → Task 3 Step 5 + `clusterRadiusExpression`. `station-cluster-count` symbol label → Task 3 Step 5. Click bubble → `getClusterLeaves` → popup with names sorted by `n_dest` desc via `sortForClusterList` → Task 3 Step 7. Click name → `onSelectOrigin` + close popup → Task 3 Step 7. Cluster hits before `pickFeature`, never fall through → Task 3 Step 7 (cluster check first, then `return`). `reach-dots` never clustered (separate source) → unchanged. ✓
- §5 Testing: `dots.ts` unit tests for radius bounds, sorting, tie behavior → Task 2 Step 2 (8 tests). `pickfeature.test.ts` capital-stars precedence → Task 2 Step 6 (5 tests). Pipeline tests for `n_dest` count + `is_capital` + warning → Task 1 Step 5 (4 tests). Server test passthrough → Task 1 Step 8. Visual = user → global constraint. ✓
- Out of scope: C3 city-union, destination-dot sizing/clustering, star styling refinements — none implemented. ✓

**IMPORTANT wrinkle:** Cheap patch script to back-fill `n_dest`/`is_capital` into live `data/out/stations.json` without full recompute → Task 1 Step 11. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step has complete code. ✓

**Type consistency:** `n_dest: int` / `is_capital: bool` on Python `Station`, `n_dest: number` / `is_capital: boolean` on TS `Station` — consistent. `dotRadiusExpression` / `clusterRadiusExpression` / `sortForClusterList` / `drawStarIcon` names identical across `dots.ts`, `dots.test.ts`, and `Map.tsx` imports. `pickFeature` signature unchanged; `capital-stars` layer name consistent across `pickfeature.ts`, `pickfeature.test.ts`, `Map.tsx` `CLICK_LAYERS`, and layer definition. `load_capitals` signature consistent across `capitals.py`, `compute.py` import, and test imports. ✓
