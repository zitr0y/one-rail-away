# Mobile Bottom Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing planner chrome usable on phones by turning it into a two-state bottom sheet over a fullscreen map, while leaving the desktop layout unchanged.

**Architecture:** Keep one React tree for both layouts. `App` will derive a mobile/desktop layout signal, own the collapsed/expanded state, and pass that state to the existing `JourneyPlanner` and `MapView`. The planner will re-home the existing header, station fields, filters, and details inside one sheet-shaped DOM subtree; CSS will perform the responsive layout and transform transition. Small pure helpers will define breakpoint, gesture, summary, class, and map-inset rules. MapLibre camera padding plus mobile-only navigation controls will reserve the visible sheet area for popups and controls.

**Tech Stack:** React 19, TypeScript 6, plain CSS, MapLibre GL 5, Vitest 4, Testing Library.

## Global Constraints

- The approved design at `docs/superpowers/specs/2026-07-16-mobile-layout-design.md` is authoritative.
- Mobile means width `<= 768px`, or a coarse pointer at the bounded “small width” chosen in Planner Note 1. Above those conditions, desktop structure and appearance stay unchanged.
- Reuse the existing `JourneyPlanner`, `StationField`, `StopToggle`, `TimeSlider`, `TripDetails`, header, and logo. Do not render a second mobile-only planner or duplicate either station field.
- The only sheet states are `collapsed` and `expanded`. Do not add a half-open state, velocity physics, spring library, or gesture dependency.
- The collapsed sheet exposes exactly the armed station chooser and zero or one journey-summary line. It must not duplicate TripDetails text or render connection rows in the collapsed bar.
- Tap and one basic vertical swipe on the 44px handle toggle the state. Ignore horizontal movement and sub-threshold pointer movement beyond treating it as a tap.
- Use a plain CSS `transform` transition. Disable that transition under `prefers-reduced-motion: reduce`.
- Mobile touch targets are at least `44px` high and wide where width is applicable: handle, train-count selectors, station-field controls, and selectable result/popup rows.
- Keep the map fullscreen behind the sheet. Keep MapLibre attribution, mobile zoom controls, and click-disambiguation popups above the visible sheet inset.
- Existing `[data-theme="dark"]` tokens remain the source of dark-mode colors; do not introduce hard-coded light sheet surfaces.
- No screenshot, pixel, snapshot, or visual-regression assertions. Tests verify state, roles, classes, visibility, text, and MapLibre padding/control calls; the user performs the phone visual pass.
- Do not push commits. Keep each task's diff within its declared expected surface.
- Baseline recorded after the transfers feature: `cd web && npm test -- --reporter=dot` passes 190 tests across 23 files; `npm run build` succeeds.

---

### Task 1: Define the mobile breakpoint, sheet state, gesture, summary, and inset contracts

**Expected diff surface:**
- Create: `web/src/lib/mobileLayout.ts`
- Create: `web/src/lib/mobileLayout.test.ts`
- No other files.

**Public contracts introduced:**

```ts
export type SheetState = "collapsed" | "expanded";

export const MOBILE_MAX_WIDTH = 768;
export const COARSE_SMALL_MAX_WIDTH = 1024;
export const COLLAPSED_SHEET_PX = 112;
export const COLLAPSED_SHEET_WITH_CONTEXT_PX = 136;
export const EXPANDED_SHEET_VIEWPORT_FRACTION = 0.88;

export function isMobileLayout(width: number, coarsePointer: boolean): boolean;
export function appLayoutClassName(
  mobile: boolean,
  state: SheetState,
  hasContext: boolean,
): string;
export function sheetStateAfterGesture(
  current: SheetState,
  startY: number,
  endY: number,
): SheetState;
export function collapsedJourneySummary(
  dest: Destination | undefined,
  maxTrains: MaxTrains,
): string | null;
export function sheetBottomInsetPx(
  viewportHeight: number,
  state: SheetState,
  hasContext: boolean,
): number;
export function useMobileLayout(): boolean;
```

`useMobileLayout` is the thin browser adapter: initialize from `window.innerWidth` and `window.matchMedia("(pointer: coarse)")`, subscribe to both resize and pointer-query changes, and delegate the decision to `isMobileLayout`. All branching math remains in the pure functions.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan contract verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add nine failing pure tests to `web/src/lib/mobileLayout.test.ts`**

