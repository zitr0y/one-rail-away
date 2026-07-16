# Smoothed Line Trees Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the OSM-routed rail geometry with client-side smoothed "subway map style" cubic-Bézier curves computed over the origin's full hop tree, then delete the entire OSM paths subsystem (pipeline stage, committed artifact, API endpoint, client fetch).

**Architecture:** One new pure module `web/src/lib/smoothPaths.ts` builds a per-hop polyline lookup (same shape `hopCoords` consumes today, keyed by `segmentKey("idA|idB")`) from the FULL reach file: expand train legs into weighted hops, give each station exactly one tangent (degree-1: its hop's direction; degree≥2: weight-and-straightness-dominant bisector), draw each hop as a sampled cubic Bézier with control points along the sign-corrected station tangents. `App.tsx` computes the lookup memoized per reach file and threads it where `railPaths` went. Everything OSM-paths-related is deleted.

**Tech Stack:** TypeScript + React 19 + MapLibre (web, vitest for tests), Python + FastAPI (server, pytest), `uv` + `just` for pipeline tooling.

**Spec:** `docs/superpowers/specs/2026-07-17-smoothed-line-trees-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Stations are EXACT polyline vertices**: the first/last coordinate of every hop curve is exactly `[station.lon, station.lat]` — no float drift (trunk-dedup + rider invariant, backlog X).
- **One geometry per physical hop**: a hop shared by many journeys has exactly one polyline, independent of journey iteration order — trunks stay merged, no splay.
- **Full-reach-file stability rule**: tangents/geometry derive from the FULL reach file, never from the filtered/shown subset. The 1/2/3-trains selector and time slider hide lines but never reshape them.
- **`CURVINESS` is a single exported tunable constant**, value `0.25`, in `web/src/lib/smoothPaths.ts` — the only visual knob (user-judged tuning after ship).
- **No new network requests**: page load LOSES one fetch (`/api/rail-paths`). Nothing new is fetched.
- **Never throw during rendering**: empty/malformed reach file → empty lookup → straight-line fallback. Stations missing from `byId` → that hop absent from the lookup → straight line at render.
- The **straight-line fallback in `hopCoords` stays** (a hop absent from the lookup renders as a straight line).
- **Verification commands** (used throughout; run from repo root `/home/aaron/Projects/personal/de-trains-speed-map`):
  - Web tests: `cd web && npm test` (runs `vitest run`)
  - Web typecheck: `cd web && npx tsc -b`
  - Web lint: `cd web && npm run lint` (oxlint)
  - Python tests: `uv run pytest -q`
  - Python lint: `uv run ruff check .`
- Commit at the end of every task (small, frequent commits). Commit messages end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## File Structure

- Create: `web/src/lib/smoothPaths.ts` — pure geometry module (hop expansion → graph → tangents → Bézier sampling → lookup), no React/map imports.
- Create: `web/src/lib/smoothPaths.test.ts` — vitest units.
- Modify: `web/src/lib/geojson.ts` — export `segmentKey`; rename `RailPathLookup` → `HopGeometryLookup` and `railPaths` params → `hopGeometry` (the name no longer lies once OSM paths are gone); delete `buildRailPathLookup`.
- Modify: `web/src/App.tsx` — drop the `/api/rail-paths` fetch/state; memoized smoothed lookup instead.
- Modify: `web/src/components/Map.tsx` — prop rename only (`railPaths` → `hopGeometry`).
- Modify: `web/src/lib/geojson.test.ts` — lookup construction swap; new stability tests. Existing trunk-dedup / exact-vertex / fallback tests keep passing.
- Delete: `pipeline/railpaths.py`, `tests/test_railpaths.py`, `data/out/rail_paths.json`, `data/out/rail_paths.json.gz` (git rm).
- Modify: `pipeline/cli.py`, `tests/test_cli.py`, `server/app.py`, `tests/test_server.py`, `web/src/lib/api.ts`, `web/src/lib/types.ts`, `pipeline/artifacts.py` (docstring), `tests/test_compute.py` (comment), `docs/data-sources.md`, `.gitignore`.
- No change: `web/src/lib/ride.ts` (rider consumes `journeyLegPaths` output), `justfile` (its `pipeline-from` recipe takes the stage as an argument; nothing paths-specific in it — verified).

**Codebase note (spec deviation, verified by grep):** the web UI never actually rendered an OSM attribution string for rail paths — `RailPathsFile.attribution` was a data field that no component displayed (the only rendered attribution is `TIMETABLE_ATTRIBUTION` in `Map.tsx`, which stays). The spec's "delete OSM rail-paths attribution wherever it is displayed" is therefore satisfied by deleting the `RailPathsFile` type (Task 4) and the OSM row in `docs/data-sources.md` (Task 4). Do NOT touch `TIMETABLE_ATTRIBUTION` or the basemap's OSM credit (OpenFreeMap tiles are still OSM data).

---

### Task 1: `smoothPaths.ts` core — rename groundwork, hop expansion, hop graph, station tangents

**Files:**
- Modify: `web/src/lib/geojson.ts` (export `segmentKey`; rename `RailPathLookup` → `HopGeometryLookup`, `railPaths` → `hopGeometry`)
- Modify: `web/src/components/Map.tsx` (mechanical rename)
- Modify: `web/src/App.tsx` (mechanical rename — fetch removal comes later, in Task 3)
- Modify: `web/src/lib/geojson.test.ts` (type-name rename only)
- Create: `web/src/lib/smoothPaths.ts`
- Test: `web/src/lib/smoothPaths.test.ts`

**Interfaces:**
- Consumes: `segmentKey(a: string, b: string): string` and `isTrainLeg(leg: JourneyLeg): leg is Leg` from `web/src/lib/geojson.ts`; `ReachFile`, `Station`, `JourneyLeg` from `web/src/lib/types.ts`.
- Produces (later tasks rely on these exact names/signatures):
  - `export type HopGeometryLookup = Map<string, HopGeometry>` (in `geojson.ts`, renamed from `RailPathLookup`)
  - `export function segmentKey(a: string, b: string): string` (in `geojson.ts`, now exported)
  - In `smoothPaths.ts`:
    - `export type Vec = [number, number]`
    - `export interface Hop { a: string; b: string; weight: number }` (`a < b`, segmentKey order)
    - `export function expandHops(reach: ReachFile): Map<string, Hop>` (key = `segmentKey(a, b)`)
    - `export function stationTangents(hops: Map<string, Hop>, byId: Map<string, Station>): Map<string, Vec>`
    - module-private `direction(a: Station, b: Station): Vec` (Task 2 reuses it in the same file)

- [ ] **Step 1: Mechanical rename in `geojson.ts` — export `segmentKey`, honest type name**

The type will hold smoothed geometry, not OSM rail paths, so rename it now; all behavior is unchanged and the existing suite proves it. In `web/src/lib/geojson.ts`:

Replace:

```ts
function segmentKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}
```

with:

```ts
/** Direction-normalized hop key ("idA|idB", ids sorted) — shared with
 *  smoothPaths.ts, which builds its lookup under the same keys. */
export function segmentKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}
```

Replace:

```ts
/** Precomputed real-track geometry per physical hop, keyed by segmentKey.
 *  Built by `ose paths` (backlog I). */
export type RailPathLookup = Map<string, HopGeometry>;
```

with:

```ts
/** Precomputed smoothed geometry per physical hop, keyed by segmentKey.
 *  Built client-side by smoothPaths.ts (backlog I). */
