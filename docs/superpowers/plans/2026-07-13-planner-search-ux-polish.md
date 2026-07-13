# Planner and Search UX Polish Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` or the repository's equivalent task runner to implement this plan one step at a time. Track the checkbox items, keep every RED/GREEN sequence in order, and commit only the files named by the current step.

**Goal:** Polish four independent planner interactions: promote the selected destination when From is cleared, broaden curated station-search exonyms and relabel city options, show transfer rings on the selected route, and offer station-versus-city origin selection from grouped map dots.

**Architecture:** Keep decisions in the existing pure helper modules and side effects in their current owners. `selection.ts`, `geojson.ts`, and `cities.ts` gain one helper each; `server.app.EXONYMS` remains static query expansion; `App.tsx` owns planner state and city-union loading; `Map.tsx` owns MapLibre sources, layers, rider-adjacent synchronization, and popup lifecycle. No endpoint, pipeline, data shape, reachability, selection-filter, click-precedence, or theme-system redesign is included.

**Tech stack:** Python 3.14, FastAPI, pytest, uv; React, TypeScript, Vite, Vitest, oxlint; MapLibre GL.

## Global constraints

- Implement in this exact unit order: **Unit 1 → Unit 3 → Unit 2 → Unit 4**.
- Treat every unit as independently implementable and revertible. A unit may use existing repository code, but must not consume code introduced by another unit in this plan.
- Follow TDD for `clearOriginAction`, the `EXONYMS` changes, the `cityOptions` label, `transferPoints`, theme-token/style-swap changes, and `cityForStation`: add the named test first, run it and observe the specified failure, implement only that behavior, then rerun the focused and relevant full suites.
- Do not add runtime dependencies, change API or persisted data shapes, recompute pipeline output, alter normalization/ranking/reach-file filtering, or refactor unrelated code.
- Preserve `maxTrains` and `maxMinutes` across selection changes in Unit 1.
- Preserve `CLICK_LAYERS`, `routeMapClick`, `armedTarget`, and To-armed behavior. Transfer rings are non-interactive; city-union choice is From-only.
- Styling in Units 2 and 4 is a tuning point. Automated verification proves structure and behavior; the user performs browser visual calibration.
- Stage only files listed in the current step. Before each commit, inspect `git diff --check` and `git status --short` so unrelated user changes remain untouched.

## File map

| Unit | File | Responsibility |
|---|---|---|
| 1 | `web/src/lib/selection.ts` / `.test.ts` | Pure clear-origin decision truth table. |
| 1 | `web/src/App.tsx` | Promotion fetch and planner callback wiring. |
| 3 | `server/app.py` | Curated, evidence-backed exonym query mappings. |
| 3 | `tests/test_search.py` | Search fixture and exonym expansion regressions. |
| 3 | `web/src/lib/planner.ts` / `.test.ts` | Exact grouped-city option label. |
| 2 | `web/src/lib/geojson.ts` / `.test.ts` | Journey-boundary coordinate extraction. |
| 2 | `web/src/lib/colors.ts` / `.test.ts` | Per-theme transfer-ring token. |
| 2 | `web/src/lib/themeswap.ts` / `.test.ts` | Preserve/re-tint the transfer source and layer. |
| 2 | `web/src/components/Map.tsx` | Transfer source, layer, filter synchronization, and final layer order. |
| 4 | `web/src/lib/cities.ts` / `.test.ts` | Pure grouped-city popup eligibility. |
| 4 | `web/src/App.tsx` | Pass city groups, resolved armed target, and existing city-origin callback. |
| 4 | `web/src/components/Map.tsx` | From-only semantic popup creation and lifecycle. |
| 4 | `web/src/index.css` | Compact theme-aware popup and button styling. |

---

## Unit 1 — Promote destination when From is cleared (2 steps)

This unit depends only on existing `selectedDest`, `clearSelection`, `api.getReach`, `swapSelection`, and `JourneyPlanner.onClearOrigin`. It must be revertible without affecting Units 2–4.

### Step 1.1: Add `clearOriginAction` with its full truth table

**Files:**

