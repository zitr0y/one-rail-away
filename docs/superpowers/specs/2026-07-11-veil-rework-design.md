# Veil Rework: World-Wide Dissolved Coverage Veil

Date: 2026-07-11
Status: approved
Supersedes: 2026-07-11-country-greying-design.md (§3 copy and veil architecture)

## Problem

User feedback on the merged country-greying feature (live test 2026-07-11):

1. Only a 42-country Europe subset is veiled. Isle of Man, India — any land
   outside the subset — renders unveiled. The logic must invert: *all* land is
   veiled except covered countries. Ocean stays untouched.
2. The Natural Earth 1:50M borders (coords rounded to ~110 m) visibly mismatch
   the OSM borders drawn by the OpenFreeMap Positron basemap.
3. The feature over-explains itself. The legend line goes; the hover tooltip
   becomes the only explanation, with copy about international reachability.

Decisions made with user: NE 1:10M data plus a softened (blurred) veil edge —
not exact OSM boundaries (PMTiles pipeline rejected as ~10x effort). Tooltip is
generic, no country name.

## Design

### 1. New world asset (one-off, committed)

`pipeline/assets/countries_world_10m.geojson`, built one-off with
`npx mapshaper` from `ne_10m_admin_0_countries.geojson` (Natural Earth, public
domain). The exact download URL and mapshaper command are recorded in the
`pipeline/coverage.py` module docstring (same provenance pattern as `geo.py`):

- properties reduced to `ISO_A2_EH`
- simplified to 40% retention (visvalingam, keep-shapes) — clean at z4–8
- coordinates rounded to 4 decimals (~11 m, well inside 1:10M accuracy)
- target size ≤ ~5 MB committed

The existing `countries_europe_50m.geojson` stays untouched — `geo.py`
station→country assignment keeps using it. Two assets, two jobs.

### 2. Pipeline: dissolved veil geometry

`pipeline/coverage.py` reworked:

- `covered_from_feeds(feeds_path)` — unchanged.
- `build_coverage(covered, asset_path)` — loads the world asset, selects
  features whose ISO code is NOT in `covered`, unions them with shapely
  `unary_union`, and returns a FeatureCollection containing **one Feature**
  (MultiPolygon, empty properties).
- `COUNTRY_NAMES` deleted (generic tooltip needs no names).
- New dependency: `shapely` (pipeline). Union of ~250 simplified features runs
  in seconds at compute time.

The veil is the union of country land polygons only, so ocean is never veiled.
Every country on Earth absent from feeds.toml is veiled, including
dependencies (Isle of Man etc. are separate NE admin-0 features).

`ose compute` still writes `data/out/coverage.json`; `GET /api/coverage`
(server/app.py) is unchanged.

### 3. Frontend: fill + feathered edge, tooltip-only copy

`web/src/components/Map.tsx`:

- `coverage-veil` fill layer: drop the `covered == false` filter (the source
  now contains only veil geometry). Paint stays `#6b7280` at 0.25 opacity.
- New `coverage-veil-edge` line layer, same source, inserted with the fill:
  `line-color #6b7280`, `line-width ~2.5`, `line-blur ~3`, `line-opacity ~0.2`.
  Because the geometry is dissolved, edges exist only where veil meets covered
  countries or coastline — a blurred edge there reads as intentional feathering
  and hides residual NE-vs-OSM offsets. (This is why per-country features were
  rejected: line-blur would paint fuzzy artifacts along every internal border
  between two veiled countries.)

`web/src/lib/coverage.ts`:

- `VEIL_LEGEND` deleted; Legend.tsx drops the veil entry (tooltip is the only
  explanation).
- `veilFilter()` deleted.
- `coverageTooltip(name)` replaced by an exported constant `VEIL_TOOLTIP`:
  "May be reachable by international trains from other countries, but we don't
  yet have data from this country's rail providers."
- `showVeilTooltip(stationHitCount)` (station-hover precedence) — unchanged.

### 4. Testing

- `web/src/lib/coverage.test.ts`: tooltip constant asserted; filter tests
  removed; precedence tests unchanged.
- Pipeline tests: `build_coverage` output is a single-feature FeatureCollection;
  a point inside a covered country (e.g. Germany) falls outside the veil
  geometry, a point inside a non-covered country (e.g. Italy) falls inside;
  ocean point falls outside.
- Visual verification is the user's (no screenshot-based checks).

## Out of scope

- Exact OSM boundary matching (PMTiles) — revisit only if 10m + feathering
  still looks wrong.
- Any change to station→country assignment (keeps 50m Europe asset).