export type HopGeometryLookup = Map<string, HopGeometry>;
```

Then replace **every remaining occurrence** in `web/src/lib/geojson.ts`: `RailPathLookup` → `HopGeometryLookup` (in `buildRailPathLookup`'s return type and body — the function itself is deleted in Task 3, leave it in place for now) and the parameter name `railPaths` → `hopGeometry`. The six affected function signatures must end up exactly like this (bodies: every use of `railPaths` becomes `hopGeometry`):

```ts
export function buildRailPathLookup(paths: Record<string, [number, number][]>): HopGeometryLookup {
```

```ts
function hopCoords(
  a: { id: string; station: Station }, b: { id: string; station: Station },
  hopGeometry: HopGeometryLookup | null,
): [number, number][] {
  const geometry = hopGeometry?.get(segmentKey(a.id, b.id));
```

```ts
export function legSegments(
  leg: Leg, stationsById: Map<string, Station>, hopGeometry: HopGeometryLookup | null,
): LegSegment[] {
```

```ts
export function journeyLegPaths(
  j: Journey, stationsById: Map<string, Station>, hopGeometry: HopGeometryLookup | null,
): [number, number][][] {
```

```ts
export function segmentsGeoJSON(
  shownList: ShownEntry[], stationsById: Map<string, Station>,
  hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
```

```ts
export function linesGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
  hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
```

```ts
export function selectedLineGeoJSON(
  reach: ReachFile | null, selectedDest: string | null, stationsById: Map<string, Station>,
  maxTrains: MaxTrains, maxMinutes: number, hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
```

Also update the `journeyLegPaths` doc comment: change the phrase `real-track geometry must never cut a stop's corner` to `hop geometry must never cut a stop's corner` (rest of the comment unchanged).

- [ ] **Step 2: Mechanical rename in `Map.tsx`, `App.tsx`, `geojson.test.ts`**

In `web/src/components/Map.tsx`, replace every occurrence of `RailPathLookup` with `HopGeometryLookup` and every occurrence of `railPaths` with `hopGeometry`. The occurrences (verify none are missed with the grep below): the import near the top (`transferPoints, type MaxTrains, type RailPathLookup,`), the `Props` member `railPaths: RailPathLookup | null;` (~line 53), the `syncData` destructure (~line 372) and `segmentsGeoJSON(shownList, byId, railPaths)` call (~line 378), the `syncData` dep array (~line 395), the `syncSelectedLine` destructure (~line 435), `selectedLineGeoJSON(...)` call (~line 438) and dep array (~line 443), the `syncRider` call `journeyLegPaths(journey, byId, propsRef.current.railPaths)` (~line 559) and its dep array (~line 616).

In `web/src/App.tsx`, same two replacements: the import on line 10 (`type RailPathLookup` → `type HopGeometryLookup`), the state `const [railPaths, setRailPaths] = useState<RailPathLookup | null>(null);` → `const [hopGeometry, setHopGeometry] = useState<HopGeometryLookup | null>(null);`, the fetch effect (`setRailPaths(...)` → `setHopGeometry(...)`, twice), and the `MapView` prop `railPaths={railPaths}` → `hopGeometry={hopGeometry}`. (The fetch itself is deleted in Task 3 — only rename here.)

In `web/src/lib/geojson.test.ts`, replace `type RailPathLookup` with `type HopGeometryLookup` in the import block (line 5) and the one annotation `const railPaths: RailPathLookup = buildRailPathLookup({` → `const railPaths: HopGeometryLookup = buildRailPathLookup({` (local variable names stay for now; Task 3 rewrites those tests).

Verify nothing is left (the local `railPaths` variable names inside `geojson.test.ts` are allowed to stay until Task 3 rewrites those tests):

Run: `grep -rn "RailPathLookup" web/src`
Expected: no output.

Run: `grep -rn "railPaths" web/src | grep -v "lib/geojson.test.ts"`
Expected: no output. (`getRailPaths` / `RailPathsFile` in `api.ts`/`types.ts` don't match this case-sensitive pattern and are deleted in Task 4.)

- [ ] **Step 3: Run the web suite + typecheck to prove the rename is behavior-neutral**

Run: `cd web && npx tsc -b && npm test`
Expected: typecheck clean; all test files PASS (geojson.test.ts unchanged in behavior).

- [ ] **Step 4: Commit the rename**

```bash
git add web/src/lib/geojson.ts web/src/components/Map.tsx web/src/App.tsx web/src/lib/geojson.test.ts
git commit -m "refactor(web): rename RailPathLookup->HopGeometryLookup, export segmentKey

Groundwork for smoothed line trees (backlog I): the lookup is about to hold
client-computed smoothed geometry, not OSM rail paths.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Write the failing tests for hop expansion + tangents**

Create `web/src/lib/smoothPaths.test.ts` with exactly:

```ts
import { describe, expect, it } from "vitest";
import { expandHops, stationTangents } from "./smoothPaths";
import type { Journey, JourneyLeg, ReachFile, Station } from "./types";

const S = (id: string, lon: number, lat: number): [string, Station] =>
  [id, { id, name: id, lon, lat, country: "XX", has_reach: true }];

const leg = (from: string, to: string, via: string[] = []): JourneyLeg =>
  ({ train: "ICE 1", dep: "08:00", arr: "09:00", from, to, via });

const journey = (...legs: JourneyLeg[]): Journey =>
  ({ trains: legs.length, duration_min: 60, legs });

/** One destination per journey list — enough shape for the geometry code. */
const reachOf = (...journeyLists: Journey[][]): ReachFile => ({
  origin: "A", computed_at: "", sample_date: "2026-07-14",
  destinations: journeyLists.map((journeys, i) => ({
    id: `dest${i}`, direct_per_day: 1, journeys,
  })),
});

describe("expandHops", () => {
  it("expands [from, ...via, to] into weighted consecutive hops", () => {
    const hops = expandHops(reachOf([journey(leg("A", "C", ["B"]))]));
    expect([...hops.keys()].sort()).toEqual(["A|B", "B|C"]);
    expect(hops.get("A|B")).toEqual({ a: "A", b: "B", weight: 1 });
  });

  it("accumulates weight per traversal and direction-normalizes the key", () => {
    const hops = expandHops(reachOf(
      [journey(leg("A", "C", ["B"]))],
      [journey(leg("C", "A", ["B"]))], // opposite direction, same physical hops
    ));
    expect(hops.size).toBe(2);
    expect(hops.get("A|B")!.weight).toBe(2);
    expect(hops.get("B|C")!.weight).toBe(2);
  });

  it("skips transfer legs", () => {
    const transfer: JourneyLeg =
      { type: "transfer", mode: "walk", minutes: 10, from_id: "B", to_id: "X" };
    const hops = expandHops(reachOf([journey(leg("A", "B"), transfer, leg("X", "C"))]));
    expect([...hops.keys()].sort()).toEqual(["A|B", "C|X"]);
  });

  it("drops zero-length hops from repeated consecutive stop ids", () => {
    const hops = expandHops(reachOf([journey(leg("A", "B", ["A"]))]));
    expect([...hops.keys()]).toEqual(["A|B"]);
  });

  it("returns an empty map for a malformed reach file instead of throwing", () => {
    expect(expandHops({} as ReachFile).size).toBe(0);
    expect(expandHops(null as unknown as ReachFile).size).toBe(0);
  });
});

describe("stationTangents", () => {
  // Collinear east-west line at lat 50 — directions must be angle-true even
  // though a lon-degree is only cos(50°) of a lat-degree here.
  const line = new Map([S("A", 8, 50), S("B", 9, 50), S("C", 10, 50)]);

  it("degree-1 station: tangent is its single hop's direction", () => {
    const hops = expandHops(reachOf([journey(leg("A", "B"))]));
    const ta = stationTangents(hops, line).get("A")!;
    expect(Math.abs(ta[0])).toBeCloseTo(1, 6); // along the east-west hop
    expect(ta[1]).toBeCloseTo(0, 6);
  });

  it("degree-2 through-station: tangent is the bisector of the through pair", () => {
    const hops = expandHops(reachOf([journey(leg("A", "C", ["B"]))]));
    const tb = stationTangents(hops, line).get("B")!;
    expect(Math.abs(tb[0])).toBeCloseTo(1, 6);
    expect(tb[1]).toBeCloseTo(0, 6);
  });

  it("weight × straightness picks the dominant through pair over a light branch", () => {
    const stations = new Map([...line, S("D", 9, 51)]); // branch due north of B
    const heavy = journey(leg("A", "C", ["B"]));
    const hops = expandHops(reachOf([heavy], [heavy], [heavy], [journey(leg("B", "D"))]));
    const tb = stationTangents(hops, stations).get("B")!;
    expect(Math.abs(tb[0])).toBeGreaterThan(0.99); // stays on the A–C axis
  });

  it("is independent of journey iteration order", () => {
    const stations = new Map([...line, S("D", 9, 51), S("E", 11, 50.2)]);
    const journeys = [
      journey(leg("A", "C", ["B"])),
      journey(leg("B", "D")),
      journey(leg("A", "E", ["B", "C"])),
    ];
    const forward = reachOf(...journeys.map((j) => [j]));
    const reversed = reachOf(...journeys.map((j) => [j]).reverse());
    const tf = stationTangents(expandHops(forward), stations);
    const tr = stationTangents(expandHops(reversed), stations);
    expect(Object.fromEntries(tf)).toEqual(Object.fromEntries(tr));
  });

  it("ignores hops whose stations are missing from byId", () => {
    const hops = expandHops(reachOf([journey(leg("A", "Z"))])); // Z unknown
    const t = stationTangents(hops, line);
    expect(t.has("Z")).toBe(false);
    expect(t.has("A")).toBe(false); // its only hop was unusable
  });
});
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd web && npm test -- src/lib/smoothPaths.test.ts`
Expected: FAIL — cannot resolve `./smoothPaths` (module does not exist).

- [ ] **Step 7: Implement hop expansion + tangents**

Create `web/src/lib/smoothPaths.ts` with exactly:

```ts
/** Client-side smoothed "subway map style" curves for reach-line hops
 *  (backlog I — replaces the OSM-routed `ose paths` geometry, 2026-07-17).
 *
 *  Every train hop in the origin's FULL reach file gets a gentle cubic-Bézier
 *  curve through the real station positions. By construction: stations are
 *  EXACT curve endpoints (trunk-dedup + rider invariant, backlog X); a hop
 *  shared by many journeys has exactly one geometry (trunks stay merged); a
 *  line passing through a station enters and leaves along one shared tangent
 *  (no kink at served stops); branches leave a trunk along the shared tangent,
 *  then bend away.
 *
 *  Pure functions — no map or React dependency. Never throws: malformed input
 *  degrades to an empty lookup, and hopCoords (geojson.ts) falls back to
 *  straight lines for anything missing. */
import { isTrainLeg, segmentKey } from "./geojson";
import type { ReachFile, Station } from "./types";

/** Planar direction/position vector: [x (east), y (north)]. */
export type Vec = [number, number];

/** One physical hop of the graph. `a < b` (segmentKey order). */
export interface Hop { a: string; b: string; weight: number }

/** Every train hop in the reach file, keyed by segmentKey(a, b), weighted by
 *  the number of journey traversals. Transfer legs contribute nothing; hops
 *  between identical consecutive stop ids are dropped. Defensive against
 *  malformed input: anything unexpected yields fewer hops, never a throw. */
export function expandHops(reach: ReachFile): Map<string, Hop> {
  const hops = new Map<string, Hop>();
  const destinations = Array.isArray(reach?.destinations) ? reach.destinations : [];
  for (const d of destinations) {
    for (const j of d?.journeys ?? []) {
      for (const leg of j?.legs ?? []) {
        if (!isTrainLeg(leg)) continue;
        const stops = [leg.from, ...(leg.via ?? []), leg.to];
        for (let i = 0; i < stops.length - 1; i++) {
          const s = stops[i];
          const t = stops[i + 1];
          if (s === t) continue; // zero-length hop
          const key = segmentKey(s, t);
          const hop = hops.get(key);
          if (hop) hop.weight += 1;
          else hops.set(key, { a: s < t ? s : t, b: s < t ? t : s, weight: 1 });
        }
      }
    }
  }
  return hops;
}

/** Unit vector from `a` toward `b` in a locally angle-true plane: lon scaled
 *  by cos(mid latitude) so directions are true angles, not lon/lat-squished.
 *  Zero vector when the stations coincide. */
function direction(a: Station, b: Station): Vec {
  const midLat = ((a.lat + b.lat) / 2) * (Math.PI / 180);
  const dx = (b.lon - a.lon) * Math.cos(midLat);
  const dy = b.lat - a.lat;
  const len = Math.hypot(dx, dy);
  return len === 0 ? [0, 0] : [dx / len, dy / len];
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V): void {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

/** All incident directions point AWAY from the station. A pair that passes
 *  straight through has opposing directions (dot ≈ −1), so alignment
 *  (1 − dot) / 2 is 1 for straight-through and 0 for a doubled-back pair.
 *  The winning pair's tangent is its bisector with one side flipped so the
 *  two oppose: normalize(u − v). */
function dominantTangent(list: { dir: Vec; weight: number }[]): Vec {
  if (list.length === 1) return list[0].dir;
  let best: Vec = list[0].dir;
  let bestScore = -Infinity;
  for (let i = 0; i < list.length; i++) {
    for (let j = i + 1; j < list.length; j++) {
      const u = list[i].dir;
      const v = list[j].dir;
      const alignment = (1 - (u[0] * v[0] + u[1] * v[1])) / 2;
      const score = (list[i].weight + list[j].weight) * alignment;
      if (score > bestScore) {
        bestScore = score;
        const t: Vec = [u[0] - v[0], u[1] - v[1]];
        const len = Math.hypot(t[0], t[1]);
        best = len === 0 ? u : [t[0] / len, t[1] / len];
      }
    }
  }
  return best;
}

/** Exactly ONE tangent per station: degree 1 → its hop's direction; degree
 *  ≥ 2 → the dominant through-direction (combined weight × straightness
 *  alignment). Hops with a station missing from `byId` are ignored (they fall
 *  back to straight lines at render). Iteration runs over SORTED hop keys so
 *  the result is independent of journey order in the reach file. */
export function stationTangents(
  hops: Map<string, Hop>, byId: Map<string, Station>,
): Map<string, Vec> {
  const incident = new Map<string, { dir: Vec; weight: number }[]>();
  for (const key of [...hops.keys()].sort()) {
    const hop = hops.get(key)!;
    const a = byId.get(hop.a);
    const b = byId.get(hop.b);
    if (!a || !b) continue;
    const dirAB = direction(a, b);
    if (dirAB[0] === 0 && dirAB[1] === 0) continue; // co-located stations
    push(incident, hop.a, { dir: dirAB, weight: hop.weight });
    push(incident, hop.b, { dir: [-dirAB[0], -dirAB[1]], weight: hop.weight });
  }
  const tangents = new Map<string, Vec>();
  for (const [id, list] of incident) tangents.set(id, dominantTangent(list));
  return tangents;
}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd web && npm test -- src/lib/smoothPaths.test.ts`
Expected: PASS — all `expandHops` and `stationTangents` tests green.

- [ ] **Step 9: Run the full web suite + typecheck**

Run: `cd web && npx tsc -b && npm test`
Expected: everything PASS.

- [ ] **Step 10: Commit**

```bash
git add web/src/lib/smoothPaths.ts web/src/lib/smoothPaths.test.ts
git commit -m "feat(web): smoothPaths core - hop graph + station tangents (backlog I)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `smoothPaths.ts` — Bézier curves, sampling, lookup builder, memoization

**Files:**
- Modify: `web/src/lib/smoothPaths.ts` (append; one import-line edit)
- Test: `web/src/lib/smoothPaths.test.ts` (append)

**Interfaces:**
- Consumes (already in `web/src/lib/smoothPaths.ts` from Task 1): `expandHops(reach: ReachFile): Map<string, Hop>`, `stationTangents(hops, byId): Map<string, Vec>`, private `direction(a: Station, b: Station): Vec`, `type Vec = [number, number]`, `interface Hop { a: string; b: string; weight: number }`. From `web/src/lib/geojson.ts`: `export type HopGeometryLookup = Map<string, HopGeometry>` where `HopGeometry = { fwd: [number, number][]; rev: [number, number][] }`.
- Produces (Task 3 relies on these exact names):
  - `export const CURVINESS = 0.25;`
  - `export function buildSmoothedLookup(reach: ReachFile, byId: Map<string, Station>): HopGeometryLookup`
  - `export function smoothedLookupFor(reach: ReachFile, byId: Map<string, Station>): HopGeometryLookup` (WeakMap-memoized per reach identity)

- [ ] **Step 1: Write the failing tests**

Append to `web/src/lib/smoothPaths.test.ts` (and extend the import at the top of the file from `import { expandHops, stationTangents } from "./smoothPaths";` to `import { buildSmoothedLookup, expandHops, smoothedLookupFor, stationTangents } from "./smoothPaths";`):

```ts
const norm = ([x, y]: [number, number]): [number, number] => {
  const l = Math.hypot(x, y);
  return [x / l, y / l];
};

describe("buildSmoothedLookup", () => {
  // Gentle east-west line with a slight bend at B, near the equator so
  // lon/lat distances are near-planar and the assertions stay readable.
  const bent = new Map([S("A", 0, 0), S("B", 2, 0.5), S("C", 4, 0)]);
  const bentReach = reachOf([journey(leg("A", "C", ["B"]))]);

  it("station coordinates are the exact first/last curve vertices", () => {
    const lookup = buildSmoothedLookup(bentReach, bent);
    const ab = lookup.get("A|B")!;
    expect(ab.fwd[0]).toEqual([0, 0]);
    expect(ab.fwd[ab.fwd.length - 1]).toEqual([2, 0.5]);
    expect(ab.rev[0]).toEqual([2, 0.5]);
    expect(ab.rev[ab.rev.length - 1]).toEqual([0, 0]);
  });

  it("a shared hop has exactly one geometry, independent of journey order", () => {
    const twoJourneys = reachOf([journey(leg("A", "B"))], [journey(leg("A", "C", ["B"]))]);
    const reordered = reachOf([journey(leg("A", "C", ["B"]))], [journey(leg("A", "B"))]);
    const l1 = buildSmoothedLookup(twoJourneys, bent);
    const l2 = buildSmoothedLookup(reordered, bent);
    expect(l1.size).toBe(2);
    expect(Object.fromEntries(l1)).toEqual(Object.fromEntries(l2));
  });

  it("curves join collinearly at a through station (no kink at B)", () => {
    const lookup = buildSmoothedLookup(bentReach, bent);
    const into = lookup.get("A|B")!.fwd; // oriented A→B
    const out = lookup.get("B|C")!.fwd;  // oriented B→C
    const [x1, y1] = into[into.length - 2];
    const u = norm([2 - x1, 0.5 - y1]); // arrival direction at B
    const [x2, y2] = out[1];
    const v = norm([x2 - 2, y2 - 0.5]); // departure direction from B
    expect(u[0] * v[0] + u[1] * v[1]).toBeGreaterThan(0.99);
  });

  it("an isolated two-point hop degenerates to a straight line", () => {
    const pair = new Map([S("A", 0, 0), S("B", 2, 0)]); // horizontal, ~222 km
    const lookup = buildSmoothedLookup(reachOf([journey(leg("A", "B"))]), pair);
    const fwd = lookup.get("A|B")!.fwd;
    expect(fwd.length).toBeGreaterThanOrEqual(8); // MIN_POINTS floor
    for (const [, y] of fwd) expect(y).toBe(0);   // exactly on the line
  });

  it("a filtered subset would produce different geometry — full file required", () => {
    // With only the A→B journey, B is degree-1 and A|B is straight; the full
    // file's A→C-via-B journey pulls B's tangent onto the through-axis. This
    // is WHY the lookup must always come from the full reach file.
    const full = reachOf([journey(leg("A", "B"))], [journey(leg("A", "C", ["B"]))]);
    const subset = reachOf([journey(leg("A", "B"))]);
    const fullLookup = buildSmoothedLookup(full, bent);
    const subsetLookup = buildSmoothedLookup(subset, bent);
    expect(fullLookup.get("A|B")!.fwd).not.toEqual(subsetLookup.get("A|B")!.fwd);
  });

  it("transfer legs contribute no geometry", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0), S("X", 1.01, 0.01), S("C", 2, 0)]);
    const withTransfer = reachOf([journey(
      leg("A", "B"),
      { type: "transfer", mode: "walk", minutes: 10, from_id: "B", to_id: "X" },
      leg("X", "C"),
    )]);
    const lookup = buildSmoothedLookup(withTransfer, stations);
    expect([...lookup.keys()].sort()).toEqual(["A|B", "C|X"]);
  });

  it("hops with a station missing from byId are absent (straight fallback)", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0)]); // C unknown
    const lookup = buildSmoothedLookup(reachOf([journey(leg("A", "C", ["B"]))]), stations);
    expect(lookup.has("A|B")).toBe(true);
    expect(lookup.has("B|C")).toBe(false);
  });

  it("malformed reach file yields an empty lookup, never a throw", () => {
    expect(buildSmoothedLookup({} as ReachFile, new Map()).size).toBe(0);
  });
});

describe("smoothedLookupFor memoization", () => {
  it("returns the same Map instance for the same reach file + stations", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0)]);
    const reach = reachOf([journey(leg("A", "B"))]);
    const first = smoothedLookupFor(reach, stations);
    expect(smoothedLookupFor(reach, stations)).toBe(first);
    // A new reach identity (e.g. a re-fetch) recomputes.
    expect(smoothedLookupFor(reachOf([journey(leg("A", "B"))]), stations)).not.toBe(first);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd web && npm test -- src/lib/smoothPaths.test.ts`
Expected: FAIL — `buildSmoothedLookup` / `smoothedLookupFor` are not exported.

- [ ] **Step 3: Implement curves, sampling, lookup, memo**

In `web/src/lib/smoothPaths.ts`, change the geojson import line from:

```ts
import { isTrainLeg, segmentKey } from "./geojson";
```

to:

```ts
import { isTrainLeg, segmentKey, type HopGeometryLookup } from "./geojson";
```

Then append to the end of the file:

```ts
/** Single visual tunable: control-point distance as a fraction of hop
 *  length. User-judged after ship — raise for curvier, lower for straighter. */
export const CURVINESS = 0.25;

/** Control points never exceed this fraction of the hop length (self-
 *  intersection guard if CURVINESS is ever tuned up)... */
const MAX_CONTROL_FRACTION = 0.4;
/** ...nor this absolute distance, so short hops in dense areas don't
 *  overshoot into neighbouring stations. */
const MAX_CONTROL_KM = 30;

const KM_PER_DEG = 111.32; // per degree of latitude; lon scaled by cos(lat)

// Sampling: points per curve scale with hop length between these bounds.
const MIN_POINTS = 8;
const MAX_POINTS = 40;
const KM_PER_POINT = 12;

function hopLengthKm(a: Station, b: Station): number {
  const midLat = ((a.lat + b.lat) / 2) * (Math.PI / 180);
  const dx = (b.lon - a.lon) * Math.cos(midLat) * KM_PER_DEG;
  const dy = (b.lat - a.lat) * KM_PER_DEG;
  return Math.hypot(dx, dy);
}

/** Flip `t` if needed so it points along `dir` (non-negative dot). */
function flipAlong(t: Vec, dir: Vec): Vec {
  return t[0] * dir[0] + t[1] * dir[1] >= 0 ? t : [-t[0], -t[1]];
}

/** The point `km` kilometres from station `s` along planar unit vector `v`,
 *  back in [lon, lat] degrees (lon un-scaled by cos of the station's lat). */
function offsetKm(s: Station, v: Vec, km: number): Vec {
  const cosLat = Math.cos(s.lat * (Math.PI / 180));
  return [s.lon + (km * v[0]) / (KM_PER_DEG * cosLat), s.lat + (km * v[1]) / KM_PER_DEG];
}

function cubic(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: number): [number, number] {
  const u = 1 - t;
  const c0 = u * u * u;
  const c1 = 3 * u * u * t;
  const c2 = 3 * u * t * t;
  const c3 = t * t * t;
  return [
    c0 * p0[0] + c1 * p1[0] + c2 * p2[0] + c3 * p3[0],
    c0 * p0[1] + c1 * p1[1] + c2 * p2[1] + c3 * p3[1],
  ];
}

function dedupeConsecutive(coords: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const c of coords) {
    const last = out[out.length - 1];
    if (last && last[0] === c[0] && last[1] === c[1]) continue;
    out.push(c);
  }
  return out;
}

/** One hop's cubic Bézier, oriented a→b, sampled to a polyline. First/last
 *  vertices are EXACTLY the station coordinates (assigned, not computed — no
 *  float drift). `ta`/`tb` are the stations' tangents, sign-corrected here to
 *  point along the a→b travel direction. */
function hopCurve(a: Station, b: Station, ta: Vec, tb: Vec): [number, number][] {
  const lengthKm = hopLengthKm(a, b);
  if (lengthKm === 0) return [[a.lon, a.lat], [b.lon, b.lat]];
  const dirAB = direction(a, b);
  const sa = flipAlong(ta, dirAB);
  const sb = flipAlong(tb, dirAB);
  const d = Math.min(CURVINESS * lengthKm, MAX_CONTROL_FRACTION * lengthKm, MAX_CONTROL_KM);
  const p0: Vec = [a.lon, a.lat];
  const p3: Vec = [b.lon, b.lat];
  const p1 = offsetKm(a, sa, d);
  const p2 = offsetKm(b, sb, -d);
  const points = Math.min(MAX_POINTS, Math.max(MIN_POINTS, Math.round(lengthKm / KM_PER_POINT)));
  const out: [number, number][] = [];
  for (let i = 0; i < points; i++) out.push(cubic(p0, p1, p2, p3, i / (points - 1)));
  out[0] = [a.lon, a.lat];
  out[out.length - 1] = [b.lon, b.lat];
  return dedupeConsecutive(out);
}

/** The smoothed lookup for a reach file: one HopGeometry per train hop, keyed
 *  by segmentKey, `fwd` oriented idA→idB (idA < idB). MUST be built from the
 *  FULL reach file — filters (1/2/3 trains, time slider) hide lines but never
 *  reshape them. Never throws: malformed input yields an empty lookup and the
 *  render side falls back to straight lines. */
export function buildSmoothedLookup(
  reach: ReachFile, byId: Map<string, Station>,
): HopGeometryLookup {
  try {
    const hops = expandHops(reach);
    const tangents = stationTangents(hops, byId);
    const lookup: HopGeometryLookup = new Map();
    for (const key of [...hops.keys()].sort()) {
      const hop = hops.get(key)!;
      const a = byId.get(hop.a);
      const b = byId.get(hop.b);
      if (!a || !b) continue; // stale reach vs stations.json → straight fallback
      const dirAB = direction(a, b);
      const fwd = hopCurve(a, b, tangents.get(hop.a) ?? dirAB, tangents.get(hop.b) ?? dirAB);
      if (fwd.length < 2) continue; // co-located stations degenerate away
      lookup.set(key, { fwd, rev: [...fwd].reverse() });
    }
    return lookup;
  } catch {
    return new Map();
  }
}

/** Memoized per reach-file identity (and stations identity) so filter and
 *  selection churn never recomputes — a full reach file is ~4k hops worst
 *  case, target <10 ms, but once is still better than every render. */
const memo = new WeakMap<ReachFile, { byId: Map<string, Station>; lookup: HopGeometryLookup }>();

export function smoothedLookupFor(
  reach: ReachFile, byId: Map<string, Station>,
): HopGeometryLookup {
  const hit = memo.get(reach);
  if (hit && hit.byId === byId) return hit.lookup;
  const lookup = buildSmoothedLookup(reach, byId);
  memo.set(reach, { byId, lookup });
  return lookup;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd web && npm test -- src/lib/smoothPaths.test.ts`
Expected: PASS — all smoothPaths tests green.

- [ ] **Step 5: Full web suite + typecheck + lint**

Run: `cd web && npx tsc -b && npm test && npm run lint`
Expected: all PASS, lint clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/smoothPaths.ts web/src/lib/smoothPaths.test.ts
git commit -m "feat(web): smoothed Bezier hop curves + memoized lookup builder (backlog I)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire smoothed geometry into the app, retire `buildRailPathLookup`

**Files:**
- Modify: `web/src/App.tsx` (lines ~10, ~22, ~36-42, ~172 — drop rail-paths fetch/state, add memoized lookup)
- Modify: `web/src/lib/geojson.ts` (delete `buildRailPathLookup`)
- Test: `web/src/lib/geojson.test.ts` (lookup construction swap + stability tests)

**Interfaces:**
- Consumes: `smoothedLookupFor(reach: ReachFile, byId: Map<string, Station>): HopGeometryLookup` and `buildSmoothedLookup(reach, byId): HopGeometryLookup` from `web/src/lib/smoothPaths.ts`; `HopGeometry = { fwd: [number, number][]; rev: [number, number][] }` and `type HopGeometryLookup = Map<string, HopGeometry>` from `web/src/lib/geojson.ts`. `Map.tsx` already takes `hopGeometry: HopGeometryLookup | null` (renamed in Task 1) — no `Map.tsx` change in this task.
- Produces: `App.tsx` computes `hopGeometry` via `useMemo` + `smoothedLookupFor` and passes it to `MapView`; `buildRailPathLookup` no longer exists (Task 4 deletes its data source).

- [ ] **Step 1: Update `geojson.test.ts` — build lookups without `buildRailPathLookup`, fail first**

In `web/src/lib/geojson.test.ts`:

Replace the import block at the top:

```ts
import {
  bestJourney, buildRailPathLookup, destinationsGeoJSON, frequencyClass, journeyLegPaths,
  legSegments, linesGeoJSON, segmentsGeoJSON, selectedLineGeoJSON, shown, timeBucket,
  transferPoints, type HopGeometryLookup, initialMaxTrains,
} from "./geojson";
import type { Journey, Leg, ReachFile, Station } from "./types";
```

with:

```ts
import {
  bestJourney, destinationsGeoJSON, frequencyClass, journeyLegPaths,
  legSegments, linesGeoJSON, segmentsGeoJSON, selectedLineGeoJSON, shown, timeBucket,
  transferPoints, type HopGeometryLookup, initialMaxTrains,
} from "./geojson";
import { buildSmoothedLookup } from "./smoothPaths";
import type { Journey, Leg, ReachFile, Station } from "./types";
```

Directly after the `const reach: ReachFile = { ... };` literal (ends around line 23), add:

```ts
/** Hand-built lookup entry — both orientations, like buildSmoothedLookup emits. */
const hopGeom = (coords: [number, number][]) =>
  ({ fwd: coords, rev: [...coords].reverse() });
```

In the `selectedLineGeoJSON (backlog AU)` describe, replace:

```ts
  it("equals the old linesGeoJSON output with rail-path geometry threaded through", () => {
    const railPaths = buildRailPathLookup({ "A|B": [[8, 50], [8.5, 50.2], [9, 50]] });
    const old = linesGeoJSON(reach, stationsById, 3, Infinity, railPaths)
      .features.find((f) => f.properties.id === "D")!;
    const next = selectedLineGeoJSON(reach, "D", stationsById, 3, Infinity, railPaths).features[0];
    expect(next).toEqual(old);
  });
```

with:

```ts
  it("equals the old linesGeoJSON output with hop geometry threaded through", () => {
    const hopGeometry: HopGeometryLookup =
      new Map([["A|B", hopGeom([[8, 50], [8.5, 50.2], [9, 50]])]]);
    const old = linesGeoJSON(reach, stationsById, 3, Infinity, hopGeometry)
      .features.find((f) => f.properties.id === "D")!;
    const next = selectedLineGeoJSON(reach, "D", stationsById, 3, Infinity, hopGeometry).features[0];
    expect(next).toEqual(old);
  });
```

Replace the whole `describe("legSegments with rail paths", () => { ... });` block with (only the lookup construction, variable name, and titles change — the assertions are identical):

```ts
describe("legSegments with hop geometry", () => {
  const hopGeometry: HopGeometryLookup = new Map([
    ["a|b", hopGeom([[0, 0], [0.5, 0.4], [1, 0]])],
  ]);

  it("uses lookup geometry for a hop when present", () => {
    expect(legSegments(railLeg("a", "b", []), railStationsById, hopGeometry)[0].coords)
      .toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
  });

  it("reverses geometry when the hop travels against key order", () => {
    expect(legSegments(railLeg("b", "a", []), railStationsById, hopGeometry)[0].coords)
      .toEqual([[1, 0], [0.5, 0.4], [0, 0]]);
    // Original forward entry must not be mutated by the reversal.
    expect(hopGeometry.get("a|b")!.fwd[0]).toEqual([0, 0]);
  });

  it("falls back to a straight line for hops without geometry", () => {
    expect(legSegments(railLeg("b", "c", []), railStationsById, hopGeometry)[0].coords)
      .toEqual([[1, 0], [2, 0]]);
  });

  it("splits a via-leg into per-hop segments, each with its own lookup", () => {
    const segments = legSegments(railLeg("a", "c", ["b"]), railStationsById, hopGeometry);
    expect(segments.map((s) => s.key)).toEqual(["a|b", "b|c"]);
    expect(segments[0].coords).toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
    expect(segments[1].coords).toEqual([[1, 0], [2, 0]]);
  });

  it("journeyLegPaths threads geometry and keeps stops as exact vertices", () => {
    const journey = { trains: 1, duration_min: 60, legs: [railLeg("a", "c", ["b"])] };
    expect(journeyLegPaths(journey, railStationsById, hopGeometry))
      .toEqual([[[0, 0], [0.5, 0.4], [1, 0], [2, 0]]]);
  });
});
```

Then append a new describe at the end of the file — the full-reach-file stability guard:

```ts
describe("smoothed geometry integration (backlog I)", () => {
  // The lookup is built ONCE from the full reach file; filters must only
  // hide lines, never reshape them.
  const lookup = buildSmoothedLookup(reach, stationsById);

  it("stations stay exact vertices with smoothed geometry threaded through", () => {
    const fc = linesGeoJSON(reach, stationsById, 1, Infinity, lookup);
    const coords = fc.features.find((f) => f.properties.id === "C")!
      .geometry.coordinates as [number, number][];
    const a = stationsById.get("A")!;
    const b = stationsById.get("B")!;
    const c = stationsById.get("C")!;
    expect(coords[0]).toEqual([a.lon, a.lat]);
    expect(coords[coords.length - 1]).toEqual([c.lon, c.lat]);
    expect(coords).toContainEqual([b.lon, b.lat]);
  });

  it("filters never reshape geometry: same hop, same coords at 1 and 3 trains", () => {
    const at1 = segmentsGeoJSON(shown(reach, 1, Infinity), stationsById, lookup);
    const at3 = segmentsGeoJSON(shown(reach, 3, Infinity), stationsById, lookup);
    const ab1 = at1.features.find((f) => f.properties.id === "A|B")!;
    const ab3 = at3.features.find((f) => f.properties.id === "A|B")!;
    expect(ab1.geometry.coordinates).toEqual(ab3.geometry.coordinates);
    expect(ab3.geometry.coordinates).toEqual(lookup.get("A|B")!.fwd);
  });

  it("journeys sharing a trunk keep identical smoothed trunk coords (backlog X)", () => {
    const fc = linesGeoJSON(reach, stationsById, 3, Infinity, lookup);
    const toC = fc.features.find((f) => f.properties.id === "C")!
      .geometry.coordinates as [number, number][];
    const toD = fc.features.find((f) => f.properties.id === "D")!
      .geometry.coordinates as [number, number][];
    expect(toD.slice(0, toC.length)).toEqual(toC);
  });
});
```

- [ ] **Step 2: Run geojson tests to verify the rewritten suite is green**

Run: `cd web && npm test -- src/lib/geojson.test.ts`
Expected: PASS — the test file no longer references `buildRailPathLookup` (so it is safe to delete next), the pre-existing trunk-dedup / exact-vertex / fallback tests still pass unchanged, and the new stability tests pass because `buildSmoothedLookup` exists since Task 2.

- [ ] **Step 3: Delete `buildRailPathLookup` from `geojson.ts`**

In `web/src/lib/geojson.ts`, delete this entire block (nothing imports it any more except `App.tsx`, fixed next step):

```ts
/** Builds the lookup from the raw `{segmentKey: coords}` payload the API
 *  serves — the one place both orientations get materialized (backlog AU). */
export function buildRailPathLookup(paths: Record<string, [number, number][]>): HopGeometryLookup {
  const lookup: HopGeometryLookup = new Map();
  for (const [key, coords] of Object.entries(paths)) {
    lookup.set(key, { fwd: coords, rev: [...coords].reverse() });
  }
  return lookup;
}
```

- [ ] **Step 4: Swap the geometry source in `App.tsx`**

In `web/src/App.tsx` (line numbers from the pre-edit file):

Replace line 10:

```ts
import { buildRailPathLookup, initialMaxTrains, type MaxTrains, type HopGeometryLookup } from "./lib/geojson";
```

with:

```ts
import { initialMaxTrains, type MaxTrains } from "./lib/geojson";
import { smoothedLookupFor } from "./lib/smoothPaths";
```

(If Task 1's rename left `type HopGeometryLookup` unused after this edit, it must be dropped from the import — the line above is the exact final form.)

Delete the state line (~22):

```ts
  const [hopGeometry, setHopGeometry] = useState<HopGeometryLookup | null>(null);
```

Replace the fetch effect (~36-42):

```ts
  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch(console.error);
    api.getCities().then(setCityGroups).catch(() => setCityGroups({}));
    api.getRailPaths()
      .then((r) => setHopGeometry(buildRailPathLookup(r.paths)))
      .catch(() => setHopGeometry(null)); // straight-line fallback, by design
  }, []);