- Modify: `web/src/lib/selection.test.ts`
- Modify: `web/src/lib/selection.ts`

**Interface:** `clearOriginAction(selectedDest: string | null): { promote: string } | { clearAll: true }`

- [ ] Add a `clearOriginAction` test group to `selection.test.ts` before changing the helper module. Assert a normal station id such as `"station-b"` returns `{ promote: "station-b" }`.
- [ ] Assert `null` returns `{ clearAll: true }`.
- [ ] Lock the documented null-only semantics by asserting `""` returns `{ promote: "" }`; do not use truthiness to decide absence.
- [ ] Run `cd web && npx vitest run src/lib/selection.test.ts` and confirm RED because `clearOriginAction` is not exported.
- [ ] Add the pure helper beside `emptyClickAction` and `swapDest`. It must inspect only `selectedDest`, return the exact discriminated union above, and have no React, reach-file, or city-origin knowledge.
- [ ] Rerun `cd web && npx vitest run src/lib/selection.test.ts` and confirm all selection helper tests pass.
- [ ] Run `cd web && npm test` and `cd web && npm run lint && npm run build`.
- [ ] Commit only the two selection files with a focused message such as `feat: decide clear-origin promotion`.

### Step 1.2: Wire destination promotion into `App`

**Files:**

- Modify: `web/src/App.tsx`

**Existing seams:** `clearSelection`, `swapSelection`, `api.getReach`, `setCityOrigin`, `setSelectedDest`, `setHint`, `setActiveField`, `setReach`, and `JourneyPlanner.onClearOrigin`.

- [ ] Import `clearOriginAction` alongside the existing selection helpers and add an App-level `onClearOrigin` callback.
- [ ] In the `{ clearAll: true }` branch, call the existing `clearSelection()` unchanged. This preserves the current no-destination behavior: clear city origin, reach, destination, hint, and armed field.
- [ ] In the promotion branch, capture the destination id, clear `cityOrigin`, `selectedDest`, and `hint` immediately, set/keep `activeField` to `"to"`, then call `api.getReach(promoteId)` and install the successful result with `setReach`.
- [ ] Use the existing fetch error behavior, `setError(String(e))`. Do not roll back, invent a loading state, restore the cleared destination, or clear the old reach while the request is pending.
- [ ] Do not call `swapDest`, preserve the old origin as a destination, or reset `maxTrains`/`maxMinutes`. A promoted city-union destination is always one ordinary station reach file because `cityOrigin` is cleared.
- [ ] Pass the new callback to `JourneyPlanner.onClearOrigin` instead of `clearSelection`; do not change `JourneyPlanner.tsx` or `StationField.tsx` props or rendering.
- [ ] Run `cd web && npx vitest run src/lib/selection.test.ts`.
- [ ] Run `cd web && npm test`.
- [ ] Run `cd web && npm run lint && npm run build`; the build is the prop/type integration check.
- [ ] Browser behavior for the implementer to exercise, without claiming visual acceptance: A → B then clear From promotes B, blanks To, loads B's fan, and leaves To armed; origin-only clear retains full-clear behavior; city-union origin → station destination promotes a plain station origin.
- [ ] Commit only `web/src/App.tsx` with a focused message such as `feat: promote destination when clearing origin`.

---

## Unit 3 — Curated station-search exonyms and city-option relabel (3 steps)

This unit depends only on the existing server query-expansion seam and `cityOptions`; it must not import or consume Unit 1 code. Search response shape, ranking, limit, normalization, and on-disk reach filtering remain unchanged.

### Step 3.1: Extend exonym search coverage tests first, then add the curated mappings

**Files:**

- Modify: `tests/test_search.py`
- Modify: `server/app.py`

**Existing seams:** `_exonym_client`, `_ids`, `normalize`, `_query_variants`, `EXONYMS`, and `/api/stations/search`.

