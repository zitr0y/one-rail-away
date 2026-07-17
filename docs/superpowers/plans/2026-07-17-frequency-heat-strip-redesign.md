# Frequency Heat Strip Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transpose the trip-details frequency heat strip to days-on-x-axis with icon+word daypart labels, a brand-blue validated color ramp, a legend, and cell tooltips, extracted into its own component.

**Architecture:** New `FrequencyHeatStrip` component owns the transposed grid, daypart icons, legend, and the histogram bucketing/level logic (moved out of `TripDetails.tsx`). `TripDetails` keeps its text fallback and the expand/collapse state, passing rows + toggle down. All styling stays in `index.css` CSS vars/classes; the mobile word-hiding rides the existing `.mobile-layout` class.

**Tech Stack:** React 19 + TypeScript, Vitest + Testing Library (jsdom), plain CSS in `web/src/index.css`.

**Spec:** `docs/superpowers/specs/2026-07-17-frequency-heat-strip-redesign-design.md`

## Global Constraints

- Data contract unchanged: `Destination["histogram"]` is `Record<string, number[]>` (24 bins), optional; invalid/absent → text fallback (`frequencyLabel`).
- Daypart hour boundaries unchanged: morning 0–11, afternoon 12–17, evening 18–23.
- Level formula unchanged: `count === 0 ? 0 : Math.max(1, Math.ceil(count / maximum * 4))`, `maximum` = max daypart count across the strip.
- CSS var names unchanged: `--frequency-heat-0..4` in `:root` and `[data-theme="dark"]`.
- Validated ramp hexes (dataviz `validate_palette.js --ordinal`, ALL CHECKS PASS 2026-07-17 — do not substitute):
  - Light (surface `#ffffff`): keep `--frequency-heat-0: #f3f4f6`; steps 1–4 = `#9DB2E5`, `#7089D3`, `#3B5CB9`, `#003399`.
  - Dark (surface `#0B1533`): keep `--frequency-heat-0: #1a2a55`; steps 1–4 = `#3A5495`, `#5C79BE`, `#85A2DF`, `#B4C8F4`.
- Tooltip/aria copy uses "direct trains" (e.g. `Tue morning: 4 direct trains`), replacing the old "connections" wording.
- The grid stays a single `<button>` toggling the connection table; the note "Sampled timetable evidence, not a promise." stays beneath the legend.
- Run all web commands from `web/`: `npm test`, `npx oxlint`, `npm run build`.

## File Structure

- **Create** `web/src/components/FrequencyHeatStrip.tsx` — component: transposed grid, icons, legend, note; exports `histogramRows` + `HistogramRow` for TripDetails and tests.
- **Create** `web/src/components/FrequencyHeatStrip.test.tsx` — unit tests (bucketing, levels, structure, tooltips, legend, toggle).
- **Modify** `web/src/components/TripDetails.tsx` — delete moved logic/JSX, mount the new component.
- **Modify** `web/src/components/TripDetails.test.tsx` — retarget histogram tests at integration level.
- **Modify** `web/src/index.css` — new tokens + transposed grid/legend/icon styles, `.mobile-layout` word-hiding.

---

### Task 1: FrequencyHeatStrip component + tests, integrated into TripDetails

**Files:**
- Create: `web/src/components/FrequencyHeatStrip.tsx`
- Create: `web/src/components/FrequencyHeatStrip.test.tsx`
- Modify: `web/src/components/TripDetails.tsx` (remove lines 16–40 logic block and the strip JSX at lines 107–124)
- Modify: `web/src/components/TripDetails.test.tsx`

**Interfaces:**
- Consumes: `Destination` from `../lib/types`.
- Produces: `histogramRows(histogram: Destination["histogram"]): HistogramRow[] | null` (named export), `interface HistogramRow { date: string; weekday: string; dayparts: number[] }` (named export), and default export `FrequencyHeatStrip({ rows, expanded, legsId, onToggle }: { rows: HistogramRow[]; expanded: boolean; legsId: string; onToggle: () => void })`. Task 2's CSS targets the exact class names in this markup.

- [ ] **Step 1: Write the failing tests**

Create `web/src/components/FrequencyHeatStrip.test.tsx`:

```tsx
// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import FrequencyHeatStrip, { histogramRows } from "./FrequencyHeatStrip";

afterEach(cleanup);

const bins = (fill: Record<number, number> = {}): number[] =>
  Array.from({ length: 24 }, (_, hour) => fill[hour] ?? 0);

describe("histogramRows", () => {
  it("buckets 24 hour bins into morning/afternoon/evening per sorted date", () => {
    const rows = histogramRows({
      "2026-07-21": bins({ 6: 2, 13: 1, 20: 3 }), // a Tuesday
      "2026-07-20": bins({ 0: 1, 11: 1 }),        // a Monday
    })!;
    expect(rows.map((row) => row.weekday)).toEqual(["Mon", "Tue"]);
    expect(rows[0].dayparts).toEqual([2, 0, 0]);
    expect(rows[1].dayparts).toEqual([2, 1, 3]);
  });

  it("rejects missing, empty, wrong-length, and negative histograms", () => {
    expect(histogramRows(undefined)).toBeNull();
    expect(histogramRows({})).toBeNull();
    expect(histogramRows({ "2026-07-20": [1, 2, 3] })).toBeNull();
    expect(histogramRows({ "2026-07-20": bins({ 5: -1 }) })).toBeNull();
  });
});

describe("FrequencyHeatStrip", () => {
  const rows = histogramRows({
    "2026-07-20": bins({ 8: 4 }),
    "2026-07-21": bins({ 8: 1, 14: 2 }),
  })!;

  const renderStrip = (onToggle = vi.fn()) =>
    render(<FrequencyHeatStrip rows={rows} expanded={false} legsId="legs" onToggle={onToggle} />);

  it("renders days as column headers and dayparts as icon-labelled rows", () => {
    const { container } = renderStrip();
    const days = [...container.querySelectorAll(".frequency-heat-day")].map((el) => el.textContent);
    expect(days).toEqual(["Mon", "Tue"]);
    const labels = [...container.querySelectorAll(".frequency-heat-daypart")];
    expect(labels).toHaveLength(3);
    expect(labels.map((el) => el.getAttribute("title"))).toEqual(["Morning", "Afternoon", "Evening"]);
    expect(labels.every((el) => el.querySelector("svg.frequency-daypart-icon"))).toBe(true);
    expect([...container.querySelectorAll(".frequency-daypart-word")].map((el) => el.textContent))
      .toEqual(["Morning", "Afternoon", "Evening"]);
    expect(container.querySelectorAll(".frequency-heat-cell")).toHaveLength(6);
  });

  it("assigns levels relative to the busiest daypart and titles every cell", () => {
    const { container } = renderStrip();
    const cells = [...container.querySelectorAll(".frequency-heat-cell")];
    // Row-major by daypart: Mon/Tue morning, Mon/Tue afternoon, Mon/Tue evening.
    expect(cells[0].className).toContain("frequency-heat-level-4"); // 4 of max 4
    expect(cells[1].className).toContain("frequency-heat-level-1"); // 1 of max 4
    expect(cells[3].className).toContain("frequency-heat-level-2"); // 2 of max 4
    expect(cells[4].className).toContain("frequency-heat-level-0"); // 0
    expect(cells[0].getAttribute("title")).toBe("Mon morning: 4 direct trains");
    expect(cells[0].getAttribute("aria-label")).toBe("Mon morning: 4 direct trains");
  });

  it("shows a legend from 0 to the max count with 5 swatches", () => {
    const { container } = renderStrip();
    const legend = container.querySelector(".frequency-heat-legend")!;
    expect(legend.querySelectorAll(".frequency-heat-swatch")).toHaveLength(5);
    const counts = [...legend.querySelectorAll(".frequency-heat-legend-count")].map((el) => el.textContent);
    expect(counts).toEqual(["0", "4"]);
    expect(legend.textContent).toContain("direct trains / daypart");
  });

  it("fires onToggle and wires aria expansion state", () => {
    const onToggle = vi.fn();
    const { container } = renderStrip(onToggle);
    const button = container.querySelector<HTMLButtonElement>(".frequency-heat-strip")!;
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe("legs");
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("keeps the sampling note beneath the strip", () => {
    const { container } = renderStrip();
    expect(container.querySelector(".frequency-heat-note")!.textContent)
      .toBe("Sampled timetable evidence, not a promise.");
  });
});
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd web && npx vitest run src/components/FrequencyHeatStrip.test.tsx`
Expected: FAIL — cannot resolve `./FrequencyHeatStrip`.