```

with:

```ts
  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch(console.error);
    api.getCities().then(setCityGroups).catch(() => setCityGroups({}));
  }, []);
```

After the `stationsById` / `cities` memos (~lines 33-34), add:

```ts
  // Smoothed hop geometry (backlog I): derived from the FULL reach file so
  // the 1/2/3-trains and time filters hide lines but never reshape them.
  // Memoized per reach identity (useMemo here + WeakMap in smoothedLookupFor)
  // so filter/selection churn never recomputes. Never throws — a malformed
  // reach file degrades to straight lines.
  const hopGeometry = useMemo(
    () => (reach ? smoothedLookupFor(reach, stationsById) : null),
    [reach, stationsById],
  );
```

The `MapView` prop `hopGeometry={hopGeometry}` (renamed in Task 1) now receives the memo value — no further change on that line.

- [ ] **Step 5: Verify no stale references, run everything**

Run: `grep -rn "buildRailPathLookup" web/src`
Expected: no output.

Run: `cd web && npx tsc -b && npm test && npm run lint`
Expected: typecheck clean, all tests PASS, lint clean. (`api.getRailPaths` still exists but is now unused by the app — it is deleted with the endpoint in Task 4.)

- [ ] **Step 6: Commit**

```bash
git add web/src/App.tsx web/src/lib/geojson.ts web/src/lib/geojson.test.ts
git commit -m "feat(web): render smoothed hop curves instead of OSM rail paths (backlog I)