- [ ] Extend `_exonym_client` before changing `EXONYMS`. Add reachable fixture stations and matching `reach_*.json` files for exact representative native names/ids covering Roma, København, Den Haag, București, and Łódź. Keep the existing Praha, Köln, Barcelona, and Wien fixture data.
- [ ] Add a parameterized full-query test proving `rome`, `copenhagen`, `the hague`, `bucharest`, and `lodz` resolve to their intended fixture ids. This covers common English input, a multiword key, a normalized diacritic target, and stroke characters retained by `normalize()`.
- [ ] Add a concrete type-ahead assertion that partial `copen` already resolves to København.
- [ ] Extend the native-name regression test to query the representative native forms directly and prove expansion augments rather than replaces the original query variant.
- [ ] Run `uv run pytest tests/test_search.py -q` and confirm the new exonym assertions are RED while existing native/exonym tests remain diagnostic.
- [ ] Extend only `server.app.EXONYMS`; do not modify `normalize`, `_query_variants`, endpoint logic, scoring, limit, or reach-file filtering.
- [ ] Add the approved 35 key/target pairs, subject to Step 3.2's real-data gate: `rome`→`roma`, `antwerp`→`antwerpen`, `the hague`→`den haag`, `copenhagen`→`københavn`, `lyons`→`lyon`, `marseilles`→`marseille`, `seville`→`sevilla`, `aix-la-chapelle`→`aachen`, `ratisbon`→`regensburg`, `brunswick`→`braunschweig`, `hanover`→`hannover`, `coblenz`→`koblenz`, `mayence`→`mainz`, `francfort`→`frankfurt`, `strassburg`→`strasbourg`, `bale`→`basel`, `lucerne`→`luzern`, `berne`→`bern`, `bucharest`→`bucuresti`, `danzig`→`gdansk`, `breslau`→`wroclaw`, `stettin`→`szczecin`, `posen`→`poznan`, `cracow`→`krakow`, `lodz`→`łodz`, `saragossa`→`zaragoza`, `gerona`→`girona`, `lerida`→`lleida`, `corunna`→`a coruna`, `bois-le-duc`→`s-hertogenbosch`, `flushing`→`vlissingen`, `pressburg`→`bratislava`, `lemberg`→`lviv`, `zagabria`→`zagreb`, and `fiume`→`rijeka`.
- [ ] Do not add Florence/Firenze, Naples/Napoli, Turin/Torino, Lisbon/Lisboa, Gothenburg/Goteborg, Athens/Athina, Bruges/Brugge, or Pilsen/Plzen. Their native targets do not match intended stations in the current output; revisit only after a future build contains them.
- [ ] Rerun `uv run pytest tests/test_search.py -q` and confirm the full-query, partial-prefix, multiword, non-ASCII/stroke-target, and native-name cases pass.
- [ ] Leave the evidence comment provisional until Step 3.2; do not commit the server changes yet.

### Step 3.2: Verify every exonym target against real data and finalize the evidence comment

**Files:**

- Modify: `server/app.py`

**Review boundary:** This is the explicit real-data evidence step. It finalizes only curated data/commentary and can be reviewed separately from search mechanics.

- [ ] With all proposed mappings present, run this exact snippet from the repository root:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from server.app import EXONYMS, normalize

stations = json.loads(
    Path("data/out/stations.json").read_text(encoding="utf-8")
)["stations"]
normalized = [(station["name"], normalize(station["name"])) for station in stations]

missing = []
for native in sorted(set(EXONYMS.values())):
    matches = [name for name, folded in normalized if native in folded]
    print(f"{native}={len(matches)}: {matches}")
    if not matches:
        missing.append(native)

if missing:
    raise SystemExit(f"DROP unmatched EXONYMS targets: {missing}")
