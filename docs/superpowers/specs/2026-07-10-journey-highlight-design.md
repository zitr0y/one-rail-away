# Selected-journey highlight (backlog item J) — design

Date: 2026-07-10. Approved by user in brainstorming session.

## Problem

When a journey card is open (e.g. Bern→Zürich), the map still shows every reach line at
full strength; the selected journey does not stand out (user feedback 2026-07-10,
backlog item J in `docs/superpowers/feedback-backlog.md`).

## Behavior (user decisions)

While a journey card is open (`selectedDest` set in App):

- The selected journey's line renders **thicker (4px) at full opacity**, keeping its
  normal time-bucket color, drawn **above** all other reach lines.
- All other reach lines **dim strongly to 0.12 opacity** (normal is 0.75).
- Destination dots (`reach-dots`) and grey all-station dots are **unchanged** — they
  stay full-strength click targets for switching journeys.
- Closing the card (× button, Escape, selecting a new origin) restores today's styling.
- Click handling and `pickFeature` precedence are untouched.

**Provisional styling note:** the thick-line treatment is a placeholder to be revisited
when branding (backlog item D) lands — user wants to explore an animated train moving
along the selected route instead.

## Approach (chosen: dedicated highlight layer)

Considered: (A) swap paint expressions on the existing `reach-lines` layer — smallest
diff but z-order within the layer is source-order; (B) dedicated highlight layer
filtered by feature id — static paint, guaranteed z-order, natural attachment point for
the future animated train; (C) `promoteId` + feature-state — hover-style machinery,
overkill for single selection. **Chosen: B.**

## Architecture

- **`web/src/lib/highlight.ts`** (new, pure, vitest-covered):
  - `selectedLineFilter(id: string | null)` → MapLibre filter expression; matches the
    feature whose `id` property equals `id`, matches nothing for `null`.
  - `baseLineOpacity(hasSelection: boolean)` → `0.12` if a selection is active,
    else `0.75` (the current constant moves here so there is one source of truth).
- **`web/src/components/Map.tsx`**:
  - New prop `selectedDest: string | null`.
  - New static layer `reach-lines-selected` added at map load, **between**
    `reach-lines` and `reach-dots`: same `reach-lines` source, `line-width: 4`,
    `line-opacity: 1`, same bucket-color expression, initial filter matches nothing.
  - On `selectedDest` change: `setFilter("reach-lines-selected", …)` +
    `setPaintProperty("reach-lines", "line-opacity", …)`. This runs in its **own
    effect**, separate from `syncData`, so selecting a journey does not trigger the
    `easeTo` re-center.
- **`web/src/App.tsx`**: pass existing `selectedDest` state to `MapView` (one line).

## Edge cases

- **Time slider filters the selected journey out while its card is open** (JourneyCard
  checks `maxTrains` but not `maxMinutes`): base lines still dim; the highlight layer
  simply has nothing to draw. Loosening the slider brings the highlight back. No
  special-casing.
- **Reach cleared / origin switched**: App already resets `selectedDest`; filter and
  opacity are reset alongside for cleanliness (stale filter would be harmless anyway —
  sources go empty).
- The highlighted line is by construction the same journey the card shows: both derive
  from `bestJourney(dest, maxTrains)`.

## Testing

- TDD: vitest for `selectedLineFilter` (expression shape for an id; matches-nothing for
  `null`) and `baseLineOpacity` (both states) before implementation.
- Full web suite + build + lint green before review.
- Visual evaluation is the user's (established convention) — verify via code/test/build
  checks only.