The lookup is computed client-side from the full reach file, memoized per
reach identity; the /api/rail-paths fetch is gone (one fewer page-load fetch,
1.17 MB gzipped). hopCoords straight-line fallback unchanged.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Delete the OSM paths subsystem (pipeline, artifact, server, client API, docs)

**Files:**
- Delete (git rm): `pipeline/railpaths.py`, `tests/test_railpaths.py`, `data/out/rail_paths.json`, `data/out/rail_paths.json.gz`
- Modify: `pipeline/cli.py` (STAGES, `_run_paths`, `_add_paths_args`, subparser)
- Modify: `tests/test_cli.py`
- Modify: `server/app.py:472-474` (endpoint)
- Modify: `tests/test_server.py` (fixture hunk, two tests, ARTIFACT_ENDPOINTS entry)
- Modify: `web/src/lib/api.ts` (`getRailPaths` + import), `web/src/lib/types.ts` (`RailPathsFile`)
- Modify: `pipeline/artifacts.py` (docstring), `tests/test_compute.py` (comment), `docs/data-sources.md`, `.gitignore`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure deletion — the web app stopped using `/api/rail-paths` in Task 3).
- Produces: `STAGES = ["fetch", "build", "compute"]` in `pipeline/cli.py` (`stages_from` behavior changes accordingly); no `/api/rail-paths` route; no `api.getRailPaths`; no `RailPathsFile` type. `shapely` stays in `pyproject.toml` (still used by `pipeline/coverage.py` — verified).