print(f"verified against {len(stations)} stations")
PY
```

- [ ] Inspect the printed station names, not only counts, and confirm each substring represents the intended city rather than only an incidental match. Incidental extra matches such as `roma` in Romanshorn are acceptable only when the intended Roma station is also present; do not change existing prefix-first/shorter-name ranking.
- [ ] Drop every new key whose target has zero matches or whose output contains no intended city station. Never retain an unmatched target to satisfy a fixture.
- [ ] Include every approved modern exonym whose native target genuinely exists. Historical approved entries may remain only when their native target matches a real intended station; add no speculative historical extras.
- [ ] Refresh the `EXONYMS` evidence comment with the snippet's current station total and fresh match count for every unique target. The checked-in snapshot was 1,725 stations during planning, but the implementation-time output is authoritative.
- [ ] Rerun the exact snippet and require exit 0 after all drops/comment updates.
- [ ] Run `uv run pytest tests/test_search.py tests/test_international.py -q`; `test_exonym_targets_exist` must remain green when real output is available.
- [ ] Run `uv run pytest` to catch any server or pipeline regressions.
- [ ] Run `git diff --check`, review that only query data/evidence and the intended search tests changed, then commit `server/app.py` and `tests/test_search.py` with a focused message such as `feat: expand verified station exonyms`.

### Step 3.3: Relabel grouped-city planner options with an exact-output TDD cycle

**Files:**

- Modify: `web/src/lib/planner.test.ts`
- Modify: `web/src/lib/planner.ts`

- [ ] Change the existing `cityOptions` exact-object assertion first from `label: "Paris — all stations"` to `label: "Paris (All stations)"`. Do not weaken it to a partial match.
- [ ] Run `cd web && npx vitest run src/lib/planner.test.ts` and confirm RED with the old exact label.
- [ ] Change only the `cityOptions` label template to produce `<City> (All stations)`. Do not expand `CITY_EXONYMS`, alter matching, sorting, member ids, option kinds, or any other planner copy.
- [ ] Rerun `cd web && npx vitest run src/lib/planner.test.ts` and confirm GREEN, including existing city-exonym tests.
- [ ] Run `cd web && npm test` and `cd web && npm run lint && npm run build`.
- [ ] Commit only the planner helper and test with a focused message such as `fix: relabel all-stations city options`.

---

## Unit 2 — Mark transfers on the selected route (4 steps)

This unit depends only on existing journey/station types, `bestJourney`, MapLibre style lifecycle, and map props. It must not consume Unit 1 or Unit 3 code. Transfer markers describe only the selected eligible journey.

### Step 2.1: Add `transferPoints` with journey-boundary tests first

**Files:**

- Modify: `web/src/lib/geojson.test.ts`
- Modify: `web/src/lib/geojson.ts`

**Interface:** `transferPoints(journey: Journey, stationsById: Map<string, Station>): [number, number][]`

- [ ] Import `transferPoints` in `geojson.test.ts` and add a dedicated test group before implementing it.
- [ ] Add the exact one-leg case and assert `[]`, even when that leg contains a `via` station.
- [ ] Add the exact two-leg case and assert one `[lon, lat]` coordinate for the first leg's `to` station.
- [ ] Add the exact three-leg case and assert two coordinates in journey order, from the first and second legs' `to` stations.
- [ ] Add a missing-boundary-station case and assert the missing coordinate is omitted without throwing while later valid boundaries retain order.
- [ ] Add an explicit `via` regression assertion proving through stops are never emitted as transfer points.
- [ ] Run `cd web && npx vitest run src/lib/geojson.test.ts` and confirm RED because `transferPoints` is missing.
- [ ] Implement the pure helper beside the existing GeoJSON builders: inspect every non-final leg, look up `leg.to`, return station `[lon, lat]`, omit missing ids, preserve order and repeated boundaries, and perform no journey/filter selection or deduplication.
- [ ] Rerun `cd web && npx vitest run src/lib/geojson.test.ts`, then run `cd web && npm test`.
- [ ] Commit only the GeoJSON helper and test with a focused message such as `feat: derive selected-route transfer points`.

### Step 2.2: Add and preserve the theme-aware transfer-ring token test-first

**Files:**

- Modify: `web/src/lib/colors.test.ts`
- Modify: `web/src/lib/colors.ts`
- Modify: `web/src/lib/themeswap.test.ts`
- Modify: `web/src/lib/themeswap.ts`

- [ ] Update `colors.test.ts` first so both exact `themeTokens` objects require `transferRing`: `#F2EFE9` in light mode and `#101C36` in dark mode.
- [ ] Run `cd web && npx vitest run src/lib/colors.test.ts` and confirm RED because the token is absent.
- [ ] Add `transferRing` to `ThemeTokens` and both `themeTokens` branches with those exact starting values, then rerun the focused colors test to GREEN.
- [ ] Update the `themeswap.test.ts` fake previous style before changing `themeswap.ts`: add the `transfer-points` GeoJSON source and circle layer, with a live stroke width/radius and light-theme stroke color.
- [ ] Change the source-preservation assertion to require six custom sources, including `transfer-points`.
- [ ] Change the layer-order assertion to require seven custom layers in this exact order after the basemap: `coverage-veil`, `reach-lines`, `reach-lines-selected`, `transfer-points`, `all-stations`, `reach-dots`, `capital-stars`.
- [ ] Extend the retint assertion so a dark swap changes only the transfer layer's `circle-stroke-color` to the dark `transferRing` token while retaining its other live paint state; also assert a light swap restores the light stroke.
- [ ] Run `cd web && npx vitest run src/lib/themeswap.test.ts` and confirm RED because the sixth source/seventh layer are not carried or re-tinted.
- [ ] Extend `CUSTOM_SOURCE_IDS`, `CUSTOM_LAYER_IDS`, and `retintLayer` in `themeswap.ts`. Preserve source data and live paint through `mergeCustomStyle`; do not create a second style lifecycle.
- [ ] Rerun `cd web && npx vitest run src/lib/colors.test.ts src/lib/themeswap.test.ts`, then `cd web && npm test`.
- [ ] Commit only the colors/theme-swap files with a focused message such as `feat: theme selected-route transfer rings`.