Add these exact Vitest cases (new file: 0 -> 9 tests):

1. `uses_mobile_layout_at_768_pixels_and_below`
   - Table-test widths `320`, `767`, and `768` with `coarsePointer=false`; each returns `true`.
2. `keeps_fine_pointer_layout_desktop_above_768_pixels`
   - Assert widths `769` and `1024` with `coarsePointer=false` return `false`.
3. `uses_mobile_layout_for_a_coarse_pointer_up_to_1024_pixels`
   - Assert widths `769` and `1024` with `coarsePointer=true` return `true`.
4. `keeps_coarse_pointer_layout_desktop_above_1024_pixels`
   - Assert width `1025` with `coarsePointer=true` returns `false`.
5. `returns_breakpoint_and_sheet_state_classes_without_altering_desktop_class`
   - Assert desktop returns exactly `"app"` regardless of sheet state/context.
   - Assert mobile returns `"app mobile-layout sheet-collapsed"` or `"app mobile-layout sheet-expanded"`, adding `"sheet-has-context"` only for the collapsed-context case.
6. `maps_handle_taps_and_vertical_swipes_to_the_two_sheet_states`
   - Use a `32px` threshold: a tap toggles, an upward swipe opens, and a downward swipe closes.
7. `ignores_horizontal_or_subthreshold_drag_direction_as_a_new_snap_state`
   - Since only Y coordinates enter the helper, assert a `31px` move follows tap toggling and every return value is one of the two `SheetState` literals.
8. `formats_zero_or_one_collapsed_journey_context_line`
   - Assert no destination and no eligible journey return `null`; a 240-minute/two-train journey returns exactly `"4 h · 2 trains"`; a 125-minute/one-train journey returns exactly `"2 h 5 min · nonstop"`.
9. `computes_sheet_bottom_insets_for_collapsed_context_and_expanded_states`
   - At `viewportHeight=800`, assert collapsed/no-context is `112`, collapsed/context is `136`, and expanded is `704` (`800 * 0.88`, rounded).

Use synthetic `Destination` objects only. Do not involve DOM, CSS, MapLibre, or API fixtures in this file.

- [ ] **Step 2: Run the focused test and confirm the expected failure**

```bash
cd web
npx vitest run src/lib/mobileLayout.test.ts
```

Expected before implementation: collection fails because `./mobileLayout` does not exist. Do not proceed if the failure is unrelated.

- [ ] **Step 3: Implement the pure rules and browser adapter**

In `mobileLayout.ts`:

1. Import `bestJourney` and the existing `Destination`/`MaxTrains` types; do not duplicate journey-selection logic.
2. Implement the breakpoint as `width <= 768 || (coarsePointer && width <= 1024)`.
3. Keep desktop's class exactly `app`; sheet-state classes are mobile-only.
4. Use a module constant `SWIPE_THRESHOLD_PX = 32`. `endY <= startY - 32` opens, `endY >= startY + 32` collapses, and smaller movement toggles the current state.
5. Format the summary from `bestJourney(dest, maxTrains)`: existing hour/minute style, followed by `nonstop` for one train or `<n> trains` otherwise. Return one string or `null`, never a React node array.
6. Keep the sheet inset constants aligned with Task 4's CSS custom properties. Round the expanded viewport product to an integer.
7. In the hook cleanup, remove every resize/media-query listener it registered. Do not write layout classes to `document.body`; `App` owns its class.

- [ ] **Step 4: Run the focused tests**

```bash
cd web
npx vitest run src/lib/mobileLayout.test.ts
```

Expected: `9 passed`.

---

### Task 2: Re-home the existing header and planner controls into one accessible two-state sheet

