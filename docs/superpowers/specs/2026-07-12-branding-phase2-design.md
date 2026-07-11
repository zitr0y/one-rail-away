# onestopeurope — branding Phase 2: dark mode + mascot rider (backlog item D)

Date: 2026-07-12. Decided interactively with the user. Parent spec:
`docs/superpowers/specs/2026-07-11-branding-design.md` (tokens, phasing).
Phase 1 (light identity) shipped 2026-07-11 with three user calibration rounds.

## Scope

Two features, one plan:

1. **Dark mode ("deep night")** — `mapstyle-dark.json`, theme state
   (`prefers-color-scheme` + manual toggle, persisted), per-theme overlay
   re-tunes, CSS-variable panel chrome.
2. **Mascot riding the selected journey line** — the C0 train animates along
   the selected journey's geometry in a continuous loop, rotating with the
   line, pausing at transfer stations.

Out of scope: bend-along-route logo morphing (parent spec Phase 3), corridor
bundling (backlog I), any pipeline/server change. Everything here is web-side.

## User decisions (2026-07-12 brainstorm)

| Decision | Choice |
|---|---|
| Ride style | Continuous loop: origin → destination, ~1 s rest, restart |
| Traverse duration | Fixed per traverse — see TUNING POINT below |
| Orientation | Rotate to path tangent + mirror when heading westward (never upside down) |
| Transfers | ~0.5 s pause at each transfer station |
| Theme switching | `map.setStyle(url, { transformStyle })` carrying custom sources/layers over |
| Mascot rendering | DOM `maplibregl.Marker` + `requestAnimationFrame` (crisp SVG, CSS transforms) |

**TUNING POINT (traverse duration):** start with a fixed ~7 s traverse
regardless of journey length (short hops don't blur, long ones don't crawl).
The user is explicitly unsure ("not super sure about long and short ones all
taking 7 s — we shall find out"). Keep the duration a single named constant;
if fixed feels wrong on the real map, the prepared fallback is mild scaling
with path length (e.g. 5–10 s clamped). User judges on the real map.

## Dark mode

### Theme state

- New `web/src/lib/theme.ts`: pure `resolveTheme(stored, systemPrefersDark)`
  → `"light" | "dark"`. No stored choice → follow the system; an explicit
  toggle click sticks. Persisted in `localStorage` key `ose-theme`.
- A React hook (in `App.tsx` or `theme.ts`) wires `matchMedia`
  (`prefers-color-scheme: dark`, with change listener) + localStorage, and
  stamps `data-theme="light|dark"` on `<html>`.
- Toggle UI: small sun/moon button in the navy header bar, right side next to
  the tagline. Chrome stays navy `#003399` in both themes (parent spec).

### Basemap dark

- `web/public/mapstyle-dark.json`: fork OpenFreeMap's **dark** style (its
  labels/roads are already light-tuned), retinted to parent-spec tokens:
  land `#101C36`, water `#0A1226`. Sources/glyphs/sprite URLs stay untouched
  (same discipline as `mapstyle-light.json`).
- `styleUrl(theme)` in `web/src/lib/mapstyle.ts` extends to
  `"dark"` → `/mapstyle-dark.json`.
- On theme change: `map.setStyle(styleUrl(theme), { transformStyle })` where
  `transformStyle` merges our five custom sources (`all-stations`,
  `reach-lines`, `reach-dots`, `coverage`, `capitals`) and their layers
  (incl. `reach-lines-selected`, `coverage-veil`, `capital-stars`) from the
  previous style into the new one — no re-add, no flicker, live paint state
  (opacity expressions, filters) preserved. The `star-icon` image survives
  `setStyle` only if re-added: verify, and re-add on `styledata` if wiped.
  Then apply the new theme's overlay tokens (below).

### Per-theme overlay tokens

