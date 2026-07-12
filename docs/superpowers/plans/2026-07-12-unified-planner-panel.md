# Unified Journey-Planner Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the scattered `SearchBox`, bottom status bar, and floating `JourneyCard` into one upper-left journey-planner card with From/To fields, swap, in-card filters, trip details, and legend — plus an "armed field" model where clicking a field then clicking a station on the map fills that field.

**Architecture:** Two new pure `lib/` modules hold all testable logic (`planner.ts` for the client-side reachable-destination autocomplete + enable flags; `mapclick.ts` for routing a station click to origin/dest based on the armed field). A reusable `StationField` combobox (extracted from `SearchBox`) drives both From and To. A `JourneyPlanner` component composes the card. `Map.tsx` stops classifying clicks and emits a single `onStationClick(pick)`; `App.tsx` owns the routing and the new `activeField` state.

**Tech Stack:** Vite + React 18 + TypeScript + MapLibre GL. Tests: vitest (node environment — pure logic only). UI-only change; no `pipeline/`, `server/`, data, or HTTP API changes.

## Global Constraints

- **UI-only.** Do not touch `pipeline/`, `server/`, `data/`, or the HTTP API. No new npm dependencies.
- **Test harness is node-env vitest, pure-logic only.** There is NO `@testing-library`/jsdom. New behavior goes in `lib/*.ts` with colocated `*.test.ts`. Component/CSS/wiring tasks are verified by typecheck + the full suite staying green (the user eyeballs the rendered UI separately).
- **Verify every task with BOTH:**
  - Tests: `cd web && npm test -- --run` → expect `Tests <N> passed`.
  - Typecheck: `cd web && npx tsc -b` → expect exit 0, no output.
- **`pickFeature` logic must not change** (`web/src/lib/pickfeature.ts`). `FeaturePick = { type: "dest" | "origin"; id: string }`.
- **Brand blue is `#003399`** (already used by `.stop-toggle button.active` and `.book`); reuse it, do not introduce new colors.
- **Decided defaults (do not re-litigate):** (1) filling From via a map click auto-advances arming to `"to"`; (2) an unreachable To-click is ignored with a hint, not reinterpreted as a new origin; (3) legend appears only once a reach is loaded.
- **Commit after each task.** End commit messages with the repo's Co-Authored-By trailer.

Spec: `docs/superpowers/specs/2026-07-12-unified-planner-panel-design.md`.

---

### Task 1: `lib/planner.ts` — reachable-destination autocomplete + enable flags

**Files:**
- Create: `web/src/lib/planner.ts`
- Test: `web/src/lib/planner.test.ts`

**Interfaces:**
- Consumes: `ReachFile`, `Station` from `./types`.
- Produces:
  - `reachableDestOptions(reach: ReachFile | null, stationsById: Map<string, Station>, query: string, limit?: number): Station[]`
  - `swapEnabled(hasOrigin: boolean, hasDest: boolean): boolean`
  - `toEnabled(hasOrigin: boolean): boolean`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/planner.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { reachableDestOptions, swapEnabled, toEnabled } from "./planner";
import type { ReachFile, Station } from "./types";

const st = (id: string, name: string): Station => ({
  id, name, lat: 0, lon: 0, country: "DE", has_reach: true,
});

const stationsById = new Map<string, Station>([
  ["p", st("p", "Paris Nord")],
  ["b", st("b", "Brussels Midi")],
  ["k", st("k", "Köln Hbf")], // in the map but NOT a destination of this origin
]);

const reach: ReachFile = {
  origin: "o", computed_at: "", sample_date: "",
  destinations: [
    { id: "p", direct_per_day: 3, journeys: [] },
    { id: "b", direct_per_day: 5, journeys: [] },
  ],
};

