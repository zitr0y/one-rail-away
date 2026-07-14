# Real rail geometry for reach lines + target-chooser fix (items I + AE)

Date: 2026-07-14. Status: approved by user (brainstorm session 2026-07-14).

Two changes shipped together to make the map presentable for a first public
feedback round:

- **Item I:** reach lines follow real railway tracks (OSM geometry) instead of
  straight lines / four curated French corridors. Also covers the 2026-07-14
  "paths not showing" report — the base segments layer is rewired and its data
  regenerated, verified end-to-end.
- **Item AE:** the click-disambiguation popup no longer changes the ORIGIN when
  the user is picking a TARGET; target-mode gets its own ranking.

## Decisions made with the user

- OSM ingest weight is acceptable: per-country Geofabrik extracts, a few GB,
  cached, refreshed rarely.
- Routing cost is **speed-weighted** (length ÷ maxspeed), so high-speed hops
  prefer LGV/NBS tracks over parallel classic lines.
- Target chooser shows unreachable stations **last, muted, still clickable**
  (not hidden).
- Curated `corridors.ts` is retired (deleted) once real geometry lands.

## Background / measured scale

- The full dataset is local: 2,637 `data/out/reach_*.json` files containing
  **4,332 unique physical hops** (direction-normalized station pairs from leg
  `from`/`via`/`to` chains; nonstop legs contribute their from→to pair).
- `web/src/lib/geojson.ts` already dedupes drawing by `segmentKey(a, b)`
  (item X). That key is the attachment point for real geometry.
- The mascot rider shares `journeyLegPaths`, so it follows real track for free.
- AE root cause: in `web/src/components/Map.tsx::showOverlapChoice`, the
  "(all stations)" button unconditionally calls `onSelectCityOrigin`, ignoring
  `armed === "to"`. Individual stations route correctly via `selectStation`.

## 1. Pipeline stage `ose paths` (new module `pipeline/railpaths.py`)

Runs after compute/build, reads `data/out/stations.json` +
`data/out/reach_*.json`, writes `data/out/rail_paths.json`.

1. **Hop collection:** walk every journey leg of every reach file; for each
   consecutive stop pair (and each nonstop leg's from→to) record the
   direction-normalized pair key `idA|idB` (lexicographic, matching the web's
   `segmentKey`). ~4.3k unique hops today.
2. **OSM source:** Geofabrik per-country `.osm.pbf` extracts for the union of
   countries appearing in `stations.json` (includes leak countries). Cached
   under `data/osm/`; re-download only on explicit force flag. Each extract is
   filtered to `railway=rail` ways (osmium tags-filter), then merged. Filtered
   rail-only files are ~50–150 MB per country.
3. **Graph build (pyosmium):** nodes/edges from filtered ways; chains of
   degree-2 nodes contracted into single edges carrying their full polyline.
   Edge cost = geodesic length ÷ maxspeed; maxspeed parsed from tags, default
   100 km/h where missing/unparseable, capped at sane bounds.
4. **Station snapping:** each station snaps to the nearest graph vertex within
   ~1 km of its coordinates. Unsnappable stations go to the report (below).
5. **Routing:** per hop, A* over the contracted graph with an admissible
   heuristic (geodesic distance ÷ maximum network speed). Unroutable pairs
   (disconnected components, snap failures) go to the report.
6. **Output** `data/out/rail_paths.json`:

   ```json
   {
     "attribution": "© OpenStreetMap contributors (ODbL)",
     "paths": { "x:db_fern:8000105|x:db_fern:8000191": [[lon, lat], ...] }
   }
   ```

   Coordinates rounded to 5 decimals, Douglas-Peucker simplified (~30 m
   tolerance — TUNING POINT). Expected low single-digit MB, gzip-served. If it
   measures fat, switch values to encoded polylines — decide in the plan by
   measurement.

## 2. Error handling / observability (AC/Q spirit)

- Unsnappable stations and unroutable hops are **omitted** from
  `rail_paths.json` and written with reasons to
  `data/out/rail_paths_report.json` (a seed of backlog item Q). The web draws
  those hops as straight lines, as today.
- A missing or failed `rail_paths.json` fetch degrades to straight lines
  everywhere — never a blank map, never a blocked initial render.
- ODbL: the attribution string ships in the file; the site already renders OSM
  attribution via the basemap. Verify the line covers "© OpenStreetMap
  contributors" on screen.

## 3. Web rendering changes (`web/src/lib/geojson.ts` and friends)

- `legSegments` (and through it `segmentsGeoJSON` / `journeyLegPaths` /
  `linesGeoJSON`) takes a `railPaths` lookup
  (`Map<string, [number, number][]> | null`):
  - geometry present → use it, reversed when needed so it runs in the hop's
    travel direction (match by endpoint proximity to the from-station);
  - absent → today's straight line between the two stops.
- **Chaikin smoothing and `corridors.ts` (+ its tests) are deleted.** Real
  geometry needs no smoothing; served stops stay exact vertices.
- `rail_paths.json` is fetched once alongside initial data (server serves it
  like the other `data/out` artifacts); rendering does not wait on it — lines
  pick up real geometry when the lookup arrives.
- Rider (`ride.ts`) needs no change: it consumes `journeyLegPaths`.

## 4. AE — target-chooser fix (`web/src/lib/overlap.ts`, `web/src/components/Map.tsx`)

- **Origin mode (`armed !== "to"`): unchanged** — bold "City (all stations)"
  entries first, stations by connection count (b43faec behavior).
- **Target mode (`armed === "to"`):**
  - **No city "(all stations)" entries at all** (this removes the bug's trigger;
    no re-wiring of city-union targeting).
  - Station order: reachable first, by **fewest trains from the current origin
    under the active trains/time filters**, then connection count (desc), then
    name, then id. Unreachable stations sort last, get a muted style and a
    "not reachable" hint, and remain clickable (selecting shows the normal
    no-route state).
- Ordering/labeling logic lives as pure functions in `overlap.ts` (mode-aware),
  unit-testable; `Map.tsx` supplies a `destId → min trains` map derived from
  the loaded reach file plus current filter values.
- The single-station city popup in `selectStation` already bypasses city
  selection in target mode — no change there.

## 5. Testing

- **Pipeline:** synthetic mini-OSM fixture — a toy network with a slow classic
  line and a fast bypass between the same endpoints — asserting: speed-weighted
  routing picks the bypass, degree-2 contraction preserves polylines, snapping
  radius honored, Douglas-Peucker output stable, report emitted for an
  unroutable pair. **No live station ids anywhere in tests** (AD spirit).
- **Web:** geometry lookup / orientation / straight-line fallback tests for
  `legSegments`; AE ordering tests (both modes, unreachable-last, tie-breaks).
- Full suites (pytest, vitest) + web build green.
- **End-to-end:** run `ose paths` on the real data, serve, user eyeballs the
  map — paths visible, track-following, rider on track. This closes the
  2026-07-14 "paths not showing" report or surfaces its real cause.

## Out of scope

- Fake intra-city transfer edges (item U), id-churn hardening (AD/AC),
  density-aware declutter, hover previews.
- Perfect track-level fidelity (platform-level routing, direction of switch
  legs). The bar: lines visibly follow railways at the zooms people browse.
