# Planner and search UX polish (backlog T) — design

**Date:** 2026-07-13

**Backlog item:** T (plus the city-option relabel from U)

**Status:** design approved, spec for implementation planning

**Scope:** four independent units across the existing FastAPI search and
Vite/React/MapLibre planner. No pipeline, data-schema, or API-contract changes.

## Goal and boundaries

Polish four common planning interactions without changing how reachability is
computed: clearing From can continue from the current destination, selected
journeys expose their transfer stations, station search recognizes a broader
curated set of exonyms, and a grouped-city station click can select either that
station or the whole city.

Each unit is independently implementable, testable, and revertible. Units 2 and
4 both touch `Map.tsx`, but neither consumes the other's helper, source, popup,
or state. The suggested implementation order is **1, 3, 2, 4** (cheap state and
copy changes first, visual/map work last).

Preserve the current endpoint shapes, `ReachFile`/`CityGroups` data shapes,
selection filters, MapLibre click precedence, and theme system. Add no runtime
dependency and perform no unrelated refactoring.

## Unit 1 — Promote destination when From is cleared

### Purpose

Clearing From while a complete journey is selected should keep the user's place
in the exploration. The current destination becomes the next origin, and the
planner remains ready to accept a new destination.

### Exact behavior

- Add an App-level `onClearOrigin` callback instead of passing
  `clearSelection` directly to `JourneyPlanner`.
- Decide the action from `selectedDest` only:
  - Destination present: capture its station id, clear `cityOrigin`,
    `selectedDest`, and `hint`; keep/set `activeField = "to"`; request
    `api.getReach(destId)` and install the successful result with `setReach`.
    Do **not** keep the previous origin as the new destination. This is
    `swapSelection`'s reach-loading path without its `swapDest` step.
  - No destination: call the existing `clearSelection()` unchanged. This still
    clears the city origin, reach, destination, hint, and armed field.
- The promoted value is always one station. If the old origin was a city union,
  promotion clears `cityOrigin`; the new From label comes from the promoted
  station and its ordinary reach file.
- Do not reset `maxTrains` or `maxMinutes`; the current filters survive, as they
  do for other origin changes.
- Use the existing `api.getReach` error path (`setError(String(e))`). Do not add
  rollback or a new loading-state model in this unit. As with `swapSelection`,
  the old reach may remain until the request resolves, while To is cleared
  immediately.

### Files touched

- `web/src/lib/selection.ts` — add the pure decision helper.
- `web/src/lib/selection.test.ts` — add its truth-table tests.
- `web/src/App.tsx` — add the async state wiring and pass it as
  `JourneyPlanner.onClearOrigin`.

`JourneyPlanner.tsx` and `StationField.tsx` need no interface or rendering
change; they already expose and invoke `onClearOrigin`.

### Pure helper

`clearOriginAction(selectedDest: string | null): { promote: string } | { clearAll: true }`
lives in `web/src/lib/selection.ts` beside `emptyClickAction` and `swapDest`.
It returns `{ promote: selectedDest }` for a non-null id and
`{ clearAll: true }` otherwise. It has no knowledge of React, reach files, or
city origins; App owns all side effects.

### Testing notes

- Unit-test a station id returning `{ promote: id }` and `null` returning
  `{ clearAll: true }` in `selection.test.ts`.
- Typecheck/build verifies that the new App callback still satisfies
  `JourneyPlanner`'s existing prop.
- Browser acceptance:
  1. Select A → B, clear From, and observe B as From, blank To, the reach fan
     loaded from B, and To still armed.
  2. Select only A, clear From, and observe the current full-clear behavior.
  3. Select a city-union origin → station destination, clear From, and observe a
     plain station origin rather than a city union.

### Edge cases

- A city-union origin with no destination still takes the full-clear branch.
- The helper treats an empty string as a destination id if one is ever passed;
  production state uses `null` for absence, so do not broaden the helper with
  truthiness rules.
- A failed promotion fetch follows existing swap error behavior: show the error,
  do not invent a replacement reach, and do not restore the cleared destination.

## Unit 2 — Mark transfers on the selected route

### Purpose

Make a multi-leg selected journey readable on the map by marking every place
where one leg ends and the next begins. These markers describe only the journey
currently highlighted and ridden, not every possible journey in the reach fan.

### Exact behavior

- The transfer stations for a `Journey` are `leg.to` for every leg except the
  final leg, in journey order. `leg.via` stations are through stops, not
  transfers. A zero- or one-leg journey has no transfer marker.
- In `Map.tsx`, resolve the same selected journey used by `syncRider`:
  `selectedDest` → matching destination → `bestJourney(dest, maxTrains)`.
  If there is no reach, selected destination, matching destination, or eligible
  journey, set the transfer source to the shared empty FeatureCollection.