- [ ] **Step 3: Implement the component**

Create `web/src/components/FrequencyHeatStrip.tsx`:

```tsx
import { Fragment, type CSSProperties } from "react";
import type { Destination } from "../lib/types";

const DAYPARTS = [
  { name: "morning", label: "Morning", start: 0, end: 12 },
  { name: "afternoon", label: "Afternoon", start: 12, end: 18 },
  { name: "evening", label: "Evening", start: 18, end: 24 },
] as const;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export interface HistogramRow {
  date: string;
  weekday: string;
  dayparts: number[];
}

export function histogramRows(histogram: Destination["histogram"]): HistogramRow[] | null {
  if (!histogram) return null;
  const entries = Object.entries(histogram).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length || entries.some(([, bins]) => !Array.isArray(bins) || bins.length !== 24
    || bins.some((count) => !Number.isFinite(count) || count < 0))) return null;
  return entries.map(([date, bins]) => ({
    date,
    weekday: WEEKDAYS[new Date(`${date}T00:00:00Z`).getUTCDay()],
    dayparts: DAYPARTS.map(({ start, end }) => bins.slice(start, end)
      .reduce((total, count) => total + count, 0)),
  }));
}

/** Faint daypart glyphs: sunrise, sun, crescent moon. Stroke follows text color. */
function DaypartIcon({ part }: { part: (typeof DAYPARTS)[number]["name"] }) {
  const shared = {
    className: "frequency-daypart-icon",
    viewBox: "0 0 16 16",
    "aria-hidden": true,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round",
  } as const;
  if (part === "morning") {
    return (
      <svg {...shared}>
        <path d="M4.5 11a3.5 3.5 0 0 1 7 0" />
        <line x1="1.5" y1="11" x2="14.5" y2="11" />
        <line x1="8" y1="2.5" x2="8" y2="4.5" />
        <line x1="3.4" y1="5.4" x2="4.8" y2="6.8" />
        <line x1="12.6" y1="5.4" x2="11.2" y2="6.8" />
      </svg>
    );
  }
  if (part === "afternoon") {
    return (
      <svg {...shared}>
        <circle cx="8" cy="8" r="3" />
        <line x1="8" y1="1.5" x2="8" y2="3" />
        <line x1="8" y1="13" x2="8" y2="14.5" />
        <line x1="1.5" y1="8" x2="3" y2="8" />
        <line x1="13" y1="8" x2="14.5" y2="8" />
        <line x1="3.4" y1="3.4" x2="4.5" y2="4.5" />
        <line x1="11.5" y1="11.5" x2="12.6" y2="12.6" />
        <line x1="3.4" y1="12.6" x2="4.5" y2="11.5" />
        <line x1="11.5" y1="4.5" x2="12.6" y2="3.4" />
      </svg>
    );
  }
  return (
    <svg {...shared}>
      <path d="M12.9 9.7A5.4 5.4 0 1 1 6.3 3.1a4.3 4.3 0 0 0 6.6 6.6Z" />
    </svg>
  );
}

interface Props {
  rows: HistogramRow[];
  expanded: boolean;
  legsId: string;
  onToggle: () => void;
}

export default function FrequencyHeatStrip({ rows, expanded, legsId, onToggle }: Props) {
  const maximum = Math.max(...rows.flatMap((row) => row.dayparts));
  return (
    <>
      <button type="button" className="frequency-heat-strip"
              aria-label="Toggle connection details" aria-expanded={expanded}
              aria-controls={legsId} onClick={onToggle}>
        <span className="frequency-heat-grid"
              style={{ "--heat-days": rows.length } as CSSProperties}>
          <span className="frequency-heat-corner" aria-hidden="true" />
          {rows.map((row) => (
            <span className="frequency-heat-day" key={row.date}>{row.weekday}</span>
          ))}
          {DAYPARTS.map((daypart, index) => (
            <Fragment key={daypart.name}>
              <span className="frequency-heat-daypart" title={daypart.label}
                    aria-label={daypart.label}>
                <DaypartIcon part={daypart.name} />
                <span className="frequency-daypart-word" aria-hidden="true">{daypart.label}</span>
              </span>
              {rows.map((row) => {
                const count = row.dayparts[index];
                const level = count === 0 ? 0 : Math.max(1, Math.ceil(count / maximum * 4));
                const detail = `${row.weekday} ${daypart.name}: ${count} direct trains`;
                return <span className={`frequency-heat-cell frequency-heat-level-${level}`}
                             title={detail} aria-label={detail} key={row.date} />;
              })}
            </Fragment>
          ))}
        </span>
        <span className="frequency-heat-legend">
          <span className="frequency-heat-legend-count">0</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <span className={`frequency-heat-swatch frequency-heat-level-${level}`}
                  aria-hidden="true" key={level} />
          ))}
          <span className="frequency-heat-legend-count">{maximum}</span>
          <span className="frequency-heat-legend-caption">direct trains / daypart</span>
        </span>
      </button>
      <p className="frequency-heat-note">Sampled timetable evidence, not a promise.</p>
    </>
  );
}
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd web && npx vitest run src/components/FrequencyHeatStrip.test.tsx`
Expected: PASS (all).

