# Mobile layout — bottom sheet (backlog item AN) — design

Approved by user 2026-07-16 (design round in-session).

## Problem

The site is not adjusted to phones at all (dad feedback, 2026-07-15): the
desktop side panel covers/collides with the map, touch targets are small, and
exploring the map underneath the UI is impossible.

## Decisions (user-approved)

1. **Pattern: bottom sheet.** On mobile the map is fullscreen; all UI collapses
   into a slim bottom bar with a drag handle/arrow that pulls the full panel up
   as a bottom sheet (Google-Maps-style).
2. **Collapsed bar content: active box + context.** The bar always shows the
   active chooser (origin or target search box) in one line; when a destination
   is selected it additionally shows a one-line journey summary (duration,
   number of trains). Always at most one context line.

## Design

- **Breakpoint:** treat viewports ≤ 768 px wide (or coarse pointer +
  small width) as mobile. CSS-first: reuse the existing panel components,
  restyled and re-homed into the sheet — no separate mobile component tree.
- **Sheet states:** collapsed (bar only) / expanded (full panel, map still
  peeking at top). Two states for v1 — no half-open snap point until real
  usage asks for it. State toggles via the drag handle (tap or swipe).
  Plain CSS transform transition; respect `prefers-reduced-motion`.
- **What lives in the expanded sheet:** everything the desktop panel has
  (origin/target boxes, trains=1|2|3 selector, journey details, connection
  tables) in the same order.
- **Map interactions:** selecting a station on the map while collapsed updates
  the bar; the click-disambiguation popup (shipped item AE) must stay within
  the viewport above the bar. Map attribution/zoom controls shift up by the
  bar height.
- **Touch targets:** minimum 44×44 px for the handle, selector buttons, and
  list rows on mobile.
- **Desktop unchanged** above the breakpoint.

## Testing

Component-level (vitest): sheet state toggling, collapsed-bar content rules
(origin-active vs destination-selected), breakpoint class switching. No
screenshot/visual assertions (project rule: verify via data/text). Manual
visual pass is the user's (phone in hand) after deploy.

## Out of scope

- AO's heat strip (its own spec; it renders inside the sheet wherever the
  frequency line renders).
- Half-open snap state, swipe gestures beyond basic drag, PWA/manifest work.
- Desktop layout changes of any kind.
