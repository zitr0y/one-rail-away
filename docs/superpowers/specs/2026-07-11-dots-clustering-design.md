# Dots & Clustering (backlog C1+C2): Sized Dots, Capital Stars, Cluster Pick-List

Date: 2026-07-11
Status: approved
Context: backlog item C, sliced C1+C2 now; C3 (city union entity) gets its own
brainstorm later. 1651 reach stations render as identical 3px dots today —
hard to click, no hierarchy. Wien-vs-Wiener-Neustadt shows name matching is
unsafe; capitals are hand-curated.

## Design

### 1. Pipeline: `n_dest` + `is_capital` on stations

- `compute_all` already knows each origin's destination count
  (`results[station.id]`); it now writes it as `n_dest: int` (0 when no reach)
  on every station in `data/out/stations.json`. `Station` model gains the
  field (default 0); the server passes it through via `model_dump`.
- New curated file `capitals.toml` (repo root, next to `station_aliases.toml`):
  `[capitals]` table mapping ISO country → exact canonical station name, e.g.
  `DE = "Berlin Hbf"`, `FR = "Paris Gare du Nord"`, `AT = "Wien Hbf"`,
  `NL = "Amsterdam Centraal"`, `ES = "Madrid-Puerta de Atocha-Almudena Grandes"`,
  `PL = "Warszawa Centralna"`, `CH = "Bern"`, `BE = "Bruxelles Midi"`,
  `CZ = "Praha hl.n."` — seed with stations that exist in the current build;
  the user edits taste later. Compute flags matching stations
  `is_capital: true` (match on exact name AND country); an entry that matches
  no station logs a warning and is skipped (never fails the build).

### 2. Frontend: sized dots

- Grey `all-stations` layer: data-driven `circle-radius` — sqrt scale from
  2.5px (n_dest 0) to 8px, clamped at n_dest 400. Expression built by a pure
  helper in new `web/src/lib/dots.ts` (`dotRadiusExpression()`), unit-tested.
- Colored `reach-dots` stay fixed-size (color encodes time; size stays quiet).

### 3. Frontend: capital stars

- Capitals are excluded from the `all-stations` source and rendered on a new
  `capital-stars` symbol layer fed by a `capitals` GeoJSON source; the icon is
  a 5-point star generated on a canvas at startup and registered with
  `map.addImage` (no dependency on the style's glyph ranges). Fixed size
  (~15px), grey fill matching the dot palette, subtle white outline.
- Stars are never clustered and always visible.
- Clicking a star selects that station as origin. `pickfeature.ts` precedence
  becomes: `reach-dots` (dest) > `capital-stars` (origin) > `all-stations`
  (origin). When a reach is active the capital ALSO appears as a colored
  destination dot on top if reachable — that dot wins the click, as today.

### 4. Frontend: clustering with pick-list

- The `all-stations` source enables MapLibre native clustering:
  `clusterRadius: 30` (tight — only genuine bunches merge),
  `clusterMaxZoom: 7` (fully dissolved above ~z7.5).
- Two new layers: `station-clusters` (grey bubble, radius scaled by
  `point_count`) and `station-cluster-count` (symbol label,
  `point_count_abbreviated`).
- Click a bubble → `getClusterLeaves(cluster_id, 25)` → MapLibre popup
  (`setDOMContent`) listing member station names sorted by `n_dest`
  descending — sorting by a pure helper `sortForClusterList(stations)` in
  `dots.ts`. Clicking a name calls `onSelectOrigin(id)` and closes the popup.
- Cluster hits are handled in the click handler BEFORE `pickFeature`, so a
  cluster click never falls through to origin-pick or empty-click. Empty-click
  behavior (2026-07-11-selection-ux spec) is otherwise unchanged.
- `reach-dots` are never clustered — the reach fan stays intact at all zooms.

### 5. Testing

- `dots.ts` unit tests: radius expression bounds (2.5 at 0, 8 at ≥400,
  monotonic), `sortForClusterList` ordering + tie behavior.
- `pickfeature.test.ts`: capital-stars precedence cases.
- Pipeline tests: `n_dest` present and equal to the fixture origin's
  destination count; `is_capital` set for a fixture capitals.toml entry and
  warning (not failure) for an unmatched entry.
- Server test: stations endpoint passes `n_dest`/`is_capital` through.
- Visual verification is the user's (no screenshot checks).

## Iteration 2 (2026-07-11 live-test feedback)

1. **Clustering removed.** At the default zoom nearly everything merged into
   uniform bubbles (headless check: 102 bubbles vs 10 raw dots) and the density
   picture died. §4 shipped and was reverted; sized dots + stars stay. If tiny
   stations need decluttering later, revisit inside C3 (city grouping).
2. **Stars enlarged/darkened.** They rendered but were imperceptible (7.5px,
   same grey as dots). Now 44px asset at icon-size 0.8 (~17.6px), fill #4b5563.
3. **addImage regression note:** a canvas element is not a valid addImage
   argument; drawStarIcon returns {width, height, data} rasterized in pure
   math (no DOM), with pixel-level tests.

## Out of scope

- C3 city-union entity (own brainstorm next).
- Sizing/clustering of colored destination dots.
- Star styling refinements — revisit with branding (backlog D).
