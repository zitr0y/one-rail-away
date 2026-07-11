# Selection UX Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Start here" / "⇄ Swap" buttons to the journey card and make empty-map clicks step the selection back (mirroring Escape), all driven by a new pure-logic module.

**Architecture:** A new `web/src/lib/selection.ts` contains two pure functions (`emptyClickAction`, `swapDest`) unit-tested without a map. `App.tsx` wires the new callbacks (`onStartHere`, `onSwap`, `onEmptyClick`) using existing `selectOrigin` and the API. `Map.tsx`'s click handler gains an `!pick` branch that calls `onEmptyClick`. `JourneyCard.tsx` gets two new buttons styled consistently with the existing `.close` pill and `.book` block.

**Tech Stack:** React + TypeScript + MapLibre GL (vitest, oxlint). Frontend-only — no pipeline/ or server/ changes.

## Global Constraints

- **Frontend-only.** Do not touch `pipeline/`, `server/`, or any Python files.
- **TDD.** Write the failing test first, watch it fail, implement minimally, watch it pass. Commit after every task.
- **Current baseline:** 33 web tests (7 test files). Test counts must change ONLY by the deltas described in each task.
- **The user does visual checks.** Acceptance is at unit-test / type-check / lint level only. Do not claim visual verification or take screenshots.
- **Subagent models:** opus or sonnet only, never haiku.
- **Verification commands** are always run from `web/`:
  - `npm test` (vitest) — expected count noted per task
  - `npx tsc -b` — must exit 0 with no output
  - `npm run lint` (oxlint) — must report no errors

---

## File Structure

**Create:**
- `web/src/lib/selection.ts` — pure helpers `emptyClickAction` and `swapDest` (no React, no MapLibre).
- `web/src/lib/selection.test.ts` — unit tests for both functions (5 tests).

**Modify:**
- `web/src/App.tsx` — add `swapSelection`, `onEmptyClick`, `onStartHere` callbacks; pass them to `MapView` and `JourneyCard`.
- `web/src/components/Map.tsx:16-24,87-94` — extend `Props` with `onEmptyClick`; wire `!pick` branch.
- `web/src/components/JourneyCard.tsx:7-13,16,22-40` — extend `Props` with `onStartHere`, `onSwap`; add two buttons.
- `web/src/index.css:38-43` — add `.journey-card .actions` row style and `.journey-card .action-btn` style.

---

## Task 1: Pure selection helpers + unit tests

Creates the new `web/src/lib/selection.ts` module with `emptyClickAction` and `swapDest`, driven by tests written first.

**Files:**
- Create: `web/src/lib/selection.test.ts`
- Create: `web/src/lib/selection.ts`

**Interfaces:**
- Consumes: nothing (pure functions, no imports from the project).
- Produces:
  - `emptyClickAction(hasDest: boolean, hasOrigin: boolean) -> "clearDest" | "clearAll" | "noop"` — determines what an empty-map click should do.
  - `swapDest(destinations: { id: string }[], oldOriginId: string) -> string | null` — returns `oldOriginId` if it appears among `destinations`, else `null`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/selection.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { emptyClickAction, swapDest } from "./selection";

describe("emptyClickAction", () => {
  it("clears dest when a destination is selected", () => {
    expect(emptyClickAction(true, true)).toBe("clearDest");
  });

  it("clears all when only an origin is selected", () => {
    expect(emptyClickAction(false, true)).toBe("clearAll");
  });

  it("is a noop when nothing is selected", () => {
    expect(emptyClickAction(false, false)).toBe("noop");
  });
});