- [ ] **Step 1: Update `tests/test_cli.py` to the post-deletion stage list (failing first)**

Replace the entire contents of `tests/test_cli.py` with:

```python
"""Stage selection for `ose all --from <stage>`."""

import pytest

from pipeline.cli import stages_from


def test_default_start_runs_full_pipeline():
    assert stages_from("fetch") == ["fetch", "build", "compute"]


def test_mid_pipeline_start_runs_remaining_stages():
    assert stages_from("build") == ["build", "compute"]


def test_last_stage_runs_alone():
    assert stages_from("compute") == ["compute"]


def test_removed_paths_stage_rejected():
    # The OSM paths stage was deleted 2026-07-17 (smoothed line trees, backlog I).
    with pytest.raises(ValueError):
        stages_from("paths")


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        stages_from("frobnicate")
```

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `stages_from("fetch")` still returns `[..., "paths"]` and `stages_from("paths")` does not raise.

- [ ] **Step 2: Remove the `paths` stage from `pipeline/cli.py`**

Apply these exact edits:

Replace:

```python
STAGES = ["fetch", "build", "compute", "paths"]
```

with:

```python
STAGES = ["fetch", "build", "compute"]
```

Delete this function entirely:

```python
def _add_paths_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force-download", action="store_true",
                        help="re-download cached OSM extracts")
```

