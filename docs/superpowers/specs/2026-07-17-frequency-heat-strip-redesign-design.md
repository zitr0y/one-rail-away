# Frequency heat strip redesign (backlog AO rework)

**Date:** 2026-07-17
**Status:** Approved design, pre-implementation
**Supersedes the layout of:** `2026-07-16-frequency-viz-design.md` (data model and
pipeline output are unchanged; only the web presentation changes)

## Problem

User verdict on the shipped 7×3 heat strip (backlog item AO): "I like the viz but"
— it must be horizontal (days along the x-axis), the three dayparts must be
clearly labeled morning/afternoon/evening, and the colors must make their meaning
obvious. Additional constraint from this brainstorm: it must stay compact and
glanceable on the mobile bottom sheet, so full-word row labels can't be the only
labeling mechanism.

Scope: fix the three feedback points + polish what they touch. Keep the
click-to-expand behavior, the data shape, and the daypart hour boundaries as-is.

## Design

### Layout (transposed)

- Grid becomes **7 columns (days) × 3 rows (dayparts)**.
- Day abbreviations (existing `WEEKDAYS` labels) run along the **top** as column
  headers; day order still follows the sampled dates.
- Dayparts are rows, top to bottom: **morning, afternoon, evening** (natural
  time-of-day order). Hour boundaries unchanged: morning 0–11, afternoon 12–17,
  evening 18–23.
- Grid template: a narrow label column (~24px) then `repeat(7, 1fr)`. Cells
  ~16–20px tall, 2px gaps, 3px radius.
- The grid remains the single `<button>` that toggles `detailsExpanded` (the
  connection table). The "Sampled timetable evidence, not a promise." note stays
  beneath the legend.

### Row labels: icons always, words when wide

- The label column holds three faint, muted inline SVG icons in the app's style:
  **sunrise** (morning), **full sun** (afternoon), **crescent moon** (evening).
- When the container is wide enough (desktop side panel), the full word
  ("Morning" / "Afternoon" / "Evening") renders next to the icon. On narrow
  widths (mobile bottom sheet) the word is hidden via CSS and only the icon
  column remains. Prefer a container query on the strip's wrapper; a viewport
  media query aligned with the existing mobile-layout breakpoint is an
  acceptable fallback.
- Each row icon carries `title` and `aria-label` with the full word, so the
  label is always available on hover/tap and to screen readers regardless of
  width.
- Width budget: ~24px icon column + 7 cells ≈ 300px total on mobile — fits the
  bottom sheet.

### Colors: brand-blue single-hue ramp

- Replaces the grey→blue ramp. **Deliberately distinct from the map's viridis
  travel-time ramp** so each color system encodes exactly one thing (decision:
  no viridis reuse).
- 5 steps, same CSS-var mechanism (`--frequency-heat-0..4` in `index.css`) and
  same level formula: `count === 0 ? 0 : max(1, ceil(count / maximum × 4))`
  where `maximum` is the max daypart count across the strip.
- Step 0 ("no trains") is a near-surface neutral; steps 1–4 are a light→dark
  progression of the brand EU blue (#003399 family) for light mode.
- Dark mode gets its **own** four steps chosen against the dark surface (not an
  inverted or reused copy), under the existing `[data-theme="dark"]` block.
- Both ramps must pass the dataviz skill's `validate_palette.js` (light and dark
  surface modes) before they're final; record the validator output in the
  implementation notes.

### Legend

- One compact line under the grid: the 5 swatches in a row, "0" at the left end,
  the strip's actual max count at the right end, captioned
  "direct trains / daypart".
- Muted text tokens, small type — present but visually quiet.

### Tooltips + accessibility

- Every cell gets `title="Tue morning: 4 direct trains"` — the same string as
  its existing `aria-label`, which is kept.
- Day headers are real text; daypart identity is icon + title/aria (+ word when
  wide); nothing is encoded by color alone.

### Code shape

- New component **`web/src/components/FrequencyHeatStrip.tsx`** owns the grid,
  header row, icon labels, legend, tooltips, and the bucketing/level logic
  (`DAYPARTS`, `histogramRows()`, level mapping move in with it).
- `TripDetails.tsx` shrinks to rendering `<FrequencyHeatStrip histogram={…}
  expanded={…} onToggle={…} />` plus its existing text fallback when the
  histogram is absent/invalid.
- CSS stays in `index.css` (both theme blocks), same var names.
- Data contract unchanged: `HourlyHistogram = Record<string, number[24]>`,
  optional, with the existing validation and text fallback.

## Testing / verification

- Unit tests for daypart bucketing, level mapping (including all-zero and
  missing-histogram fallback), and legend max computation.
- Palette validator run for both themes; output recorded.
- End-to-end via the `/verify` recipe (headless build + drive, no screenshots);
  final visual judgment by the user on desktop and phone.

## Out of scope

- Any pipeline/reach-file change (histogram format stays).
- Hour-level drill-down, departure-time filter (that's AQ).
- Custom styled tooltip component (native `title` is deliberate).
- Full-screen/tap-to-enlarge mobile view (rejected: breaks at-a-glance use).