- [ ] **Step 5: Integrate into TripDetails**

In `web/src/components/TripDetails.tsx`:

1. Delete the `DAYPARTS`, `WEEKDAYS`, `HistogramRow`, and `histogramRows` block (current lines 16–40).
2. Add the import: `import FrequencyHeatStrip, { histogramRows } from "./FrequencyHeatStrip";`
3. Replace the strip JSX (current lines 107–124, the `{rows && <>…</>}` block containing the old `<button className="frequency-heat-strip">` and the note `<p>`) with:

```tsx
      {rows && (
        <FrequencyHeatStrip rows={rows} expanded={detailsExpanded} legsId={legsId}
                            onToggle={() => setDetailsExpanded((expanded) => !expanded)} />
      )}
```

`rows`, `maximum` usage: the `maximum` computation at line 80 moves into the component — delete `const maximum = …` from TripDetails. Everything else (fallback `frequencyLabel`, `legs` hidden logic) stays unchanged.

- [ ] **Step 6: Update TripDetails tests**

In `web/src/components/TripDetails.test.tsx`, the `"TripDetails frequency histogram"` describe block:
- The level-class assertions (`frequency-heat-level-*`) and the strip-toggle test still target `.frequency-heat-strip` and stay valid — run them; only fix them if the markup change broke a selector (e.g. cells are now `span`s inside `.frequency-heat-grid`).
- If any assertion checks the old aria copy `… connections`, change the expected string to the new `… direct trains` wording.
- The no-histogram fallback test (`expect(markup).not.toContain("frequency-heat-strip")`) stays as-is.

- [ ] **Step 7: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS (all files, including the untouched suites).

- [ ] **Step 8: Lint and commit**

```bash
cd web && npx oxlint
cd .. && git add web/src/components/FrequencyHeatStrip.tsx web/src/components/FrequencyHeatStrip.test.tsx web/src/components/TripDetails.tsx web/src/components/TripDetails.test.tsx
git commit -m "feat(web): extract transposed FrequencyHeatStrip with icons, legend, tooltips (AO)"
```

---

### Task 2: CSS — transposed grid, tokens, legend, mobile word-hiding

**Files:**
- Modify: `web/src/index.css` (tokens at lines 50–54 and 69–73; strip styles at lines 256–272)

**Interfaces:**
- Consumes: class names from Task 1's markup (`.frequency-heat-grid`, `.frequency-heat-corner`, `.frequency-heat-day`, `.frequency-heat-daypart`, `.frequency-daypart-icon`, `.frequency-daypart-word`, `.frequency-heat-cell`, `.frequency-heat-level-0..4`, `.frequency-heat-legend`, `.frequency-heat-swatch`, `.frequency-heat-legend-count`, `.frequency-heat-legend-caption`, `.frequency-heat-note`) and the `--heat-days` var.
- Produces: nothing consumed later.