Delete this function entirely:

```python
def _run_paths(args: argparse.Namespace) -> None:
    from pipeline.railpaths import build_rail_paths

    build_rail_paths(OUT, Path("data/osm"), force_download=args.force_download)
```

Replace:

```python
_RUNNERS = {"fetch": _run_fetch, "build": _run_build, "compute": _run_compute, "paths": _run_paths}
```

with:

```python
_RUNNERS = {"fetch": _run_fetch, "build": _run_build, "compute": _run_compute}
```

Inside `main()`, delete these lines:

```python
    p = sub.add_parser("paths", help="derive real rail geometry for reach-line hops")
    _add_paths_args(p)
```

and delete this line (in the `all` subparser setup):

```python
    _add_paths_args(a)
```

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (5 tests).

- [ ] **Step 3: git rm the paths module, its tests, and the committed artifact**

```bash
git rm pipeline/railpaths.py tests/test_railpaths.py data/out/rail_paths.json data/out/rail_paths.json.gz
rm -rf data/osm
```

(`data/osm/` is the untracked OSM extract cache — the `rm -rf` only frees disk; if the directory doesn't exist that's fine.)

- [ ] **Step 4: Remove the server endpoint and its tests**

In `server/app.py`, delete (around line 472):

```python
    @app.get("/api/rail-paths")
    def rail_paths(request: Request) -> Response:
        return _artifact_response(request, data_dir / "rail_paths.json", 404, "No rail path data")
```