- Mirror the rider/visible-route time cutoff. If the chosen journey's
  `duration_min > maxMinutes`, clear the transfer source; never show markers for
  a route the current time filter does not draw or ride.
- Add a GeoJSON source `transfer-points` and a circle layer with the same id.
  Recompute it when `selectedDest`, `reach`, `maxTrains`, `maxMinutes`, or
  `stations` changes. Theme changes retain and re-tint it through the existing
  style-swap path.
- Layer order is: coverage veil, ordinary route line, selected route line,
  `transfer-points`, then `all-stations`, `reach-dots`, and capital stars. This
  moves `all-stations` above the route layers (without changing its paint) so
  the ring is strictly above the route and below every station-symbol layer.
- The transfer layer is not added to `CLICK_LAYERS` and receives no cursor
  handlers. In MapLibre terms this is the required `pointerEvents: none`
  behavior: station picking passes through to the existing dot layers.

### V1 marker style — tuning point

Ship a simple hollow circle first:

- transparent fill;
- initial `circle-radius: 10` and `circle-stroke-width: 2.5`, larger than a
  normal station dot and much smaller than the 46 px rider;
- stroke from a new `ThemeTokens.transferRing` token, initially the same casing
  values already used around reach dots: `#F2EFE9` in light mode and `#101C36`
  in dark mode.

The size, stroke width, and starting casing colours are explicitly a visual
**TUNING POINT** to calibrate on the real map. The user floated a stop-sign
(octagonal) interchange marker as a later experiment. Do not build or rasterize
an octagon in v1.

### Files touched

- `web/src/lib/geojson.ts` — add `transferPoints`.
- `web/src/lib/geojson.test.ts` — add journey-boundary tests.
- `web/src/lib/colors.ts` and `web/src/lib/colors.test.ts` — add and pin the
  per-theme transfer-ring token.
- `web/src/components/Map.tsx` — add the source/layer and synchronization.
- `web/src/lib/themeswap.ts` and `web/src/lib/themeswap.test.ts` — carry the new
  source/layer across `setStyle` and re-tint its stroke.

### Pure helper

`transferPoints(journey: Journey, stationsById: Map<string, Station>): [number, number][]`
lives in `web/src/lib/geojson.ts`. For each non-final leg it looks up `leg.to`
and returns `[station.lon, station.lat]`. Missing station ids are omitted rather
than throwing, matching the defensive behavior of the existing GeoJSON builders.
The helper does not choose a journey or apply filters; `Map.tsx` owns those
decisions.

### Testing notes

- `geojson.test.ts` covers exactly:
  - one leg → `[]`;
  - two legs → one coordinate at the first leg's `to` station;
  - three legs → two coordinates in leg order.
- Add a missing-boundary-station assertion to lock in omission rather than an
  exception. A `via` station must not appear in the result.
- `colors.test.ts` pins both `transferRing` values.
- `themeswap.test.ts` verifies the sixth custom source and seventh custom layer
  survive a theme swap, remain between selected lines and station dots, and use
  the destination theme's stroke token.
- Manual acceptance checks direct, one-transfer, and two-transfer selections in
  both themes, after changing both stop and time filters, and with reduced
  motion enabled (the static transfer markers are unaffected by rider motion).

### Edge cases

- Consecutive legs are expected to meet, but the definition remains the prior
  leg's `to` even if malformed data gives the next leg a different `from`.
- Repeated transfer ids remain repeated boundaries. Map rendering naturally
  overlaps them; do not add deduplication policy in this unit.
- Switching or clearing the destination must replace/empty the source so stale
  markers never remain.
- Theme switching must not recreate the source from scratch or lose its current
  data; extend `mergeCustomStyle` rather than adding a separate style lifecycle.

## Unit 3 — Curated station-search exonyms and city-option relabel

### Purpose

Let users type common non-native city names into the From station search while
keeping the current static, auditable query-expansion mechanism. Also apply the
approved copy change to grouped-city search results.

### Exact behavior

- Extend `server.app.EXONYMS`; do not change `normalize`, `_query_variants`, the
  `/api/stations/search` response, ranking, limit, or reach-file-on-disk filter.
- Keys are normalized user spellings and values are the exact `normalize()`d
  substring present in station names. Expansion remains query-only and is never
  written to station or pipeline data. Partial exonym typing and suffix
  replacement continue to work through `_query_variants`.
- The following 35 additions were checked against the current
  `data/out/stations.json` snapshot (1,725 stations) with the same substring
  evidence convention as the existing comment:

| New query key | Native target | Current matches |
|---|---|---:|
| `rome` | `roma` | 2 |
| `antwerp` | `antwerpen` | 1 |
| `the hague` | `den haag` | 3 |
| `copenhagen` | `københavn` | 2 |
| `lyons` | `lyon` | 4 |
| `marseilles` | `marseille` | 2 |
| `seville` | `sevilla` | 1 |
| `aix-la-chapelle` | `aachen` | 2 |
| `ratisbon` | `regensburg` | 1 |
| `brunswick` | `braunschweig` | 1 |
| `hanover` | `hannover` | 2 |
| `coblenz` | `koblenz` | 1 |
| `mayence` | `mainz` | 1 |
| `francfort` | `frankfurt` | 7 |
| `strassburg` | `strasbourg` | 1 |
| `bale` | `basel` | 2 |
| `lucerne` | `luzern` | 1 |
| `berne` | `bern` | 6 |
| `bucharest` | `bucuresti` | 1 |
| `danzig` | `gdansk` | 5 |
| `breslau` | `wroclaw` | 2 |
| `stettin` | `szczecin` | 3 |
| `posen` | `poznan` | 1 |
| `cracow` | `krakow` | 3 |
| `lodz` | `łodz` | 6 |
| `saragossa` | `zaragoza` | 1 |
| `gerona` | `girona` | 1 |
| `lerida` | `lleida` | 1 |
| `corunna` | `a coruna` | 1 |
| `bois-le-duc` | `s-hertogenbosch` | 1 |
| `flushing` | `vlissingen` | 2 |
| `pressburg` | `bratislava` | 2 |
| `lemberg` | `lviv` | 1 |
| `zagabria` | `zagreb` | 1 |
| `fiume` | `rijeka` | 1 |

`normalize()` currently retains stroke characters such as `ø`, `ł`, so the
verified Copenhagen and Łódź targets are `københavn` and `łodz`, not guessed
ASCII forms. This unit does not change normalization.

- Re-run the evidence check immediately before finalizing `EXONYMS`, update the
  comment block's station total and match counts, and **drop every new entry with
  zero matches**. Inspect the printed station names as well as the count so an
  incidental substring is not mistaken for the intended city:

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

- Current examples that must be dropped rather than guessed because their
  proposed targets have no intended station match are Florence → Firenze,
  Naples → Napoli, Turin → Torino, Lisbon → Lisboa, Gothenburg → Goteborg,
  Athens → Athina, Bruges → Brugge, and Pilsen → Plzen. Reconsider them only
  after a future data build actually contains the corresponding native station.
- Change the exact grouped-city option label in `cityOptions` from
  `` `${city} — all stations` `` to `` `${city} (All stations)` ``. No other
  planner copy changes are included.

### Files touched

- `server/app.py` — extend `EXONYMS` and refresh its evidence comment.
- `tests/test_search.py` — cover representative new English, multiword,
  non-ASCII-target, and transliteration expansions.
- `web/src/lib/planner.ts` — change the city-option label template.
- `web/src/lib/planner.test.ts` — update the exact expected label.

`tests/test_international.py::test_exonym_targets_exist` already guards every
unique target against real pipeline output when that output is available; keep
it green. `CITY_EXONYMS` in `web/src/lib/cities.ts` is not expanded by this unit:
the server list applies to station results, while this unit takes only U's copy
relabel.

### Pure helper

No new helper is needed. `normalize` and `_query_variants` are the existing pure
query-expansion seam, and `cityOptions` is already a pure web helper. This unit
changes curated data and one output label, not the search architecture.

### Testing notes

- Extend the search fixture with stations/reach files representing at least
  Roma, København, Den Haag, București, and Łódź. Assert full queries resolve to
  the intended ids; include a partial prefix such as `copen` to preserve the
  type-ahead behavior and a multiword query such as `the hague`.
- Keep native-name tests green to prove expansion does not replace the original
  query variant.
- Update the `cityOptions` exact-object assertion to
  `label: "Paris (All stations)"`.
- Run the required real-data verification snippet even if unit fixtures pass;
  fixtures cannot satisfy the evidence requirement.

### Edge cases

- The existing three-character expansion floor remains. One- and two-character
  queries do not expand.
- A native target can also match other station names by prefix/substring (for
  example `roma` also prefixes Romanshorn). Preserve current prefix-first,
  shorter-name ranking rather than adding per-exonym scoring rules.
- Search still returns only stations with a reach file on disk. An exonym is not
  permission to expose an unservable origin.
- Do not add unmatched keys with a best-effort spelling, and do not store an
  English alias on `Station` objects.

## Unit 4 — Grouped-city choice popup on map origin selection

### Purpose

Expose the existing city-union origin from the map without slowing down ordinary
station selection. A station in a multi-station city offers a one-click choice
between that exact station and the whole city; every other map click keeps its
current behavior.

### Exact behavior

- Add a one-shot city decision helper in `cities.ts`. A popup is eligible only
  when the clicked id belongs to a `cityGroups` entry containing at least two
  member ids.