### Step 2.3: Add the transfer source, ring layer, and selected-journey synchronization

**Files:**

- Modify: `web/src/components/Map.tsx`

**Existing seams:** `EMPTY`, the map `load` handler, `bestJourney`, `syncRider`, `propsRef`, and focused React effects.

- [ ] Import `transferPoints`, add a `transfer-points` GeoJSON source in the existing `load` setup, and add a circle layer with the same id.
- [ ] Use the v1 tuning-point paint: transparent fill, initial `circle-radius: 10`, `circle-stroke-width: 2.5`, and `circle-stroke-color: themeTokens(...).transferRing`. Do not implement or rasterize an octagon.
- [ ] Keep the ring non-interactive: do not add `transfer-points` to `CLICK_LAYERS`, cursor handlers, or station-picking logic. The GeoJSON circle layer therefore behaves as `pointerEvents: none` and clicks pass through to station-symbol layers.
- [ ] Add a focused transfer synchronization function/effect. Resolve exactly: `selectedDest` → matching `reach.destinations` entry → `bestJourney(dest, maxTrains)`.
- [ ] Set the shared `EMPTY` FeatureCollection when reach, selected destination, matching destination, or eligible journey is absent. Also clear it when `journey.duration_min > maxMinutes`, mirroring `syncRider` and visible-route filtering.
- [ ] For an eligible visible journey, build the station-id map, call `transferPoints`, and replace the source data with point features in returned order. Do not use `leg.via`, show markers for the whole reach fan, or retain stale data on destination/filter changes.
- [ ] Make the effect depend on `selectedDest`, `reach`, `maxTrains`, `maxMinutes`, and `stations`. Invoke it after initial source creation so the current props populate the map on load.
- [ ] Run `cd web && npx vitest run src/lib/geojson.test.ts src/lib/colors.test.ts src/lib/themeswap.test.ts`.
- [ ] Run `cd web && npm run lint && npm run build`; treat TypeScript/MapLibre source and layer typing as the integration check.
- [ ] Commit only `Map.tsx` with a focused message such as `feat: render selected-route transfer rings`.

### Step 2.4: Move `all-stations` above route layers as an isolated layer-order change

**Files:**

- Modify: `web/src/components/Map.tsx`

**Review boundary:** This step changes ordering only. Keep the `all-stations` paint and transfer synchronization unchanged.

