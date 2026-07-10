# Selected-Journey Highlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** While a journey card is open, render that journey's line thick and full-opacity on top, and dim all other reach lines to 0.12 opacity.

**Architecture:** A dedicated `reach-lines-selected` MapLibre layer reads the existing `reach-lines` GeoJSON source, filtered to the selected destination id. Selection changes only touch `setFilter` + `setPaintProperty` in an effect separate from `syncData`, so selecting a journey never triggers the `easeTo` re-center. Expression logic lives in a pure, vitest-covered helper.

**Tech Stack:** React + TypeScript + MapLibre GL (web/), vitest, oxlint.

Spec: `docs/superpowers/specs/2026-07-10-journey-highlight-design.md` (approved 2026-07-10).

## Global Constraints

- Branch: `journey-highlight` (already exists and is checked out — do not create it).
- All web commands run from `web/`: `npm test` (vitest run), `npm run build` (tsc -b && vite build), `npm run lint` (oxlint).
- Destination dots (`reach-dots`), grey all-station dots, click handling, and `pickFeature` precedence are untouched.
- Dim opacity is exactly **0.12**; normal line opacity is exactly **0.75**; highlight width is exactly **4**.
- The user does visual/browser evaluation themselves — verify via tests/build/lint only, never claim visual correctness.
- Commit after every task. Line length 100.

---

### Task 1: Pure highlight helpers (`web/src/lib/highlight.ts`)

**Files:**
- Create: `web/src/lib/highlight.ts`
- Test: `web/src/lib/highlight.test.ts`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces (Task 2 relies on these exact names/signatures):
  - `selectedLineFilter(id: string | null): ["==", ["get", "id"], string]` — MapLibre
    filter expression matching the line feature whose `id` property equals `id`;
    for `null` it compares against `""`, which matches no station id.
  - `baseLineOpacity(hasSelection: boolean): number` — `0.12` when a journey is
    selected, `0.75` otherwise (single source of truth for the base line opacity).

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/highlight.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { baseLineOpacity, selectedLineFilter } from "./highlight";

describe("selectedLineFilter", () => {
  it("matches the line feature with the selected destination id", () => {
    expect(selectedLineFilter("8507000")).toEqual(["==", ["get", "id"], "8507000"]);
  });

  it("matches nothing when no journey is selected", () => {
    expect(selectedLineFilter(null)).toEqual(["==", ["get", "id"], ""]);
  });
});

describe("baseLineOpacity", () => {
  it("dims the other lines strongly while a journey is selected", () => {
    expect(baseLineOpacity(true)).toBe(0.12);
  });

  it("keeps normal opacity when nothing is selected", () => {
    expect(baseLineOpacity(false)).toBe(0.75);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- highlight`
Expected: FAIL — cannot resolve `./highlight` (module does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/highlight.ts`:

```ts
// Styling for backlog item J (selected-journey highlight). The thick-line treatment is
// provisional: to be revisited for an animated train once branding (item D) lands.
export type SelectedLineFilter = ["==", ["get", "id"], string];

// "" is never a station id, so a null selection matches no feature.
export function selectedLineFilter(id: string | null): SelectedLineFilter {
  return ["==", ["get", "id"], id ?? ""];
}

export function baseLineOpacity(hasSelection: boolean): number {
  return hasSelection ? 0.12 : 0.75;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- highlight`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/highlight.ts web/src/lib/highlight.test.ts
git commit -m "feat: pure helpers for selected-journey highlight (backlog J)"
```

---

### Task 2: Wire the highlight layer into Map.tsx and App.tsx

**Files:**
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/App.tsx:55-56` (MapView call site)

**Interfaces:**
- Consumes (from Task 1, `web/src/lib/highlight.ts`):
  - `selectedLineFilter(id: string | null): ["==", ["get", "id"], string]`
  - `baseLineOpacity(hasSelection: boolean): number`
- Produces: `MapView` gains required prop `selectedDest: string | null`.

- [ ] **Step 1: Add the prop and import in Map.tsx**

In `web/src/components/Map.tsx`, add to the imports:

```ts
import { baseLineOpacity, selectedLineFilter } from "../lib/highlight";
```

Add to `interface Props` (after `maxMinutes: number;`):

```ts
selectedDest: string | null;
```

- [ ] **Step 2: Add the static highlight layer at map load**

In the `m.on("load", …)` handler, between the existing `reach-lines` and `reach-dots`
`addLayer` calls, insert (insertion order puts it above `reach-lines`, below
`reach-dots`, so dots stay on-top click targets):

```ts
m.addLayer({
  id: "reach-lines-selected", type: "line", source: "reach-lines",
  layout: { "line-cap": "round", "line-join": "round" },
  filter: selectedLineFilter(null) as never,
  paint: {
    "line-color": bucketColor as never,
    "line-width": 4,
    "line-opacity": 1,
  },
});
```

Also replace the hardcoded base opacity in the `reach-lines` paint block so Task 1's
helper is the single source of truth:

```ts
"line-opacity": baseLineOpacity(false),
```

- [ ] **Step 3: Add the highlight sync (separate from syncData)**

After the `syncData` function in `Map.tsx`, add:

```ts
function syncHighlight() {
  const m = map.current;
  if (!m) return;
  const { selectedDest } = propsRef.current;
  m.setFilter("reach-lines-selected", selectedLineFilter(selectedDest) as never);
  m.setPaintProperty("reach-lines", "line-opacity", baseLineOpacity(selectedDest !== null));
}
```

In the `m.on("load", …)` handler, directly after the existing `syncData();` call, add
`syncHighlight();` (the map loads asynchronously, so the effect below can fire before
the map exists — this call applies whatever selection state arrived in the meantime).

After the existing `useEffect(syncData, …)` line, add:

```ts
useEffect(syncHighlight, [props.selectedDest]);
```

Deliberately NOT part of the `syncData` effect: `syncData` ends in `easeTo`
re-centering, and selecting a journey must not move the map (spec requirement).

- [ ] **Step 4: Pass selectedDest from App.tsx**

In `web/src/App.tsx`, the `MapView` call site becomes:

```tsx
<MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
         selectedDest={selectedDest}
         onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest} />
```

- [ ] **Step 5: Run full verification**

Run (from `web/`):
- `npm test` — Expected: all suites PASS (29 tests: 25 existing + 4 from Task 1).
- `npm run build` — Expected: tsc + vite build succeed with no errors.
- `npm run lint` — Expected: no warnings/errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/Map.tsx web/src/App.tsx
git commit -m "feat: highlight selected journey line, dim the rest (backlog J)"
```