**Expected diff surface:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/JourneyPlanner.tsx`
- Modify: `web/src/components/StationField.tsx`
- Create: `web/src/components/JourneyPlanner.test.tsx`
- No other files.

**Component contract after this task:**

```ts
// JourneyPlanner additions
mobile: boolean;
sheetState: SheetState;
collapsedSummary: string | null;
header: ReactNode;
onSheetStateChange: (state: SheetState) => void;
```

The handle is a real `<button>` with `aria-expanded`, `aria-controls`, and a state-specific accessible name. The existing fields remain the same two `StationField` instances. Mobile collapsed visibility is expressed with `hidden`/ARIA plus CSS classes, so Testing Library can verify the same semantics users receive without loading CSS in jsdom.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan contract verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Install the requested component-test helper**

```bash
cd web
npm install --save-dev @testing-library/react
```

Commit neither generated caches nor `node_modules`; only `package.json` and `package-lock.json` belong in the diff.

- [ ] **Step 2: Add seven failing Testing Library cases**

Create `web/src/components/JourneyPlanner.test.tsx` with jsdom and a small controlled harness that owns `sheetState`. Mock `../lib/api` so no test issues a request. Reuse synthetic stations/destinations and Testing Library's `render`, `screen`, `within`, and `fireEvent`.

Add these exact cases (new file: 0 -> 7 tests):

1. `starts_collapsed_on_mobile_and_toggles_open_and_closed_by_handle_tap`
   - Start the harness at `collapsed`; assert the handle reports `aria-expanded="false"`.
   - Click once and assert expanded class/name/ARIA; click again and assert collapsed.
2. `opens_on_upward_swipe_and_collapses_on_downward_swipe`
   - Fire pointer down/up at `200 -> 150`, then `150 -> 200`, and assert the two state transitions.
3. `collapsed_bar_shows_only_the_active_origin_chooser_before_an_origin_exists`
   - With `armed="from"`, assert the Start field is available, the To field is hidden, selector/slider/details are hidden, and there is no summary status line.
4. `collapsed_bar_shows_the_active_destination_chooser_and_one_journey_summary`
   - Supply origin, destination, and a two-train 240-minute journey with `armed="to"`; assert only the To chooser is available and exactly one status line says `4 h · 2 trains`.
5. `collapsed_bar_keeps_one_summary_when_the_origin_chooser_is_rearmed`
   - With the same selected destination but `armed="from"`, assert the Start chooser replaces To and `getAllByRole("status")` still has length one.
6. `expanded_sheet_reveals_the_existing_header_selector_slider_and_trip_details_in_order`
   - Expand and assert the supplied header, both fields, train selector, travel-time slider, and journey heading are visible.
   - Compare DOM positions to prove header -> fields -> selector -> slider -> details; do not snapshot markup.
7. `desktop_mode_hides_the_sheet_handle_and_keeps_all_existing_panel_controls_available`
   - Render `mobile=false`; assert the handle is absent from the accessibility tree and both fields, selector, slider, and eligible details remain available regardless of the stored sheet state.

- [ ] **Step 3: Run the component test and confirm the expected failures**

```bash
cd web
npx vitest run src/components/JourneyPlanner.test.tsx
```

Expected before implementation: the new mobile/sheet contract and handle/summary markup are absent. Do not proceed if failures are caused by an unmocked API or invalid synthetic data.

- [ ] **Step 4: Lift layout and sheet state into `App`**

In `App.tsx`:

1. Call `useMobileLayout()` and add `sheetState`, initialized to `"collapsed"`.
2. Collapse whenever the layout changes from desktop to mobile; do not force an expanded/collapsed class while desktop.
3. Derive `collapsedSummary = collapsedJourneySummary(dest, maxTrains)` and `hasContext = collapsedSummary !== null`.
4. Replace the literal `.app` class with `appLayoutClassName(mobile, sheetState, hasContext)`.
5. Pass the same state/context into `JourneyPlanner`; Task 3 will pass it to `MapView` for camera padding.
6. Move the existing header JSX, unchanged in content/logo/theme behavior, through the planner's `header` slot. This is a relocation of the one header node, not a desktop/mobile duplicate. Wrap the slot in `.sheet-header`; Task 4 makes that wrapper `display: contents` and the nested header viewport-fixed on desktop so nesting does not change its current coordinates.

- [ ] **Step 5: Add the controlled handle and visibility semantics to `JourneyPlanner`**

Keep the existing child order and callbacks. Add only the mobile chrome around them:

1. The handle is the first sheet-flow child and has a decorative drag pill/arrow beneath its accessible button label.
2. Record `clientY` on pointer down and call `sheetStateAfterGesture` on pointer up. A click without a preceding completed pointer gesture toggles once; suppress the synthetic click after a pointer-up decision so one gesture cannot toggle twice.
3. Wrap the passed header so it is hidden only while mobile+collapsed. It remains in normal accessibility order while expanded and retains desktop behavior.
4. Add `hidden?: boolean` to `StationField`; forward it to the root element. In mobile+collapsed mode, hide the unarmed field and its matching gutter/swap control. Never unmount either field.
5. Group selector, slider, dividers, and details in one `id="planner-sheet-content"` region hidden only while mobile+collapsed.
6. Render the summary as one `<p role="status" className="sheet-context">` only when mobile+collapsed and `collapsedSummary` is non-null. Add `title={collapsedSummary}` for clipped text; do not split the summary into multiple elements/lines.
7. Preserve all existing `JourneyPlanner` props, order, callbacks, and TripDetails eligibility conditions.

- [ ] **Step 6: Run the focused component and existing detail tests**

```bash
cd web
npx vitest run \
  src/components/JourneyPlanner.test.tsx \
  src/components/TripDetails.test.tsx
