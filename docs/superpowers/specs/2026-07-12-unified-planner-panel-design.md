# Unified journey-planner panel (backlog M) — design

**Date:** 2026-07-12
**Backlog item:** M (Unified journey-planner panel, upper-left)
**Status:** design approved, spec for review
**Scope:** UI-only. No data, pipeline, server, or API changes.

## Problem

The controls are scattered: a `SearchBox` (origin only), a bottom **status bar**
(origin → dest text + unselect ×), and a floating bottom-left `JourneyCard`
(duration, legs, book, swap). There is no way to type a destination, no visible
"From/To" model, and the origin the map already knows about isn't shown as an
editable field. The user wants one trip-planner card in the upper-left, shaped
like a real journey planner.

## Goal

Consolidate `SearchBox` + status bar + `JourneyCard` into a single
`JourneyPlanner` card in the existing upper-left `.panel`, with **From**/**To**
fields, **swap**, filters, trip details, and legend — all in one column. Add an
"armed field" interaction so the user can click into a field and then click a
station on the map to fill *that* field.

Non-goals: the N booking-link bug, the "hide small dots at zoom" idea, and item
L dimming are out of scope. Data is unchanged.

## Layout (approved: "all-in-one card")

Single card in `.panel`, top → bottom:

```
┌ planner (upper-left) ─────┐
│ From [ Berlin Hbf     ✕ ] │
│            ⇄              │
│ To   [ type or click…   ] │
│ ───────────────────────── │
│ Nonstop │ 1 stop │ 2 stops │   ← StopToggle
│ Max time  ≤ any   [====○ ] │   ← TimeSlider
│ ───────────────────────── │
│ Berlin → Paris            │   ← Trip details (only when a To is selected)
│ 8h15 · 1 change           │
│ [   Book this trip   ]    │
│ ───────────────────────── │
│ ● <2h ● <4h ● <6h ● <8h   │   ← Legend (only once a reach is loaded)
└───────────────────────────┘
```

- **Hint** line ("Search or click a station to begin.") replaces Trip details
  when no origin is set.
- **Error** line preserved (existing `error` state).

## Component architecture

- **`StationField.tsx`** — extracted from `SearchBox`: the input + results
  dropdown + `keynav` keyboard navigation. Props:
  - `value` (selected station name or empty), `placeholder`, `disabled`.
  - `onPick(station)`, `onClear()`.
  - `onFocusField()` — arms this field (see interaction model).
  - `source`: how it produces results —
    - **From** → `api.searchStations(q)` (all stations, existing endpoint).
    - **To** → client-side `reachableDestOptions(reach, stationsById, q)` — filters
      the current origin's reachable destinations by name. No API call; naturally
      excludes unreachable stations. Empty query with an origin set may show
      nothing (dropdown only opens on typing), and a query with no match shows a
      "No route within your filters" empty row.
- **`JourneyPlanner.tsx`** — composes the card: From field, ⇄ swap button, To
  field, `StopToggle`, `TimeSlider`, Trip details, `Legend`, hint/error.
- **`TripDetails`** — the current `JourneyCard` body (duration, nonstop×/day or
  N changes, legs list, **Book this trip**, fineprint), rendered *in flow* inside
  the card. No more absolute positioning; the `onClose` × becomes the To field's
  ✕. `bookingUrl` usage unchanged (N bug not touched here).
- **`StopToggle`, `TimeSlider`, `Legend`** — unchanged internally; just re-parented
  into the card.
- **Deleted:** the standalone `SearchBox` (replaced by `StationField`), the inline
  status-bar JSX in `App.tsx`, and the floating `JourneyCard` container styling.

### Pure logic (unit-tested, `lib/` per repo convention)

- **`lib/planner.ts`**
  - `reachableDestOptions(reach, stationsById, query): Station[]` — reachable
    destinations whose name matches `query` (same normalization spirit as search).
  - `swapEnabled(hasOrigin, hasDest): boolean`.
  - `toEnabled(hasOrigin): boolean`.
- **`lib/mapclick.ts`**
  - `armedTarget(activeField, hasOrigin): "from" | "to"` —
    `activeField ?? (hasOrigin ? "to" : "from")`.
  - `routeMapClick(pick, target): { action: "origin" | "dest" | "unreachableTo"; id: string }`
    where `pick` is the existing `FeaturePick` (`{type:"dest"|"origin", id}`):
    - `target === "from"` → `{ action:"origin", id: pick.id }` (even if the hit was
      a reachable dot — From wins).
    - `target === "to"` → `pick.type === "dest"` ? `{ action:"dest" }` :
      `{ action:"unreachableTo" }`.

## Interaction model

State added to `App`: `activeField: "from" | "to" | null` (which field the next
map click fills).

- **Focusing** From or To sets `activeField` to that field. It **stays set after
  the input blurs** — clicking the map canvas blurs the input, so live focus can't
  be the source of truth. `activeField` is only changed by another focus or a map
  click.
- **`Map.tsx` change:** it no longer decides origin-vs-dest. It emits a single
  `onStationClick(pick: FeaturePick)` (still built from `pickFeature`, unchanged)
  and one `onEmptyClick()` (unchanged). App routes the station click:
  1. `target = armedTarget(activeField, hasOrigin)`
  2. `routeMapClick(pick, target)`:
     - `origin` → `selectOrigin(id)` (fetch reach, clear To); then advance
       `activeField = "to"`.
     - `dest` → `setSelectedDest(id)` (highlights journey, shows Trip details);
       `activeField` stays `"to"`.
     - `unreachableTo` → show a transient hint ("Not reachable from {origin}
       within your filters"); no state change.
- **Typing** in a field uses that field's `source` and picking a result behaves
  the same as a map fill (From → `selectOrigin`; To → `setSelectedDest`).
- **✕ on From** clears everything (origin, dest, reach) — the old status-bar
  unselect. **✕ on To** clears only the destination (back to explore).
- **⇄ Swap** reuses existing `swapSelection`; enabled only when both set.

### Defaults chosen (call out in review if wrong)

1. Filling **From** via a map click auto-advances arming to **To**.
2. An **unreachable To-click** is ignored with a hint, not reinterpreted as a new
   origin.
3. Legend appears only once a reach is loaded (nothing to legend before then).

## Preserved behaviors

- **Esc** clears (dest first, then origin) — existing handler, retargeted to the
  new state.
- **Map empty-click** clears per existing `emptyClickAction`.
- **Selected-journey highlight** (backlog J) on destination select — unchanged.
- **Header, wordmark, theme toggle** — unchanged.
- `easeTo` re-centre on origin — unchanged (still a known deferred minor).

## Testing

- New: `lib/planner.test.ts` (`reachableDestOptions` filters to reachable + name
  match; `swapEnabled`/`toEnabled` truth tables).
- New: `lib/mapclick.test.ts` (`armedTarget` default resolution; `routeMapClick`
  for from/to/reachable/unreachable, including From winning over a reachable-dot
  hit).
- Existing `keynav`, `pickfeature`, `highlight`, `booking`, `geojson` tests stay
  green (logic reused, not rewritten).
- Component render smoke: `JourneyPlanner` shows hint with no origin, fields +
  filters + legend with an origin, Trip details with a selected dest.
- Whole suite (`npm test`) must remain green.

## Out of scope / follow-ups

- **N** — broken Trainline booking link (separate bug).
- **L** — dimming; interacts with this panel but not built here.
- "Hide small location dots at smaller zoom levels" (backlog note, 2026-07-12).