(leave one blank line between the `cities` endpoint and `return app`).

In `tests/test_server.py`:

Delete from the `client` fixture:

```python
    # rail_paths.json is written by a separate pipeline step (pipeline/railpaths.py,
    # not exercised by build()+compute_all()); hand-write it here so the
    # /api/rail-paths tests below have something to serve.
    write_json_with_gzip(out_dir / "rail_paths.json", json.dumps({
        "attribution": "© OpenStreetMap contributors (ODbL)",
        "paths": {"1111111|2222222": [[0.0, 0.0], [1.0, 1.0]]},
    }))
```

Delete both tests:

```python
def test_rail_paths_served(tmp_path):
    write_json_with_gzip(
        tmp_path / "rail_paths.json",
        '{"attribution": "© OpenStreetMap contributors (ODbL)", '
        '"paths": {"a|b": [[0, 0], [1, 1]]}}')
    client = TestClient(create_app(tmp_path))
    body = client.get("/api/rail-paths").json()
    assert body["paths"]["a|b"] == [[0, 0], [1, 1]]


def test_rail_paths_404_when_missing(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/rail-paths").status_code == 404
```

In the `ARTIFACT_ENDPOINTS` dict, delete the line:

```python
    "/api/rail-paths": "rail_paths.json",
```

(`write_json_with_gzip` and `json` imports stay — both still used elsewhere in the file: cities test at ~line 91 and stations tests.)

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS (rail-paths tests gone; parametrized artifact tests now cover coverage/cities/meta only).

