# Smoothed line trees — design (item I, decided 2026-07-16)

**Decision:** replace the OSM-routed rail geometry (`ose paths` → `rail_paths.json`)
with client-side smoothed "subway map style" curves computed over the origin's hop
tree. Gentle geographic curves through the real station positions — NOT octilinear
schematic. The whole OSM paths pipeline stage and its committed artifact are
deleted (this also retires backlog item AL, the <5 GB RAM goal, and should retire
AJ, the rider swing on station-approach stubs).

## Why

The OSM-routed paths (shipped 2026-07-14) are not good enough: some hops fall back
to straight lines next to hops that follow track, and some route along the wrong
rails (subway/cargo tracks near Düsseldorf-Holthausen). Chasing per-corridor OSM
correctness is a treadmill. User verdict 2026-07-16: smoothed paths win.

## Architecture

One new pure module, one geometry-source swap, a pile of deletions.

### New module: `web/src/lib/smoothPaths.ts`

Pure functions, no map/React dependency. Input: the origin's full `ReachFile`
(ALL destinations' journeys, not the filtered subset) + the station lookup
(`byId`). Output: a lookup with the same shape `hopCoords` consumes today —
per-hop polylines keyed by the direction-normalized `segmentKey(a, b)`
(`"idA|idB"`, ids sorted).

Algorithm:

1. **Hop expansion.** For every journey, every train leg, expand
   `[leg.from, ...leg.via, leg.to]` into consecutive station-id pairs. Skip
   `type === "transfer"` legs. Accumulate a usage weight per hop (count of
   journeys using it).
2. **Hop graph.** Nodes = station ids, edges = unique hops with weights.
3. **Station tangents.** Each station gets exactly ONE tangent direction:
   - degree 1: the direction of its single hop;
   - degree ≥ 2: the dominant through-direction — over all pairs of incident
     hops, pick the pair maximizing `combined weight × alignment` (alignment =
     how close the pair is to passing straight through); the tangent is the
     normalized bisector of that pair (one direction flipped so they oppose).
   Coordinates come from station lat/lon; use a locally-scaled planar
   approximation (scale lon by cos(lat)) so directions are angle-true.
4. **Hop curves.** Each hop (a, b) becomes a cubic Bézier:
   `P0 = a`, `P3 = b`, `P1 = a + t_a · d`, `P2 = b − t_b · d`, where `t_a`/`t_b`
   are the station tangents sign-flipped to point along the travel direction
   a→b (positive dot with `b − a`), and `d = CURVINESS × hopLength`, capped
   (both as a fraction of hop length and an absolute km cap) so short hops in
   dense areas don't overshoot or self-intersect. `CURVINESS` is a single
   exported tunable constant (start ≈ 0.25).
5. **Sampling.** Sample each Bézier to a polyline — point count scaled by hop
   length with a minimum (~8) and maximum, endpoints EXACTLY the station
   coordinates. Dedupe consecutive identical points.

Consequences by construction:

- A hop shared by many journeys has exactly one geometry → trunks stay merged
  (preserves the item-X dedup guarantee; no trunk splay).
- A line passing through a station enters and leaves along the same tangent →
  no kink at served stops.
- Branches leave a trunk along the shared tangent, then bend away — the
  subway-map feel.
- Two-point hops between degree-1 stations degenerate to straight lines.
- Served stops are exact polyline vertices (rider + dedup invariant kept).

### Integration (geometry-source swap)

- `web/src/App.tsx`: delete the `/api/rail-paths` fetch. Instead, when a reach
  file loads, compute the smoothed lookup once (memoized on the reach file
  identity) and pass it down where `railPaths` went.
- `web/src/lib/geojson.ts`: `hopCoords`, `legSegments`, `journeyLegPaths`,
  `segmentsGeoJSON`, `linesGeoJSON`, `selectedLineGeoJSON` keep their logic;
  the lookup parameter keeps its semantics; `buildRailPathLookup` (OSM JSON →
  lookup) is deleted and `smoothPaths.ts` provides the lookup builder instead.
  The straight-line fallback in `hopCoords` stays: a hop absent from the
  lookup renders as a straight line (safety net only; the smoother covers
  every train hop in the reach file).
- `web/src/lib/ride.ts` (rider) is untouched — it consumes `journeyLegPaths`
  output. Expected side effect: station-approach stub wobble (item AJ)
  disappears because smoothed curves have no stubs; verify, then delete AJ.
- **Stability rule:** tangents/geometry derive from the FULL reach file, never
  from the currently filtered/shown subset — the 1/2/3-trains selector and
  other filters hide lines but never reshape them.

### Deletions

- `pipeline/railpaths.py`, `tests/test_railpaths.py`.
- `paths` stage: `pipeline/cli.py` `STAGES` + `_run_paths`; justfile mentions
  (`pipeline-from paths`); `data/osm/` cache handling.
- Committed artifacts `data/out/rail_paths.json` + `.gz` (git rm).
- `server/app.py` `/api/rail-paths` endpoint.
- `web/src/lib/api.ts` `getRailPaths`; `RailPathsFile` type in
  `web/src/lib/types.ts`.
- OSM rail-paths attribution wherever it is displayed.
- Backlog after ship: delete items I and AL; verify and delete AJ; update the
  memory/handover notes that call `rail_paths.json` a committed artifact.

## Error handling

- Empty/malformed reach file → empty lookup → all hops straight lines (same
  degraded rendering as today's missing-OSM fallback). Never throw during
  rendering.
- Stations missing from `byId` (stale reach file vs stations.json) → skip that
  hop in the tree; it falls back to a straight line at render.
- Zero-length hops (duplicate consecutive stops) → dropped after dedupe.

## Performance

A reach file today yields ~4k unique hops across all origins; a single origin
is far smaller. Graph build + tangents + sampling is O(hops) with tiny
constants — target <10 ms; memoize per reach file so filter/selection churn
never recomputes. No new network requests; page load LOSES one fetch
(rail-paths, 1.17 MB gzipped).

## Testing

Vitest units for `smoothPaths.ts`:

- shared hop → identical geometry regardless of journey iteration order;
- station coordinates are exact curve endpoints (first/last vertex);
- through-station continuity: entering/leaving segments at a degree-2 station
  are collinear at the station (within tolerance);
- isolated two-point hop → straight line;
- geometry computed from a filtered subset is NOT used: lookup built from the
  full reach file equals the one used with filters active;
- transfer legs contribute no hops;
- missing station in `byId` → hop absent from lookup (falls back straight).

Update `web/src/lib/geojson.test.ts` for the lookup swap (existing trunk-dedup
and exact-vertex tests keep passing — they are the invariant guard). Delete
`tests/test_railpaths.py`. Pipeline CLI tests updated for the removed stage.
End-to-end via the `verify` skill (headless `window.__map` state queries, no
screenshots); visual curviness tuning (`CURVINESS`) is user-judged afterwards.

## Out of scope

- Octilinear/schematic geometry, station displacement.
- Any change to reach-file schema, RAPTOR, or the server (beyond deleting the
  endpoint).
- Parallel-line offsetting where distinct routes share a corridor (future
  polish if wanted).