- [ ] Reorder initial layer insertion to produce: coverage veil, ordinary route line, selected route line, `transfer-points`, `all-stations`, `reach-dots`, and capital stars.
- [ ] Ensure the change specifically moves `all-stations` above both route layers and the transfer ring, leaving the ring above the selected line but below every station-symbol layer.
- [ ] Keep `transfer-points` absent from `CLICK_LAYERS`; do not change `pickFeature`, station cursor handling, or paints as part of this order-only review.
- [ ] Run `cd web && npx vitest run src/lib/themeswap.test.ts` and verify its seven-custom-layer order matches initial Map construction.
- [ ] Run `cd web && npm test`.
- [ ] Run `cd web && npm run lint && npm run build`.
- [ ] Record browser calibration cases for the user: direct, one-transfer, and two-transfer selected journeys; light and dark themes; stop and time filter changes; destination switching/clearing; reduced-motion mode. Radius, stroke width, and casing colors are tuning points, and only the user signs off visual evaluation.
- [ ] Commit only the layer-order diff in `Map.tsx` with a focused message such as `fix: place station dots above route rings`.

---

## Unit 4 — Grouped-city choice popup on map origin selection (3 steps)

This unit depends only on existing `CityGroups`, `selectCityOrigin`, the resolved `armed` value, `routeMapClick`, and `MapView` click handling. It must work if Units 1–3 are reverted and must leave To routing unchanged.

### Step 4.1: Add `cityForStation` popup eligibility tests first

**Files:**

- Modify: `web/src/lib/cities.test.ts`
- Modify: `web/src/lib/cities.ts`

**Interface:** `cityForStation(id: string, cityGroups: CityGroups): { city: string; memberIds: string[] } | null`

- [ ] Import `cityForStation` and add a dedicated test group before implementing it.
- [ ] Assert an id in a multi-member group returns the exact city and original member-id array.
- [ ] Assert an id absent from every group returns `null`.
- [ ] Assert an id in a singleton group returns `null`; include an empty group in the fixture and confirm it is ineligible as well.
- [ ] Add a deterministic malformed-input regression: when the same id appears in two multi-member groups, return the first `Object.entries` match.
- [ ] Run `cd web && npx vitest run src/lib/cities.test.ts` and confirm RED because the helper is missing.
- [ ] Implement a one-shot `Object.entries` scan that returns only groups of at least two members. Do not replace or rebuild the existing `CityLookup` used by planner search, copy arrays, or add data validation.
- [ ] Rerun `cd web && npx vitest run src/lib/cities.test.ts`, then `cd web && npm test`.
- [ ] Commit only the city helper and test with a focused message such as `feat: identify grouped station origins`.

### Step 4.2: Pass city context into `MapView` and implement From-only popup behavior

**Files:**

- Modify: `web/src/App.tsx`
- Modify: `web/src/components/Map.tsx`

**Existing seams:** App's `cityGroups`, already-resolved `armed`, existing `selectCityOrigin`, Map's `propsRef`, `pickFeature`, station click handler, and `onStationClick`.

- [ ] Extend `MapView` props with `cityGroups: CityGroups`, `armed: "from" | "to"`, and `onSelectCityOrigin(city, memberIds)`. In App, pass the existing `cityGroups`, computed `armed`, and existing `selectCityOrigin` callback; do not duplicate union fetching in Map.
- [ ] Import and call `cityForStation` only after a station has been picked and only when `propsRef.current.armed === "from"`.
- [ ] Preserve the To branch exactly: immediately call existing `onStationClick(pick)` without inspecting city membership or opening a popup. `routeMapClick` continues to distinguish reachable destinations from unreachable stations.
- [ ] Preserve immediate From behavior for ungrouped/singleton ids: when `cityForStation` returns `null`, call `onStationClick(pick)` exactly as today.
- [ ] If a grouped id cannot be found in `stations` for its exact display name and coordinates, skip the popup and call `onStationClick(pick)`.
- [ ] For an eligible grouped From click, create/replace one MapLibre popup anchored at the station's actual `[lon, lat]`, never at the arbitrary pointer location. Configure lifecycle for explicit removal rather than relying on automatic click closing.
- [ ] Build content with DOM APIs and `setDOMContent`, never interpolated HTML. Create a dedicated popup/container class and two semantic `button` elements whose text comes from `textContent`: the exact station display name and `All of <City>`.
- [ ] On the station button, remove the popup first and then call existing `onStationClick(pick)`, preserving the `selectOrigin(id)` route. On the city button, remove first and call `onSelectCityOrigin(city, memberIds)`.
- [ ] Remove/replace any existing city popup at the start of another map click. On an empty click, remove it before calling `onEmptyClick`. Keep the coverage tooltip popup independent.
- [ ] Add cleanup that removes the popup when `armed` leaves `"from"` and when Map unmounts. Ensure no stale button listeners/popup DOM survive replacement.
- [ ] Do not add a hover-only path: use the existing MapLibre `click` event so mouse and touch tap share behavior.
- [ ] Run `cd web && npx vitest run src/lib/cities.test.ts src/lib/mapclick.test.ts`; the existing `routeMapClick` assertions must remain unchanged and green, including From winning over reachable dots and To distinguishing reachable/unreachable stations.
- [ ] Run `cd web && npm run lint && npm run build` as the prop, DOM, and MapLibre integration check.
- [ ] Commit only `App.tsx` and `Map.tsx` with a focused message such as `feat: choose station or grouped city from map`.