Single source: `themeTokens(theme)` helper exported from
`web/src/lib/colors.ts` (next to `BRAND`). `Map.tsx` reads tokens, never hex
literals. Values (light = today's calibrated values; dark = starting points
for the user's calibration pass):

| Token | Light (current) | Dark (starting value) |
|---|---|---|
| stationDot | `#003399` | `#5B7FDB` (navy is invisible on `#101C36`) |
| reachDotStroke | `#F2EFE9` | `#101C36` (always the land color) |
| veil | `#9c9589` | `#6B7590` (cool grey; same 0.08/0.16 opacity tiers) |

Unchanged in both themes (parent spec: "viridis buckets glow on it
unchanged"): `BUCKET_COLORS`, gold capital stars with navy rim, dim opacities
0.05 (lines) / 0.08 (dots). All flagged for the user's dark calibration
round — expect a round or two, as with Phase 1.

### Panel/chrome CSS

- `index.css` moves panel/card/search/hint colors to CSS variables on
  `:root`, overridden under `[data-theme="dark"]`: warm-white panels → deep
  navy `#0B1533`, dark text → light text, journey-card and search-dropdown
  surfaces follow. Header bar unchanged (navy, white wordmark, gold tagline,
  white mascot — already theme-proof).
- Buttons/selected states stay brand navy with gold accents in both themes;
  in dark, navy-on-navy buttons may need a lighter border or the `#5B7FDB`
  accent — calibration point.

## Mascot rider

### Sprite

- New inline React SVG component (e.g. `web/src/components/RiderSvg.tsx`):
  the C0 train **without** the baked-in route line and station dots — the
  real journey line replaces them. Body, wheels, dot-eyes, smile, dotted
  window line, gold star, per the canonical C0 path data
  (`web/public/logo-mascot.svg`).
- Inline JSX (not a `public/` asset) so the stroke is a prop and follows the
  theme: navy `#003399` on light, cream `#F2EFE9` on dark; star gold
  `#FFCC00` always; wheel/fill hollows use the current land color.
- Size ~36 px wide, screen-fixed (Marker is screen-space).

### Geometry & timing — `web/src/lib/ride.ts` (pure, unit-tested)

- `journeyLegPaths(journey, stationsById)`: per-leg `chaikin(coords, 2)`
  arrays — the exact construction `linesGeoJSON` uses today. **Refactor
  `linesGeoJSON` to consume this helper** so the rider and the rendered line
  can never drift apart (drop-first-point flattening stays in
  `linesGeoJSON`).
- `buildRideTimeline(legPaths, opts)`: cumulative segment distances
  (equirectangular approximation with cos-latitude correction is fine at
  this scale); total moving time = `TRAVERSE_MS` (~7000, the TUNING POINT
  constant) split across legs proportional to length; insert
  `TRANSFER_PAUSE_MS` (500) dwell between legs and `REST_MS` (1000) at the
  destination; loop = modulo total duration.
- `rideStateAt(timeline, tMs)` → `{ lng, lat, bearingDeg, moving }` —
  interpolated position + segment bearing; during dwells, position pins to
  the station and `moving` is false.
- `riderTransform(bearingDeg)` → `{ rotateDeg, mirror }`: rotation relative
  to map-north for `rotationAlignment: "map"`; `mirror: true` (CSS
  `scaleX(-1)`, rotation adjusted accordingly) whenever the heading has a
  westward component, so the right-facing train never rides upside down.

### Wiring

- `MascotRider` logic driven from `Map.tsx`: when `selectedDest` resolves to
  a journey (same `bestJourney` lookup as `syncHighlight`), create one
  `maplibregl.Marker({ element, rotationAlignment: "map", pitchAlignment: "map" })`
  with `pointer-events: none` (never steals clicks from dots), start a
  `requestAnimationFrame` loop calling `setLngLat` + `setRotation` +
  element transform each frame. Tear down (cancel rAF, remove marker) on
  unselect, origin change, and unmount.
- Rebuild the timeline on the same deps as `syncHighlight`
  (`selectedDest`, `reach`, `maxTrains`, `maxMinutes`, `stations`) — a
  maxTrains/maxMinutes change can swap the best journey.
- `prefers-reduced-motion: reduce` → no animation; the mascot parks at the
  destination instead.
- Pan/zoom need no handling: the marker is anchored in lng/lat.

### Housekeeping

- `web/src/lib/highlight.ts` header comment ("thick-line treatment is
  provisional … pending an animated train") is resolved: the thick selected
  line **stays** — it is the rail the mascot rides. Update the comment.

## Testing & verification

- Pure helpers unit-tested in the existing vitest pattern: `resolveTheme`
  matrix, `styleUrl("dark")`, `themeTokens` shape/values, timeline totals
  (traverse + pauses + rest), leg proportionality, `rideStateAt` at
  boundaries (t=0 origin, dwell pins to station, loop wrap), `riderTransform`
  flip quadrants, `journeyLegPaths` ≡ what `linesGeoJSON` renders.
- Marker/rAF and `setStyle`/`transformStyle` wiring stay thin untested glue.
- No screenshot verification; DEV `window.__map` for headless state checks;
  visual verdicts are the user's (expect a dark-calibration round and a
  mascot-speed verdict on the TUNING POINT).