```

Expected: `14 passed` (`JourneyPlanner.test.tsx` 0 -> 7; `TripDetails.test.tsx` remains 7 -> 7).

---

### Task 3: Reserve mobile map space for zoom controls, attribution, and click popups

**Expected diff surface:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/components/Map.test.tsx`
- No other files.

**Map contract after this task:**

```ts
// MapView additions
mobile: boolean;
sheetState: SheetState;
sheetHasContext: boolean;
```

MapLibre camera padding is the behavioral guarantee for popup auto-pan. CSS in Task 4 moves the visible control containers by the same inset. Add one `NavigationControl` only in mobile layout because the current app has no explicit zoom control; do not add it to desktop.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan contract verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add two failing cases to `web/src/components/Map.test.tsx`**

Extend the MapLibre mock with `NavigationControl`, `addControl`, `removeControl`, and `setPadding` spies. Update existing renders with explicit desktop sheet props.

Add these exact cases (`Map.test.tsx`: 2 -> 4 tests):

1. `adds_navigation_control_and_collapsed_padding_only_in_mobile_layout`
   - Render/load mobile+collapsed without context at an `800px` viewport.
   - Assert one NavigationControl is added at `bottom-right` and final padding is `{ top: 0, right: 0, bottom: 112, left: 0 }`.
   - A desktop render must add no navigation control and use bottom padding `0`.
2. `updates_camera_padding_for_expanded_sheet_and_restores_zero_on_desktop`
   - Re-render the same loaded map from mobile collapsed+context to expanded and assert bottom padding changes `136 -> 704`.
   - Re-render as desktop and assert the mobile control is removed and bottom padding returns to `0`.

Do not inspect canvas pixels or popup coordinates. The tested padding is what MapLibre uses when auto-panning its existing city-origin and overlap-station popups.

- [ ] **Step 2: Run and confirm the focused failures**

```bash
cd web
npx vitest run src/components/Map.test.tsx
```

Expected before implementation: the mock never receives navigation-control or padding calls.

- [ ] **Step 3: Synchronize mobile map chrome in `MapView`**

1. Add a ref for the single `NavigationControl` instance. Never add more than one across prop changes.
2. Add a `syncMobileLayout` helper/effect that calls `sheetBottomInsetPx(window.innerHeight, sheetState, sheetHasContext)` for mobile and zero for desktop, then calls `map.setPadding` with all four sides explicit.
3. Add the control at `bottom-right` when entering mobile; remove it when returning to desktop. Leave MapLibre's existing attribution source/control behavior untouched.
4. Call the sync after the map's load path assigns `map.current`, because prop effects before load currently no-op just like the existing station syncs.
5. Listen for window/visual-viewport height changes while mobile and recompute expanded padding; clean up those listeners. Do not resize or crop the map container.
6. Pass `mobile`, `sheetState`, and `sheetHasContext` from `App` to `MapView` and update every test render explicitly.
7. On unmount, remove any mobile navigation control/listeners before removing the map.

- [ ] **Step 4: Run map and popup tests**

```bash
cd web
npx vitest run \
  src/components/Map.test.tsx \
  src/components/MapPopup.test.tsx
```