describe("reachableDestOptions", () => {
  it("returns reachable destinations whose name matches the query", () => {
    expect(reachableDestOptions(reach, stationsById, "par").map((s) => s.id)).toEqual(["p"]);
  });
  it("matches case-insensitively on a substring", () => {
    expect(reachableDestOptions(reach, stationsById, "MIDI").map((s) => s.id)).toEqual(["b"]);
  });
  it("never offers a station that is not in the reach set", () => {
    expect(reachableDestOptions(reach, stationsById, "köln")).toEqual([]);
  });
  it("is empty for a short query or when there is no reach", () => {
    expect(reachableDestOptions(reach, stationsById, "p")).toEqual([]);
    expect(reachableDestOptions(null, stationsById, "paris")).toEqual([]);
  });
  it("respects the limit", () => {
    expect(reachableDestOptions(reach, stationsById, "", 1)).toEqual([]); // empty query short-circuits
    const big = { ...reach, destinations: [
      { id: "p", direct_per_day: 1, journeys: [] },
      { id: "b", direct_per_day: 1, journeys: [] },
    ] };
    expect(reachableDestOptions(big, stationsById, "i", 1)).toHaveLength(1); // "Paris"/"Midi" both contain "i"
  });
});

describe("swapEnabled / toEnabled", () => {
  it("swap needs both endpoints", () => {
    expect(swapEnabled(true, true)).toBe(true);
    expect(swapEnabled(true, false)).toBe(false);
    expect(swapEnabled(false, true)).toBe(false);
  });
  it("To needs an origin", () => {
    expect(toEnabled(true)).toBe(true);
    expect(toEnabled(false)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/lib/planner.test.ts`
Expected: FAIL — `Failed to resolve import "./planner"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/planner.ts`:

```ts
// Pure helpers for the unified journey planner. No React, unit-testable.
// Spec: docs/superpowers/specs/2026-07-12-unified-planner-panel-design.md.
import type { ReachFile, Station } from "./types";

/**
 * Reachable destinations of the current origin whose name matches `query`,
 * resolved to Station objects via `stationsById`. Runs entirely client-side,
 * so the To field can only ever offer stations that are actually reachable.
 * Empty/short queries return nothing (the dropdown only opens on typing).
 */
export function reachableDestOptions(
  reach: ReachFile | null,
  stationsById: Map<string, Station>,
  query: string,
  limit = 8,
): Station[] {
  if (!reach) return [];
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const out: Station[] = [];
  for (const d of reach.destinations) {
    const s = stationsById.get(d.id);
    if (s && s.name.toLowerCase().includes(q)) {
      out.push(s);
      if (out.length >= limit) break;
    }
  }
  return out;
}

/** Swap is only meaningful when both endpoints are set. */
export function swapEnabled(hasOrigin: boolean, hasDest: boolean): boolean {
  return hasOrigin && hasDest;
}

/** The To field is usable only once an origin (and its reach set) exists. */
export function toEnabled(hasOrigin: boolean): boolean {
  return hasOrigin;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/planner.test.ts`
Expected: PASS (all cases green).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/planner.ts web/src/lib/planner.test.ts
git commit -m "feat(planner): reachable-dest autocomplete + enable flags

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `lib/mapclick.ts` — armed-field click routing

**Files:**
- Create: `web/src/lib/mapclick.ts`
- Test: `web/src/lib/mapclick.test.ts`

**Interfaces:**
- Consumes: `FeaturePick` from `./pickfeature`.
- Produces:
  - `type ActiveField = "from" | "to" | null`
  - `armedTarget(activeField: ActiveField, hasOrigin: boolean): "from" | "to"`
  - `type MapClickAction = { action: "origin" | "dest" | "unreachableTo"; id: string }`
  - `routeMapClick(pick: FeaturePick, target: "from" | "to"): MapClickAction`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/mapclick.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { armedTarget, routeMapClick } from "./mapclick";

describe("armedTarget", () => {
  it("uses the explicitly focused field when set", () => {
    expect(armedTarget("from", true)).toBe("from");
    expect(armedTarget("to", false)).toBe("to");
  });
  it("defaults to 'to' when an origin exists, else 'from'", () => {
    expect(armedTarget(null, true)).toBe("to");
    expect(armedTarget(null, false)).toBe("from");
  });
});

describe("routeMapClick", () => {
  it("From-armed makes any station the origin, even a reachable dot", () => {
    expect(routeMapClick({ type: "dest", id: "x" }, "from")).toEqual({ action: "origin", id: "x" });
    expect(routeMapClick({ type: "origin", id: "y" }, "from")).toEqual({ action: "origin", id: "y" });
  });
  it("To-armed accepts a reachable dot as the destination", () => {
    expect(routeMapClick({ type: "dest", id: "d" }, "to")).toEqual({ action: "dest", id: "d" });
  });
  it("To-armed on an unreachable station yields unreachableTo", () => {
    expect(routeMapClick({ type: "origin", id: "u" }, "to")).toEqual({ action: "unreachableTo", id: "u" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/lib/mapclick.test.ts`
Expected: FAIL — `Failed to resolve import "./mapclick"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/mapclick.ts`:

```ts
// Routes a map station click to a selection action based on which planner
// field is "armed". Pure, unit-testable. Spec: 2026-07-12-unified-planner-panel.
import type { FeaturePick } from "./pickfeature";

export type ActiveField = "from" | "to" | null;

/**
 * Which field the next map station click should fill. An explicitly focused
 * field wins; otherwise default to "to" when an origin exists, else "from".
 */
export function armedTarget(activeField: ActiveField, hasOrigin: boolean): "from" | "to" {
  return activeField ?? (hasOrigin ? "to" : "from");
}

export type MapClickAction =
  | { action: "origin"; id: string }
  | { action: "dest"; id: string }
  | { action: "unreachableTo"; id: string };

/**
 * Route a station click given the armed target. From wins even over a
 * reachable-dot hit; To accepts only reachable dots (pick.type === "dest").
 */
export function routeMapClick(pick: FeaturePick, target: "from" | "to"): MapClickAction {
  if (target === "from") return { action: "origin", id: pick.id };
  if (pick.type === "dest") return { action: "dest", id: pick.id };
  return { action: "unreachableTo", id: pick.id };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/mapclick.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/mapclick.ts web/src/lib/mapclick.test.ts
git commit -m "feat(mapclick): armed-field routing for map station clicks

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `StationField` combobox (extracted from `SearchBox`)

A reusable field used for both From and To. Holds its own query/edit state; shows the selected station name as a clearable chip when not editing. Focusing it (or clicking the chip) calls `onFocusField` so the parent can arm it — arming persists after the input blurs (that's what makes the follow-up map click land here).

**Files:**
- Create: `web/src/components/StationField.tsx`
- Modify: `web/src/index.css` (add `.station-field` rules; do NOT remove `.search-box` yet — `SearchBox.tsx` still exists until Task 6)

**Interfaces:**
- Consumes: `keyNav` from `../lib/keynav`; `Station` from `../lib/types`.
- Produces: default export `StationField` with props
  `{ placeholder: string; disabled?: boolean; value: string; search: (q: string) => Station[] | Promise<Station[]>; onPick: (s: Station) => void; onClear: () => void; onFocusField: () => void; }`.

- [ ] **Step 1: Create the component**

Create `web/src/components/StationField.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { keyNav } from "../lib/keynav";
import type { Station } from "../lib/types";

interface Props {
  placeholder: string;
  disabled?: boolean;
  value: string; // selected station name, or "" when none
  search: (q: string) => Station[] | Promise<Station[]>;
  onPick: (s: Station) => void;
  onClear: () => void;
  onFocusField: () => void;
}

export default function StationField(
  { placeholder, disabled, value, search, onPick, onClear, onFocusField }: Props,
) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Station[]>([]);
  const [active, setActive] = useState(-1);
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // When the parent supplies a new selected value (e.g. filled by a map click),
  // drop back to the chip display.
  useEffect(() => {
    setEditing(false);
    setQ("");
  }, [value]);

  useEffect(() => {
    setActive(-1);
    if (!editing || q.trim().length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const r = await search(q);
        if (!cancelled) setResults(r);
      } catch {
        if (!cancelled) setResults([]);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, editing, search]);

  function beginEdit() {
    if (disabled) return;
    onFocusField();
    setEditing(true);
    setQ("");
    setResults([]);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function pick(s: Station) {
    onPick(s);
    setEditing(false);
    setQ("");
    setResults([]);
    setActive(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const r = keyNav(e.key, { index: active, count: results.length });
    if (r.type === "pass") return;
    e.preventDefault();
    if (r.type === "move") setActive(r.index);
    else if (r.type === "select") pick(results[r.index]);
    else {
      setResults([]);
      setActive(-1);
      setEditing(false);
    }
  }

  if (value && !editing) {
    return (
      <div className="station-field filled">
        <button className="field-value" onClick={beginEdit} disabled={disabled}>{value}</button>
        <button className="field-clear" onClick={onClear} aria-label="Clear">×</button>
      </div>
    );
  }

  return (
    <div className="station-field">
      <input
        ref={inputRef}
        placeholder={placeholder}
        disabled={disabled}
        value={q}
        onFocus={() => {
          onFocusField();
          setEditing(true);
        }}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {results.length > 0 && (
        <ul>
          {results.map((s, i) => (
            <li key={s.id} className={i === active ? "active" : ""}>
              {/* onMouseDown preventDefault keeps the input from blurring before click */}
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(s)}
                onMouseEnter={() => setActive(i)}
              >
                {s.name} <span className="country">{s.country}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add CSS for the field**

Append to `web/src/index.css` (mirrors the existing `.search-box` rules; kept as a separate class so both can coexist until Task 6):

```css
.station-field { position: relative; display: flex; align-items: center; gap: 6px; }
.station-field input { width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); }
.station-field.filled { justify-content: space-between; }
.station-field .field-value { flex: 1; text-align: left; padding: 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); cursor: pointer; }
.station-field .field-value:hover { background: var(--surface-hover); }
.station-field .field-clear { border: 0; background: none; font-size: 18px; line-height: 1; cursor: pointer; color: var(--text); padding: 2px 6px; }
.station-field ul {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 20; margin: 4px 0 0; padding: 0;
  list-style: none; background: var(--surface); border-radius: 8px; box-shadow: var(--shadow);
}
.station-field li button { display: block; width: 100%; text-align: left; padding: 8px; border: 0; background: none; cursor: pointer; color: var(--text); }
.station-field li button:hover { background: var(--surface-hover); }
.station-field li.active button { background: var(--surface-hover); }
.station-field .country { color: var(--text-subtle); font-size: 12px; }
```

- [ ] **Step 3: Typecheck + full suite**

Run: `cd web && npx tsc -b && npm test -- --run`
Expected: tsc exit 0; `Tests 103 passed` (91 existing + 7 planner + 5 mapclick from Tasks 1–2). No render test for this component — the repo has no component-test harness.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/StationField.tsx web/src/index.css
git commit -m "feat(planner): reusable StationField combobox

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `TripDetails` + `JourneyPlanner` card

`TripDetails` is the current `JourneyCard` body rendered in-flow (no absolute positioning, no close ×). `JourneyPlanner` composes From / swap / To / filters / trip details / legend inside the `.panel`.

**Files:**
- Create: `web/src/components/TripDetails.tsx`
- Create: `web/src/components/JourneyPlanner.tsx`
- Modify: `web/src/index.css` (add `.planner`, `.swap-btn`, `.planner-divider`, `.trip-details` rules)

**Interfaces:**
- Consumes: `StationField` (Task 3); `reachableDestOptions`, `swapEnabled`, `toEnabled` (Task 1); `StopToggle`, `TimeSlider`, `Legend` (existing); `bookingUrl` (`../lib/booking`), `bestJourney`/`MaxTrains` (`../lib/geojson`); `api` (`../lib/api`); `ReachFile`, `Station`, `Destination` (`../lib/types`); `ActiveField` (`../lib/mapclick`).
- Produces: default export `JourneyPlanner` with props
  `{ reach: ReachFile | null; stationsById: Map<string, Station>; origin?: Station; destination?: Station; dest?: Destination; maxTrains: MaxTrains; maxMinutes: number; activeField: ActiveField; error: string | null; hint: string | null; onSetOrigin: (s: Station) => void; onClearOrigin: () => void; onSetDest: (s: Station) => void; onClearDest: () => void; onSwap: () => void; onArm: (f: "from" | "to") => void; onMaxTrains: (v: MaxTrains) => void; onMaxMinutes: (v: number) => void; }`.

- [ ] **Step 1: Create `TripDetails.tsx`**

Create `web/src/components/TripDetails.tsx`:

```tsx
import { bookingUrl } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station } from "../lib/types";

const REF = import.meta.env.VITE_TRAINLINE_REF ?? "";

interface Props {
  origin: Station;
  destination: Station;
  dest: Destination;
  maxTrains: MaxTrains;
  stationsById: Map<string, Station>;
}

export default function TripDetails(
  { origin, destination, dest, maxTrains, stationsById }: Props,
) {
  const journey = bestJourney(dest, maxTrains);
  if (!journey) return <p className="hint">No route within your filters.</p>;
  const h = Math.floor(journey.duration_min / 60);
  const m = journey.duration_min % 60;
  return (
    <div className="trip-details">
      <h2>{origin.name} → {destination.name}</h2>
      <p className="duration">{h} h {m ? `${m} min` : ""} · {journey.trains === 1
        ? `nonstop · ${dest.direct_per_day}× per day`
        : `${journey.trains} trains`}</p>
      <ol className="legs">
        {journey.legs.map((leg) => (
          <li key={`${leg.train}-${leg.to}`}>
            <strong>{leg.train}</strong> {stationsById.get(leg.from)?.name ?? leg.from}
            {" → "} {stationsById.get(leg.to)?.name ?? leg.to}
          </li>
        ))}
      </ol>
      <a className="book" href={bookingUrl(origin, destination, REF)}
         target="_blank" rel="noopener noreferrer">
        Book this trip
      </a>
      <p className="fineprint">Durations from a sample weekday — pick your date at checkout.</p>
    </div>
  );
}
```

- [ ] **Step 2: Create `JourneyPlanner.tsx`**

Create `web/src/components/JourneyPlanner.tsx`:

```tsx
import { useCallback } from "react";
import StationField from "./StationField";
import TripDetails from "./TripDetails";
import StopToggle from "./StopToggle";
import TimeSlider from "./TimeSlider";
import Legend from "./Legend";
import { api } from "../lib/api";
import { reachableDestOptions, swapEnabled, toEnabled } from "../lib/planner";
import type { MaxTrains } from "../lib/geojson";
import type { Destination, ReachFile, Station } from "../lib/types";

interface Props {
  reach: ReachFile | null;
  stationsById: Map<string, Station>;
  origin?: Station;
  destination?: Station;
  dest?: Destination;
  maxTrains: MaxTrains;
  maxMinutes: number;
  error: string | null;
  hint: string | null;
  onSetOrigin: (s: Station) => void;
  onClearOrigin: () => void;
  onSetDest: (s: Station) => void;
  onClearDest: () => void;
  onSwap: () => void;
  onArm: (f: "from" | "to") => void;
  onMaxTrains: (v: MaxTrains) => void;
  onMaxMinutes: (v: number) => void;
}

export default function JourneyPlanner(props: Props) {
  const { reach, stationsById, origin, destination, dest, maxTrains, maxMinutes, error, hint } = props;

  const searchFrom = useCallback(
    (q: string) => api.searchStations(q).then((r) => r.stations),
    [],
  );
  const searchTo = useCallback(
    (q: string) => reachableDestOptions(reach, stationsById, q),
    [reach, stationsById],
  );

  return (
    <aside className="panel planner">
      <StationField
        placeholder="Start from…"
        value={origin?.name ?? ""}
        search={searchFrom}
        onPick={props.onSetOrigin}
        onClear={props.onClearOrigin}
        onFocusField={() => props.onArm("from")}
      />
      <button className="swap-btn" onClick={props.onSwap}
              disabled={!swapEnabled(!!origin, !!destination)}
              aria-label="Swap From and To">⇄</button>
      <StationField
        placeholder="To… (or click the map)"
        disabled={!toEnabled(!!origin)}
        value={destination?.name ?? ""}
        search={searchTo}
        onPick={props.onSetDest}
        onClear={props.onClearDest}
        onFocusField={() => props.onArm("to")}
      />

      <div className="planner-divider" />
      <StopToggle value={maxTrains} onChange={props.onMaxTrains} />
      <TimeSlider value={maxMinutes} onChange={props.onMaxMinutes} />

      {origin && destination && dest && (
        <>
          <div className="planner-divider" />
          <TripDetails origin={origin} destination={destination} dest={dest}
                       maxTrains={maxTrains} stationsById={stationsById} />
        </>
      )}

      {hint && <p className="hint">{hint}</p>}
      {!reach && <p className="hint">Search or click a station to begin.</p>}
      {error && <p className="error">{error}</p>}

      {reach && (
        <>
          <div className="planner-divider" />
          <Legend />
        </>
      )}
    </aside>
  );
}
```

- [ ] **Step 3: Add CSS**

Append to `web/src/index.css`:

```css
.planner .swap-btn {
  align-self: center; width: 34px; height: 34px; margin: -2px 0;
  border: 1px solid var(--border); border-radius: 999px; background: var(--surface);
  color: var(--text); font-size: 16px; cursor: pointer;
}
.planner .swap-btn:hover:not(:disabled) { background: var(--surface-hover); }
.planner .swap-btn:disabled { opacity: 0.4; cursor: default; }
.planner-divider { height: 1px; background: var(--border); margin: 2px 0; }
.trip-details h2 { margin: 0 0 4px; font-size: 16px; }
.trip-details .duration { margin: 0 0 8px; color: var(--text-strong); }
.trip-details .legs { margin: 0 0 12px; padding-left: 18px; font-size: 13px; }
.trip-details .book {
  display: block; text-align: center; background: #003399; color: #fff;
  padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 600;
}
.trip-details .fineprint { margin: 8px 0 0; font-size: 11px; color: var(--text-subtle); }
```

- [ ] **Step 4: Typecheck + full suite**

Run: `cd web && npx tsc -b && npm test -- --run`
Expected: tsc exit 0; `Tests 103 passed`. (`JourneyPlanner`/`TripDetails` are not yet imported by `App`; this step only proves they compile and the suite stays green.)

- [ ] **Step 5: Commit**

```bash
git add web/src/components/TripDetails.tsx web/src/components/JourneyPlanner.tsx web/src/index.css
git commit -m "feat(planner): TripDetails + JourneyPlanner card

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `Map.tsx` emits one `onStationClick(pick)`

Stop deciding origin-vs-dest inside the map; hand the raw `FeaturePick` up to `App`. `pickFeature` is unchanged.

**Files:**
- Modify: `web/src/components/Map.tsx` (Props interface ~lines 22–32; click handler ~lines 109–119)

**Interfaces:**
- Consumes: `FeaturePick` from `../lib/pickfeature`.
- Produces: `MapView` prop change — remove `onSelectOrigin` and `onSelectDestination`, add `onStationClick: (pick: FeaturePick) => void`. `onEmptyClick` unchanged.

- [ ] **Step 1: Update the import**

In `web/src/components/Map.tsx`, change the pickfeature import to also bring the type:

```tsx
import { pickFeature, type FeaturePick } from "../lib/pickfeature";
```

- [ ] **Step 2: Update the Props interface**

Replace these three lines in the `Props` interface:

```tsx
  onSelectOrigin: (id: string) => void;
  onSelectDestination: (id: string) => void;
  onEmptyClick: () => void;
```

with:

```tsx
  onStationClick: (pick: FeaturePick) => void;
  onEmptyClick: () => void;
```

- [ ] **Step 3: Update the click handler**

Replace the body of the `m.on("click", …)` handler (the `pickFeature`→branch block):

```tsx
        const pick = pickFeature(hits);
        if (!pick) {
          propsRef.current.onEmptyClick();
          return;
        }
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
```

with:

```tsx
        const pick = pickFeature(hits);
        if (!pick) {
          propsRef.current.onEmptyClick();
          return;
        }
        propsRef.current.onStationClick(pick);
```

- [ ] **Step 4: Typecheck (expected to fail at the call site)**

Run: `cd web && npx tsc -b`
Expected: FAIL — `App.tsx` still passes `onSelectOrigin`/`onSelectDestination` to `MapView`. This is fixed in Task 6. (Do not commit a red typecheck alone; this task's commit happens after Task 6 wires App. To keep commits green, **fold Task 5's commit into Task 6's commit** — make the edits here, then proceed directly to Task 6.)

- [ ] **Step 5: Proceed to Task 6 without committing**

No commit yet — `Map.tsx` and `App.tsx` must land together to keep the build green.

---

### Task 6: Wire `App.tsx`; delete `SearchBox`/`JourneyCard`/status-bar

Add `activeField` + `hint` state, route map clicks via `armedTarget`/`routeMapClick`, render `JourneyPlanner`, drop the old status bar and floating card, retarget Escape. Delete the now-unused `SearchBox.tsx` and `JourneyCard.tsx` and their CSS.

**Files:**
- Modify: `web/src/App.tsx` (full rewrite of the component below)
- Delete: `web/src/components/SearchBox.tsx`
- Delete: `web/src/components/JourneyCard.tsx`
- Modify: `web/src/index.css` (remove `.search-box`, `.journey-card`, `.status-bar` blocks)

**Interfaces:**
- Consumes: `armedTarget`, `routeMapClick`, `ActiveField` (Task 2); `JourneyPlanner` (Task 4); `MapView` new prop (Task 5); `FeaturePick` (`./lib/pickfeature`); existing `emptyClickAction`, `swapDest`, `api`, `useTheme`, `MaxTrains`, `ReachFile`, `Station`.

- [ ] **Step 1: Rewrite `App.tsx`**

Replace the entire contents of `web/src/App.tsx` with:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
import { armedTarget, routeMapClick, type ActiveField } from "./lib/mapclick";
import MapView from "./components/Map";
import JourneyPlanner from "./components/JourneyPlanner";
import { api } from "./lib/api";
import type { MaxTrains } from "./lib/geojson";
import type { FeaturePick } from "./lib/pickfeature";
import type { ReachFile, Station } from "./lib/types";
import { useTheme } from "./lib/theme";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(1440);
  const [selectedDest, setSelectedDest] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, toggleTheme] = useTheme();

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);

  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch((e) => setError(String(e)));
  }, []);

  const selectOrigin = useCallback((id: string) => {
    setSelectedDest(null);
    setHint(null);
    setActiveField("to"); // auto-advance arming to To
    api.getReach(id).then(setReach).catch((e) => setError(String(e)));
  }, []);

  const clearSelection = useCallback(() => {
    setReach(null);
    setSelectedDest(null);
    setHint(null);
    setActiveField(null);
  }, []);

  const selectDest = useCallback((id: string) => {
    setHint(null);
    setSelectedDest(id);
  }, []);

  const swapSelection = useCallback(() => {
    if (!selectedDest || !reach) return;
    const destId = selectedDest;
    const prevOrigin = reach.origin;
    setSelectedDest(null);
    api.getReach(destId).then((newReach) => {
      setReach(newReach);
      setSelectedDest(swapDest(newReach.destinations, prevOrigin));
    }).catch((e) => setError(String(e)));
  }, [selectedDest, reach]);

  const origin = reach ? stationsById.get(reach.origin) : undefined;
  const dest = selectedDest && reach
    ? reach.destinations.find((d) => d.id === selectedDest) : undefined;
  const destination = dest ? stationsById.get(dest.id) : undefined;

  const onStationClick = useCallback((pick: FeaturePick) => {
    const target = armedTarget(activeField, reach !== null);
    const routed = routeMapClick(pick, target);
    if (routed.action === "origin") selectOrigin(routed.id);
    else if (routed.action === "dest") selectDest(routed.id);
    else setHint(`Not reachable from ${origin?.name ?? "the origin"} within your filters.`);
  }, [activeField, reach, origin, selectOrigin, selectDest]);

  const onEmptyClick = useCallback(() => {
    const action = emptyClickAction(selectedDest !== null, reach !== null);
    if (action === "clearDest") setSelectedDest(null);
    else if (action === "clearAll") clearSelection();
  }, [selectedDest, reach, clearSelection]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (selectedDest) setSelectedDest(null);
      else if (reach) clearSelection();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reach, selectedDest, clearSelection]);

  return (
    <div className="app">
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest} theme={theme}
               onStationClick={onStationClick} onEmptyClick={onEmptyClick} />
      <header className="header-bar">
        <span className="header-brand">
          <img src="/logo-train-light.svg" alt="" className="header-train" />
          <span className="header-wordmark">onestop<span className="header-wordmark-eu">europe</span></span>
          <span className="header-endstop" aria-hidden="true" />
        </span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
        <button className="theme-toggle" onClick={toggleTheme}
                aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>
      <JourneyPlanner
        reach={reach} stationsById={stationsById}
        origin={origin} destination={destination} dest={dest}
        maxTrains={maxTrains} maxMinutes={maxMinutes}
        error={error} hint={hint}
        onSetOrigin={(s) => selectOrigin(s.id)}
        onClearOrigin={clearSelection}
        onSetDest={(s) => selectDest(s.id)}
        onClearDest={() => { setSelectedDest(null); setHint(null); }}
        onSwap={swapSelection}
        onArm={setActiveField}
        onMaxTrains={setMaxTrains}
        onMaxMinutes={setMaxMinutes}
      />
    </div>
  );
}
```

- [ ] **Step 2: Delete the superseded components**

```bash
git rm web/src/components/SearchBox.tsx web/src/components/JourneyCard.tsx
```

- [ ] **Step 3: Remove dead CSS**

In `web/src/index.css`, delete the `.search-box …` block (the old one, lines ~154–163), the `.journey-card …` block (lines ~172–190), and the `.status-bar …` block (lines ~191–210). Leave `.station-field`, `.planner`, `.stop-toggle`, `.time-slider`, `.legend`, `.hint`, `.error` intact.

- [ ] **Step 4: Typecheck + full suite**

Run: `cd web && npx tsc -b && npm test -- --run`
Expected: tsc exit 0 (no more `onSelectOrigin` references); `Tests 103 passed`. If tsc reports an unused symbol or a missing prop, fix it before committing.

- [ ] **Step 5: Grep for leftovers**

Run: `cd web && grep -rn "SearchBox\|JourneyCard\|onSelectOrigin\|onSelectDestination\|status-bar" src`
Expected: no matches. If any appear, remove them.

- [ ] **Step 6: Commit (folds in Task 5's Map.tsx edits)**

```bash
git add web/src/App.tsx web/src/components/Map.tsx web/src/index.css
git commit -m "feat(planner): unify controls into JourneyPlanner; armed-field map clicks

Merge SearchBox + status bar + JourneyCard into one upper-left planner card;
Map emits onStationClick(pick) and App routes it via armedTarget/routeMapClick.
Delete SearchBox/JourneyCard and their CSS.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 7: Manual verification (user eyeballs)**

Run: `cd web && npm run dev` and confirm in the browser:
1. Empty state: planner shows From, disabled To, filters, hint "Search or click a station to begin."; no legend yet.
2. Pick a From (type or click a station) → map colors; To becomes enabled; legend appears; arming auto-advances so the next map click fills To.
3. Click a colored station → To fills, trip details + Book appear below the filters.
4. Click a grey/unreachable station while To is armed → hint "Not reachable from … within your filters."; nothing else changes.
5. Click into To (chip), then click a different colored station → To updates.
6. ⇄ swaps From/To (enabled only when both set). ✕ on To clears the destination; ✕ on From clears everything. Esc steps back (dest, then origin).

---

## Self-Review

**Spec coverage:**
- Layout "all-in-one card" → Task 4 (`JourneyPlanner` order: From/swap/To → divider → filters → trip details → divider → legend). ✓
- `StationField` extracted, From=API / To=client-side → Task 3 + Task 4 `searchFrom`/`searchTo`. ✓
- `lib/planner.ts` (`reachableDestOptions`, `swapEnabled`, `toEnabled`) → Task 1. ✓
- `lib/mapclick.ts` (`armedTarget`, `routeMapClick`) → Task 2. ✓
- Armed-field model, persists past blur, From auto-advances to To, unreachableTo hint → Task 6 (`onStationClick`, `selectOrigin` sets `activeField="to"`, focus→`onArm`). ✓
- `Map.tsx` single `onStationClick(pick)`, `pickFeature` unchanged → Task 5. ✓
- Delete status bar + floating card; legend only when reach loaded → Task 6 + Task 4 (`{reach && <Legend/>}`). ✓
- Esc + empty-click preserved → Task 6 (handlers retained, retargeted). ✓
- No route within filters state → Task 4 (`TripDetails` `bestJourney` null branch). ✓
- Tests: planner.test.ts + mapclick.test.ts; existing suite green → Tasks 1–2 add tests; every task ends on green. ✓

**Placeholder scan:** none — all steps carry full code/commands.

**Type consistency:** `FeaturePick` (import type in Map + App + mapclick); `ActiveField` from `mapclick` used in App state + `onArm`; `MapClickAction.action` values `"origin"|"dest"|"unreachableTo"` matched in App's `onStationClick`; `JourneyPlanner` prop names match App's call site; `searchTo` returns `Station[]`, `StationField.search` accepts `Station[] | Promise<Station[]>`. ✓

## Out of scope

- **N** (broken Trainline booking link) — separate bug; `bookingUrl` usage copied verbatim.
- **L** (dimming) and the "hide small dots at zoom" note — not built here.