describe("swapDest", () => {
  it("returns the old origin id when it is among the new destinations", () => {
    const dests = [{ id: "A" }, { id: "B" }, { id: "C" }];
    expect(swapDest(dests, "B")).toBe("B");
  });

  it("returns null when the old origin is not among the new destinations", () => {
    const dests = [{ id: "A" }, { id: "C" }];
    expect(swapDest(dests, "B")).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/selection.test.ts`
Expected: FAIL — `Cannot find module './selection'` or `does not provide an export named 'emptyClickAction'`.

- [ ] **Step 3: Write the minimal implementation**

Create `web/src/lib/selection.ts`:

```ts
// Pure selection helpers — logic unit-testable without React or MapLibre.
// Spec: docs/superpowers/specs/2026-07-11-selection-ux-design.md §3.

/**
 * Decide what an empty-map click (no station under cursor) should do.
 * Mirrors the Escape key step-back behaviour:
 *   journey card open → clear destination only (back to the full fan)
 *   origin selected   → clear everything
 *   nothing selected  → noop
 */
export function emptyClickAction(
  hasDest: boolean,
  hasOrigin: boolean,
): "clearDest" | "clearAll" | "noop" {
  if (hasDest) return "clearDest";
  if (hasOrigin) return "clearAll";
  return "noop";
}

/**
 * After swapping origin and destination, check whether the old origin
 * appears among the *new* origin's destinations.
 * Returns the old origin's id if present, or null to fall back to
 * origin-only (no destination selected, no error shown).
 */
export function swapDest(
  destinations: { id: string }[],
  oldOriginId: string,
): string | null {
  return destinations.some((d) => d.id === oldOriginId) ? oldOriginId : null;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/selection.test.ts`
Expected: PASS — 5 passed.

- [ ] **Step 5: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 38 tests (33 baseline + 5 new).

- [ ] **Step 6: Type-check and lint**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/selection.ts web/src/lib/selection.test.ts
git commit -m "feat: add pure selection helpers (emptyClickAction, swapDest)"
```

---

## Task 2: App.tsx + Map.tsx + JourneyCard.tsx wiring and UI

Wires the pure helpers into the component tree: `App.tsx` gets `swapSelection`, `onEmptyClick`, and `onStartHere`; `Map.tsx` calls `onEmptyClick` on empty clicks; `JourneyCard.tsx` gains "Start here" and "⇄ Swap" buttons styled consistently with existing CSS.

**Files:**
- Modify: `web/src/App.tsx:1-4,27-30,55-57,68-72`
- Modify: `web/src/components/Map.tsx:16-24,87-94`
- Modify: `web/src/components/JourneyCard.tsx:7-13,16,22-40`
- Modify: `web/src/index.css:38-43`

**Interfaces:**
- Consumes:
  - `emptyClickAction(hasDest: boolean, hasOrigin: boolean) -> "clearDest" | "clearAll" | "noop"` from `web/src/lib/selection.ts` (Task 1).
  - `swapDest(destinations: { id: string }[], oldOriginId: string) -> string | null` from `web/src/lib/selection.ts` (Task 1).
  - `api.getReach(id: string) -> Promise<ReachFile>` from `web/src/lib/api.ts`.
  - `selectOrigin(id: string) -> void` (existing in App.tsx).
- Produces:
  - `MapView` accepts a new prop `onEmptyClick: () => void`.
  - `JourneyCard` accepts new props `onStartHere: () => void` and `onSwap: () => void`.

- [ ] **Step 1: Add CSS for the journey-card action buttons**

In `web/src/index.css`, replace lines 38-43 from:

```css
.journey-card .close { position: absolute; top: 8px; right: 12px; border: 0; background: none; font-size: 18px; cursor: pointer; }
.journey-card .book {
  display: block; text-align: center; background: #111827; color: #fff;
  padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 600;
}
.journey-card .fineprint { margin: 8px 0 0; font-size: 11px; color: #9ca3af; }
```

to:

```css
.journey-card .close { position: absolute; top: 8px; right: 12px; border: 0; background: none; font-size: 18px; cursor: pointer; }
.journey-card .actions { display: flex; gap: 8px; margin: 0 0 10px; }
.journey-card .action-btn {
  flex: 1; padding: 7px 0; border: 1px solid #d1d5db; border-radius: 8px;
  background: #fff; font-size: 13px; cursor: pointer; text-align: center;
}
.journey-card .action-btn:hover { background: #f3f4f6; }
.journey-card .book {
  display: block; text-align: center; background: #111827; color: #fff;
  padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 600;
}
.journey-card .fineprint { margin: 8px 0 0; font-size: 11px; color: #9ca3af; }
```

- [ ] **Step 2: Update `JourneyCard.tsx` — add `onStartHere` and `onSwap` props and buttons**

Replace the entire contents of `web/src/components/JourneyCard.tsx` with:

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
  onClose: () => void;
  onStartHere: () => void;
  onSwap: () => void;
}

export default function JourneyCard({ origin, destination, dest, maxTrains, stationsById, onClose, onStartHere, onSwap }: Props) {
  const journey = bestJourney(dest, maxTrains);
  if (!journey) return null;
  const h = Math.floor(journey.duration_min / 60);
  const m = journey.duration_min % 60;
  return (
    <div className="journey-card">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2>{origin.name} → {destination.name}</h2>
      <p className="duration">{h} h {m ? `${m} min` : ""} · {journey.trains === 1
        ? `nonstop · ${dest.direct_per_day}× per day`
        : `${journey.trains} trains`}</p>
      <div className="actions">
        <button className="action-btn" onClick={onStartHere}>Start here</button>
        <button className="action-btn" onClick={onSwap}>⇄ Swap</button>
      </div>
      <ol className="legs">
        {journey.legs.map((leg) => (
          <li key={`${leg.train}-${leg.to}`}>
            <strong>{leg.train}</strong> {stationsById.get(leg.from)?.name ?? leg.from}
            {" → "} {stationsById.get(leg.to)?.name ?? leg.to}
          </li>
        ))}
      </ol>
      <a className="book" href={bookingUrl(origin, destination, REF)} target="_blank" rel="noopener noreferrer">
        Book this trip
      </a>
      <p className="fineprint">Durations from a sample weekday — pick your date at checkout.</p>
    </div>
  );
}
```

- [ ] **Step 3: Update `Map.tsx` — add `onEmptyClick` prop and wire `!pick` branch**

In `web/src/components/Map.tsx`, make two changes:

(a) Add `onEmptyClick` to the `Props` interface. Replace lines 16-24 from:

```ts
interface Props {
  stations: Station[];
  reach: ReachFile | null;
  maxTrains: MaxTrains;
  maxMinutes: number;
  selectedDest: string | null;
  onSelectOrigin: (id: string) => void;
  onSelectDestination: (id: string) => void;
}
```

to:

```ts
interface Props {
  stations: Station[];
  reach: ReachFile | null;
  maxTrains: MaxTrains;
  maxMinutes: number;
  selectedDest: string | null;
  onSelectOrigin: (id: string) => void;
  onSelectDestination: (id: string) => void;
  onEmptyClick: () => void;
}
```

(b) In the click handler (lines 87-94), change the `!pick` branch from returning silently to calling `onEmptyClick`. Replace:

```ts
      m.on("click", (e) => {
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS })
          .map((f) => ({ layer: f.layer.id, id: f.properties!.id as string }));
        const pick = pickFeature(hits);
        if (!pick) return;
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
      });
```

with:

```ts
      m.on("click", (e) => {
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS })
          .map((f) => ({ layer: f.layer.id, id: f.properties!.id as string }));
        const pick = pickFeature(hits);
        if (!pick) {
          propsRef.current.onEmptyClick();
          return;
        }
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
      });