Expected: `7 passed` (`Map.test.tsx` 2 -> 4; `MapPopup.test.tsx` remains 3 -> 3).

---

### Task 4: Apply the mobile bottom-sheet layout and touch rules in CSS

**Expected diff surface:**
- Modify: `web/src/index.css`
- No other files.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan contract verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Preserve desktop selectors and introduce sheet variables**

Preserve the current desktop geometry as the default. Because Task 2 nests the single header under the positioned panel, set `.sheet-header { display: contents; }` and make its `.header-bar` `position: fixed` at the existing `top: 0; left: 0; right: 0`; this keeps the same viewport coordinates rather than making the header absolute to the panel. Add all actual mobile layout behavior only below `.mobile-layout` selectors so `.app` without that class retains the present header geometry, panel at `top: 64px; left: 16px; width: 340px`, and current sizing.

Define and comment these matching CSS values on `.mobile-layout`:

```css
--sheet-collapsed-height: 112px;
--sheet-collapsed-context-height: 136px;
--sheet-expanded-height: 88dvh;
--sheet-visible-height: var(--sheet-collapsed-height);
```

Set `.sheet-has-context` to the context height and `.sheet-expanded` to `88dvh`. Add `env(safe-area-inset-bottom)` to sheet padding/control offsets without changing the TypeScript contract constants.

- [ ] **Step 2: Turn the one planner DOM tree into the sheet**

Under `.mobile-layout` only:

1. Keep the map container fullscreen (`inset: 0` remains unchanged).
2. Make `.panel` fixed to the viewport bottom, full width, `height: 88dvh`, with top corners rounded, square bottom corners, safe-area bottom padding, a bounded z-index above the map, and vertical overflow inside the expanded content.
3. Expanded uses `transform: translateY(0)`. Collapsed uses `transform: translateY(calc(100% - var(--sheet-visible-height)))` so the map remains visible behind it.
4. Transition only `transform` with a short ease (about `220ms`). Under `@media (prefers-reduced-motion: reduce)`, set transition duration to `0.01ms` or `none`.
5. Make `.sheet-handle` the full-width 44px first row, with a centered pill and state arrow. Keep focus-visible styling and do not make the decorative pill its own button.
6. In expanded mode, let the relocated `.header-bar` participate in sheet flow and keep logo, tagline, and theme toggle. Size the logo compactly enough that the header stays one row; allow the tagline to truncate rather than overlap.
7. Keep the existing planner field/selector/slider/details order and use scrolling inside the sheet body. Do not make the entire sheet itself horizontally scrollable.
8. Keep `.sheet-context` to one line with `white-space: nowrap; overflow: hidden; text-overflow: ellipsis`.

- [ ] **Step 3: Enforce mobile touch targets without changing desktop density**

Under `.mobile-layout` set `min-height: 44px` on:

- `.station-field input`, `.station-field .field-value`, and `.station-field .field-clear` (the clear control also gets `min-width: 44px`);
- `.stop-toggle button`;
- `.station-field li button` and disabled result rows;
- `.city-origin-popup button` and `.overlap-station-popup button`;
- `.theme-toggle` (also `min-width: 44px`).

The handle is already `44px`. Do not globally enlarge desktop controls or the existing booking buttons, which already exceed the minimum.

- [ ] **Step 4: Shift MapLibre chrome and bound popup content**

1. Move `.maplibregl-ctrl-bottom-left` and `.maplibregl-ctrl-bottom-right` upward by `calc(var(--sheet-visible-height) + env(safe-area-inset-bottom) + 8px)` in mobile layout. This shifts attribution and the Task 3 zoom control together.
2. Keep control transitions synchronized with the sheet transform; suppress them under reduced motion.
3. Give `.city-origin-map-popup` and `.overlap-station-map-popup` a mobile max width based on `100vw - 24px` and a max content height based on `100dvh - var(--sheet-visible-height) - safe area - 24px`, with internal vertical overflow if necessary.
4. Retain the existing theme token colors, popup tips, reachable/unreachable styling, and text labels. Camera padding from Task 3 supplies the actual above-sheet auto-pan boundary.

- [ ] **Step 5: Run all focused non-visual feature tests**