- [ ] **Step 1: Replace the ramp tokens**

In `:root` (lines 50–54), replace the four non-zero steps:

```css
  --frequency-heat-0: #f3f4f6;
  --frequency-heat-1: #9DB2E5;
  --frequency-heat-2: #7089D3;
  --frequency-heat-3: #3B5CB9;
  --frequency-heat-4: #003399;
```

In `[data-theme="dark"]` (lines 69–73):

```css
  --frequency-heat-0: #1a2a55;
  --frequency-heat-1: #3A5495;
  --frequency-heat-2: #5C79BE;
  --frequency-heat-3: #85A2DF;
  --frequency-heat-4: #B4C8F4;
```

- [ ] **Step 2: Replace the strip layout styles**

Replace the block at lines 261–272 (`.frequency-heat-row` through `.frequency-heat-note`) — keeping `.frequency-heat-strip` (256–259) and its `:focus-visible` rule — with:

```css
.trip-details .frequency-heat-grid {
  display: grid;
  grid-template-columns: auto repeat(var(--heat-days, 7), minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}
.trip-details .frequency-heat-day {
  font-size: 11px; font-weight: 600; text-align: center; color: var(--text-strong);
}
.trip-details .frequency-heat-daypart {
  display: flex; align-items: center; gap: 4px; padding-right: 4px; color: var(--text-muted);
}
.trip-details .frequency-daypart-icon { width: 14px; height: 14px; flex: none; opacity: 0.8; }
.trip-details .frequency-daypart-word { font-size: 11px; }
.mobile-layout .trip-details .frequency-daypart-word { display: none; }
.trip-details .frequency-heat-cell { min-height: 18px; border-radius: 3px; }
.trip-details .frequency-heat-legend {
  display: flex; align-items: center; gap: 3px; margin-top: 6px;
  font-size: 11px; color: var(--text-muted);
}
.trip-details .frequency-heat-swatch { width: 14px; height: 8px; border-radius: 2px; }
.trip-details .frequency-heat-legend-caption { margin-left: 4px; }
.trip-details .frequency-heat-level-0 { background: var(--frequency-heat-0); }
.trip-details .frequency-heat-level-1 { background: var(--frequency-heat-1); }
.trip-details .frequency-heat-level-2 { background: var(--frequency-heat-2); }
.trip-details .frequency-heat-level-3 { background: var(--frequency-heat-3); }
.trip-details .frequency-heat-level-4 { background: var(--frequency-heat-4); }
.trip-details .frequency-heat-note { margin: 4px 0 8px; color: var(--text-muted); font-size: 12px; }
```

(The `.frequency-heat-weekday` and `.frequency-heat-row` rules are deleted — no markup uses them any more. `grep -rn "frequency-heat-row\|frequency-heat-weekday" web/src` must return nothing.)

- [ ] **Step 3: Build + full tests**

Run: `cd web && npm test && npm run build`
Expected: tests PASS, `tsc -b && vite build` clean.

- [ ] **Step 4: Commit**

```bash
git add web/src/index.css
git commit -m "feat(web): heat strip transposed-grid CSS, validated brand-blue ramp, legend (AO)"
```

---

### Task 3: End-to-end verification + backlog update

**Files:**
- Modify: `docs/superpowers/feedback-backlog.md` (item AO)

**Interfaces:** none.

- [ ] **Step 1: Verify in the running app**

Follow the project `/verify` skill recipe (headless build/launch/drive; DEV `window.__map` state queries; NO screenshots). Confirm: selecting a destination with a histogram renders `.frequency-heat-grid` with day headers, 3 daypart rows, `.frequency-heat-legend`, and `title` attributes on cells; toggling the strip expands the legs list; the fallback text path still renders for a histogram-less destination.

- [ ] **Step 2: Update the backlog**

In `docs/superpowers/feedback-backlog.md`, item AO: delete the three rework bullets and the "User verdict" line; replace with a single line noting the rework shipped 2026-07-17 (transposed grid, icon+word daypart labels, legend, brand-blue validated ramp) and that user visual calibration on desktop + phone is pending.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/feedback-backlog.md
git commit -m "docs: mark AO heat-strip rework implemented, pending calibration"
```