```

- [ ] **Step 4: Update `App.tsx` — add `swapSelection`, `onEmptyClick`, `onStartHere` and pass them down**

In `web/src/App.tsx`, make the following changes:

(a) Add the import for the selection helpers. Replace line 1 from:

```ts
import { useEffect, useMemo, useState } from "react";
```

to:

```ts
import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
```

(b) Add the three new callbacks after the `clearSelection` function (after line 35). Insert the following block between `clearSelection` and the `const origin = ...` line:

After:
```ts
  function clearSelection() {
    setReach(null);
    setSelectedDest(null);
  }
```

Add:
```ts

  function onStartHere() {
    if (!selectedDest) return;
    selectOrigin(selectedDest);
  }

  function swapSelection() {
    if (!selectedDest || !reach) return;
    const destId = selectedDest;
    const prevOrigin = reach.origin;
    setSelectedDest(null);
    api.getReach(destId).then((newReach) => {
      setReach(newReach);
      setSelectedDest(swapDest(newReach.destinations, prevOrigin));
    }).catch((e) => setError(String(e)));
  }

  const onEmptyClick = useCallback(() => {
    const action = emptyClickAction(selectedDest !== null, reach !== null);
    if (action === "clearDest") setSelectedDest(null);
    else if (action === "clearAll") clearSelection();
  }, [selectedDest, reach]);