```bash
cd web
npx vitest run \
  src/lib/mobileLayout.test.ts \
  src/components/JourneyPlanner.test.tsx \
  src/components/Map.test.tsx \
  src/components/MapPopup.test.tsx \
  src/components/TripDetails.test.tsx
```

Expected: `30 passed` (9 + 7 + 4 + 3 + 7). No CSS screenshot assertion is added.

---

### Task 5: Run the complete web verification and audit the diff

**Expected diff surface:**
- None. This is verification only; do not edit files to make commands pass.

**Implementation guard:** if a verification command fails, do NOT modify unrelated code, relax assertions, or add exceptions — STOP and report the failing command and contradiction.

- [ ] **Step 1: Run the full web test suite**

```bash
cd web
npm test -- --reporter=dot
```

Expected: `208 passed` across `25` files (baseline 190/23 plus 18 tests in two new files and one expanded file).

- [ ] **Step 2: Run lint and the production build**

```bash
cd web
npm run lint
npm run build
```

Expected: lint exits clean and TypeScript/Vite build succeeds.

- [ ] **Step 3: Audit scope and whitespace**

```bash
git diff --name-only
git diff --check
```

Expected implementation/test files only:

```text
web/package-lock.json
web/package.json
web/src/App.tsx
web/src/components/JourneyPlanner.test.tsx
web/src/components/JourneyPlanner.tsx
web/src/components/Map.test.tsx
web/src/components/Map.tsx
web/src/components/StationField.tsx
web/src/index.css
web/src/lib/mobileLayout.test.ts
web/src/lib/mobileLayout.ts
```

Also expect this plan file if implementation occurs in the same worktree. Confirm there is no second mobile planner/header tree, no screenshot artifacts or visual-test dependency, no generated `web/dist/*`, and no backend/data changes.

- [ ] **Step 4: Hand off the manual phone visual pass**

Do not automate this step. Report that tests/lint/build are green and ask the user to verify on a real phone: collapsed/expanded motion, both themes, safe-area spacing, map peeking, selector/result-row touch comfort, popup placement near the bottom edge, and portrait/landscape rotation.

## Expected Test Delta

- Web: +18 cases, 190 -> 208; test files 23 -> 25.
  - `web/src/lib/mobileLayout.test.ts`: +9 (new file, 0 -> 9).
  - `web/src/components/JourneyPlanner.test.tsx`: +7 (new file, 0 -> 7).
  - `web/src/components/Map.test.tsx`: +2 (2 -> 4).
  - `web/src/components/MapPopup.test.tsx`: unchanged (3 -> 3).
  - `web/src/components/TripDetails.test.tsx`: unchanged (7 -> 7).
- No Python tests change.

## Planner Notes

1. The spec says “coarse pointer + small width” but gives no second numeric bound. This plan chooses `1024px`: it covers small tablets/touch devices without converting wide touch laptops to the sheet. The authoritative `<= 768px` rule remains unconditional.
2. The spec says all UI collapses but does not explicitly place the existing global header/logo. This plan relocates the one header node into the shared sheet flow: hidden in the collapsed bar, visible at the top of the expanded sheet, and fixed exactly as today on desktop. It does not create separate mobile branding.
3. `MapView` currently relies on MapLibre's attribution behavior and creates no `NavigationControl`. To satisfy “attribution+zoom controls shift above the bar” without altering desktop, this plan adds one bottom-right zoom control only while mobile and shifts the whole bottom control corner.
4. Journey-summary wording is not prescribed. This plan mirrors existing TripDetails duration formatting and uses only `nonstop` or `<n> trains`; frequency and leg details stay out of the one context line.
5. Exact bar/peek dimensions are not prescribed. This plan chooses 112px collapsed, 136px with context, and 88dvh expanded (12dvh of map peeking). They are centralized/tested so a later phone calibration is one deliberate constants change, not scattered CSS.
6. “Basic drag” is interpreted as a 32px vertical pointer displacement with no momentum/velocity model. Sub-threshold movement acts like a tap; there is no half-open state.
7. MapLibre camera padding is used because CSS alone can move visible controls but cannot make popup auto-pan aware of the overlay. Tests assert the padding/control contract; the user remains responsible for the real-phone visual judgment required by the spec.