- [ ] **Step 5: Remove the client API surface**

In `web/src/lib/api.ts`, replace line 1:

```ts
import type { CityGroups, CoverageCollection, RailPathsFile, ReachFile, Station } from "./types";
```

with:

```ts
import type { CityGroups, CoverageCollection, ReachFile, Station } from "./types";
```

and delete from the `api` object:

```ts
  getRailPaths: () => get<RailPathsFile>("/api/rail-paths"),
```

In `web/src/lib/types.ts`, delete:

```ts

export interface RailPathsFile {
  attribution: string;
  paths: Record<string, [number, number][]>;
}
```

(This also removes the never-rendered OSM attribution field — see the Codebase note in the header: no web component displayed it.)

Run: `cd web && npx tsc -b && npm test`
Expected: clean typecheck, all tests PASS.

- [ ] **Step 6: Docstring, comment, docs, gitignore cleanup**

In `pipeline/artifacts.py`, replace the docstring paragraph:

```python
Five endpoint families (`rail-paths`, `coverage`, `reach`, `cities`, `meta`)
are served verbatim by `server/app.py` -- byte-identical on every request, so
gzipping them once at pipeline-write time (instead of on every request) turns
~1.7s of server CPU per page view into a `sendfile`. The plain `.json` stays
the source of truth (other pipeline steps read it back, e.g.
`railpaths.collect_hops` globs `reach_*.json`); the `.json.gz` is purely a
serving optimisation.
```

with:

```python
Four endpoint families (`coverage`, `reach`, `cities`, `meta`) are served
verbatim by `server/app.py` -- byte-identical on every request, so gzipping
them once at pipeline-write time (instead of on every request) turns ~1.7s
of server CPU per page view into a `sendfile`. The plain `.json` stays the
source of truth; the `.json.gz` is purely a serving optimisation.
```

In `tests/test_compute.py` (~line 386), replace the comment line:

```python
    # rail-paths, coverage, reach, cities, meta are served verbatim by
```

with:

```python
    # coverage, reach, cities, meta are served verbatim by
```

In `docs/data-sources.md`:

Delete the table row:

```
| **OpenStreetMap** via Geofabrik per-country extracts | Real rail geometry (`ose paths` → `rail_paths.json`). Cached rail-only in `data/osm/` | ODbL — **attribution required**, rendered in the map's attribution control |
```

Replace:

```
Everything in `data/out/` (`stations.json`, `reach_*.json`, `cities.json`,
`coverage.json`, `rail_paths.json`) is **derived by our own pipeline**, not ingested.
```

with:

```
Everything in `data/out/` (`stations.json`, `reach_*.json`, `cities.json`,
`coverage.json`) is **derived by our own pipeline**, not ingested.
```

Delete this whole bullet (the paths inference no longer exists — reach lines are smoothed curves computed in the browser, not routed on track):

```
- **Which physical track a train actually uses.** Feeds give calling points, never
  track. `ose paths` *infers* the route (speed-weighted A* over OSM rail), which is
  right almost always but can pick a high-speed line where a slower service really
  takes the classic route. The legs' `dep`/`arr` times could disambiguate this and
  nobody has to give us the data — see the note in `pipeline/railpaths.py`.
```

In `.gitignore`, delete the line:

```
data/osm/
```

(No `justfile` change: its `pipeline` / `pipeline-from` recipes are stage-agnostic — verify with `grep -n paths justfile`, expected: no output.)

- [ ] **Step 7: Full python + web suites**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests PASS, ruff clean (in particular no unused-import errors in `tests/test_server.py` or `pipeline/cli.py`).

Run: `cd web && npx tsc -b && npm test && npm run lint`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat!: delete the OSM rail-paths subsystem (backlog I, retires AL)

Removes ose paths stage, pipeline/railpaths.py + tests, the committed
data/out/rail_paths.json(.gz) artifact, /api/rail-paths, getRailPaths and
RailPathsFile, the data/osm cache, and the docs' OSM-geometry row. Reach
lines are now smoothed client-side from the reach file.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Final verification sweep

**Files:**
- No planned modifications — fix-ups only if a check below fails.

**Interfaces:**
- Consumes: the finished state of Tasks 1-4 (smoothed lookup wired in; OSM subsystem gone).
- Produces: green suites and a leftover-reference audit.

- [ ] **Step 1: Full web verification**

Run: `cd web && npx tsc -b && npm test && npm run lint`
Expected: typecheck clean; every test file PASS, including `src/lib/smoothPaths.test.ts` and `src/lib/geojson.test.ts` (trunk-dedup, exact-vertex, and straight-line-fallback guards); oxlint clean.

- [ ] **Step 2: Full pipeline/server verification**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests PASS (no `tests/test_railpaths.py` collected); ruff clean.

- [ ] **Step 3: Leftover-reference audit**

Run:

```bash
grep -rn "railpaths\|rail_paths\|rail-paths\|RailPath\|getRailPaths\|buildRailPathLookup\|data/osm" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=data \
  --exclude-dir=__pycache__ .
```

Expected: hits ONLY under `docs/superpowers/` (the historical 2026-07-14 spec/plan, the 2026-07-17 spec, this plan, and `feedback-backlog.md` — backlog cleanup is a post-ship step, see below). Any hit in `pipeline/`, `server/`, `tests/`, `web/`, `justfile`, `.gitignore`, or `docs/data-sources.md` is a missed deletion: remove it and re-run Steps 1-2.

Also confirm the pipeline CLI rejects the removed stage:

Run: `uv run ose all --from paths`
Expected: exits non-zero with an argparse error (`invalid choice: 'paths'`).

- [ ] **Step 4: Commit (only if Step 3 required fix-ups)**

```bash
git add -A
git commit -m "chore: sweep leftover rail-paths references

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-ship follow-ups (NOT tasks in this plan — orchestrator/user, after visual review)

- End-to-end check via the `verify` skill (headless `window.__map` state queries, no screenshots): reach lines render as curves, straight fallback only for hops missing from `byId`.
- `CURVINESS` visual tuning is user-judged; it is the single knob in `web/src/lib/smoothPaths.ts`.
- Verify the rider's station-approach wobble (item AJ) is gone (smoothed curves have no stubs), then delete backlog items **I**, **AL**, and **AJ** from `docs/superpowers/feedback-backlog.md` (done items get deleted, not tombstoned), including item S's stale "`ose paths`" mention.
- Update memory/handover notes that call `rail_paths.json` a committed artifact and that mention `pipeline-from paths`.
- Deploy note: web and server must be deployed together (web stops fetching `/api/rail-paths` in the same release that removes the endpoint, so ordering is safe either way; the old committed artifact simply stops being served).