```

(c) Pass `onEmptyClick` to `MapView`. Replace lines 55-57 from:

```ts
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest} />
```

to:

```ts
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest}
               onEmptyClick={onEmptyClick} />
```

(d) Pass `onStartHere` and `onSwap` to `JourneyCard`. Replace lines 68-72 from:

```tsx
      {origin && dest && stationsById.get(dest.id) && (
        <JourneyCard origin={origin} destination={stationsById.get(dest.id)!} dest={dest}
                     maxTrains={maxTrains} stationsById={stationsById}
                     onClose={() => setSelectedDest(null)} />
      )}
```

to:

```tsx
      {origin && dest && stationsById.get(dest.id) && (
        <JourneyCard origin={origin} destination={stationsById.get(dest.id)!} dest={dest}
                     maxTrains={maxTrains} stationsById={stationsById}
                     onClose={() => setSelectedDest(null)}
                     onStartHere={onStartHere} onSwap={swapSelection} />
      )}
```

- [ ] **Step 5: Run the full web test suite**

Run: `cd web && npm test`
Expected: PASS — 38 tests (33 baseline + 5 from Task 1, no tests added/removed in this task).

- [ ] **Step 6: Type-check and lint**

Run: `cd web && npx tsc -b && npm run lint`
Expected: `tsc` exits 0 with no output; oxlint reports no errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/App.tsx web/src/components/Map.tsx web/src/components/JourneyCard.tsx web/src/index.css
git commit -m "feat: Start-here, Swap buttons and empty-click step-back"
```

---

## Self-Review

Checked the completed plan against `docs/superpowers/specs/2026-07-11-selection-ux-design.md`:

**Spec coverage:**
- §1 Journey-card actions: "Start here" button calls `selectOrigin(B)` → Task 2 Step 4b `onStartHere` calls `selectOrigin(selectedDest)`. "⇄ Swap" button loads B's reach then selects A iff among B's destinations, else no dest → Task 2 Step 4b `swapSelection` does exactly this via `api.getReach(destId)` + `swapDest(newReach.destinations, prevOrigin)`. ✓
- §2 Empty-map click steps back: journey card open → clear dest; origin selected → clear all; else noop → Task 1 `emptyClickAction` + Task 2 Step 3b `!pick` branch calls `onEmptyClick`. ✓
- §3 Pure helpers in `web/src/lib/selection.ts`: `emptyClickAction(hasDest, hasOrigin) -> "clearDest" | "clearAll" | "noop"` and `swapDest(destinations, oldOriginId) -> string | null` → Task 1. ✓
- §4 Wiring: App.tsx `swapSelection` async, `onEmptyClick` to MapView, callbacks to JourneyCard → Task 2 Step 4. Map.tsx `!pick` branch calls `onEmptyClick` → Task 2 Step 3. ✓
- §5 Testing: unit tests for `emptyClickAction` (3 states) and `swapDest` (present/absent) → Task 1 (5 tests). ✓
- Map click semantics unchanged (dest dot → connection, non-dest station → switch origin) → `pickFeature` logic and wiring untouched. ✓
- Out of scope items not implemented. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step has complete code. ✓

**Type consistency:** `emptyClickAction` / `swapDest` names and signatures identical across Task 1 tests, Task 1 implementation, and Task 2 App.tsx usage. `onEmptyClick` / `onStartHere` / `onSwap` prop names identical between App.tsx pass-down and Map.tsx/JourneyCard.tsx Props interfaces. ✓