### Step 4.3: Add theme-aware popup styling and complete lifecycle verification

**Files:**

- Modify: `web/src/index.css`

- [ ] Style the dedicated popup shell/content and both buttons with existing `--surface`, `--surface-hover`, `--text`, `--border`, and `--shadow-small`/`--shadow` variables so theme switching updates an already-open popup without JS re-creation.
- [ ] Style the MapLibre popup tip to match the themed surface, keep the layout compact, and give each button a practical touch target of at least 40 px height with visible hover and keyboard focus states.
- [ ] Do not introduce hard-coded light-only popup colors or alter unrelated panel/MapLibre popup styles globally.
- [ ] Run `cd web && npm test`.
- [ ] Run `cd web && npm run lint && npm run build`.
- [ ] Hand the following browser checks to the user for visual/pointer acceptance: From armed + Paris member opens both choices; station choice loads only that station; `All of Paris` loads the existing union and labels From as Paris; ungrouped station selects immediately; To armed never opens the popup; mouse and touch/tap both work; empty click/another click/field re-arming removes the popup; light/dark switching remains legible.
- [ ] Commit only `web/src/index.css` with a focused message such as `style: theme grouped-city map popup`.

---

## Final verification

Run these after all four units are implemented. Each unit's focused commits remain independently revertible; this section checks their combined repository state.

- `cd web && npm test`
- `cd web && npm run lint && npm run build`
- `uv run pytest tests/test_search.py tests/test_international.py`
- `uv run pytest`
- the Unit 3 real-data exonym verification snippet:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from server.app import EXONYMS, normalize

stations = json.loads(
    Path("data/out/stations.json").read_text(encoding="utf-8")
)["stations"]
normalized = [(station["name"], normalize(station["name"])) for station in stations]

missing = []
for native in sorted(set(EXONYMS.values())):
    matches = [name for name, folded in normalized if native in folded]
    print(f"{native}={len(matches)}: {matches}")
    if not matches:
        missing.append(native)

if missing:
    raise SystemExit(f"DROP unmatched EXONYMS targets: {missing}")
print(f"verified against {len(stations)} stations")
PY
```

- Browser calibration for Units 2 and 4 in light/dark themes and pointer/touch input is the user's responsibility; visual evaluation is human, not automated, and the implementer must not claim it passed.
- Finish with `git diff --check` and `git status --short`, confirming only the planned implementation files are present and no unrelated changes were staged.

## Risks and assumptions

- `data/out/stations.json` exists for the required Unit 3 evidence gate. If a later snapshot changes, its printed total/counts supersede the planning-time 1,725 count, and zero/incorrect matches must be dropped rather than guessed.
- Substring expansion intentionally retains existing incidental matches and ranking behavior; this plan does not introduce per-exonym scoring.
- MapLibre has no React component test harness in the current suite. Pure decisions and style preservation are automated; source/layer wiring and popup DOM integration are covered by TypeScript/lint/build plus explicit human browser checks.
- Unit 2 ring radius, stroke width, and casing colors and Unit 4 popup spacing are starting values, not automated visual guarantees.