- App passes `cityGroups`, the already-resolved armed target (`armed`, from
  `armedTarget(activeField, reach !== null)`), and an
  `onSelectCityOrigin(city, memberIds)` callback to `MapView`. The callback is
  the existing `selectCityOrigin`; do not duplicate union fetching in the map.
- In Map's existing station click handler:
  1. If the armed target is `"to"`, immediately call the existing
     `onStationClick(pick)`. Do not inspect city membership and do not show a
     popup.
  2. If the target is `"from"` and the helper returns `null`, immediately call
     `onStationClick(pick)` exactly as today—no extra click.
  3. If the target is `"from"` and the helper returns a city, open a small
     MapLibre `Popup` anchored at the clicked station's actual `[lon, lat]`, not
     the arbitrary pointer location. It contains two semantic buttons:
     - the station's exact display name → remove the popup, then call existing
       `onStationClick(pick)`, which routes to `selectOrigin(id)`;
     - `All of <City>` → remove the popup, then call
       `onSelectCityOrigin(city, memberIds)`.
- Build the popup with `setDOMContent`, not an interpolated HTML string. Give
  the container a dedicated class and style it in `index.css` with existing
  surface/text/border/shadow variables. Keep it compact while giving each
  button a practical touch target (at least 40 px high).
- MapLibre's normal `click` event covers mouse click and touch tap, so tap opens
  the same choice. Do not create a hover-only or desktop-only path.
- Keep at most one city popup. Remove/replace it on another map click; remove it
  after either choice, on an empty click, when the armed target leaves From,
  and when the map unmounts. The existing coverage tooltip remains independent.

### Files touched

- `web/src/lib/cities.ts` — add the pure `cityForStation` helper without
  replacing the existing prebuilt `CityLookup` used by planner search.
- `web/src/lib/cities.test.ts` — add popup-eligibility tests.
- `web/src/App.tsx` — pass city groups, armed target, and the city-origin
  callback to the map.
- `web/src/components/Map.tsx` — create, anchor, update, and clean up the popup.
- `web/src/index.css` — small theme-aware popup/button styling.

No API, `cityunion.ts`, `planner.ts`, or pipeline changes are required.

### Pure helper

`cityForStation(id: string, cityGroups: CityGroups): { city: string; memberIds: string[] } | null`
lives in `web/src/lib/cities.ts`. It returns the matching city and its member ids
only when the group has at least two members; unknown ids and singleton/empty
groups return `null`. `cities.json` groups are expected to be disjoint. If
malformed input repeats an id across groups, use the first `Object.entries`
match deterministically and do not add data validation to this UI unit.

### Testing notes

- `cities.test.ts` covers:
  - id in a multi-station group → `{ city, memberIds }`;
  - id absent from all groups → `null`;
  - id in a singleton group → `null`.
- Keep existing `routeMapClick` tests green: From still wins over a reachable-dot
  hit for the single-station button, and To still distinguishes reachable from
  unreachable stations.
- Browser acceptance covers mouse and touch/tap:
  1. From armed + Paris member dot opens the two choices.
  2. Station choice loads only that member's reach.
  3. `All of Paris` loads the existing union and labels From as Paris.
  4. An ungrouped station selects immediately.
  5. To armed + any grouped member keeps current destination behavior and never
     opens the popup.
  6. Light/dark switching leaves the popup legible.

### Edge cases

- If city groups have not loaded (the current fallback is `{}`), every station
  follows immediate single-station behavior.
- If the clicked station cannot be found in the `stations` prop for anchoring or
  labeling, skip the popup and call `onStationClick` rather than rendering a
  broken choice. Map dot data normally makes this impossible.
- A grouped station may be represented by `reach-dots`, `all-stations`, or a
  capital star; membership is based only on the picked station id, so layer
  precedence does not change the result.
- A city union is origin-only. Do not offer `All of <City>` for To, and do not
  add city unions to destination state.

## Cross-cutting verification and non-goals

Every new pure helper is unit-tested in its colocated Vitest file, and all
existing tests remain green. Final implementation verification is:

- `cd web && npm test`
- `cd web && npm run lint && npm run build`
- `uv run pytest tests/test_search.py tests/test_international.py`
- `uv run pytest`
- the Unit 3 real-data exonym verification snippet
- browser calibration for Units 2 and 4 in light/dark themes and pointer/touch
  input

The current web suite is roughly 89 tests; acceptance is a green complete suite,
not a hard-coded count as new assertions are added.

Out of scope: the octagonal stop-sign transfer experiment, route geometry or
corridor changes, dynamic/remote exonym storage, normalization changes, city
unions as destinations, popups while To is armed, city-group data changes, and
any pipeline recomputation.
