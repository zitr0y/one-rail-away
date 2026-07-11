# Selection UX Round 2: Promote, Swap, Empty-Click Step-Back

Date: 2026-07-11
Status: approved
Context: backlog item F. The 2026-07-09 fix (`6413a1b`) already shipped the
single precedence click handler (`pickfeature.ts`), the status-bar × unselect,
and Escape-to-clear. What remains is the structural ambiguity: while origin A
is selected, clicking station B shows the connection if B is a destination dot
but silently switches origin otherwise, and a destination can never become the
new origin by clicking.

## Design

### 1. Journey-card actions

`web/src/components/JourneyCard.tsx` gains two buttons beside the existing ×:

- **"Start here"** — promotes the shown destination B to the new origin:
  exactly `selectOrigin(B)` (loads B's full fan, journey card closes because
  `selectedDest` resets).
- **"⇄ Swap"** — origin A + dest B become origin B + dest A: load B's reach,
  then select A as destination **iff A is among B's destinations**; otherwise
  fall back to origin B with no destination selected (no error shown).

Click semantics on the map itself are unchanged: destination dot shows the
connection, non-destination station switches origin.

### 2. Empty-map click steps back

A click with no station under the cursor (`pickFeature` returns null — veil
clicks count as empty) steps the selection back, mirroring Escape:

- journey card open → clear `selectedDest` only (back to the full fan)
- else if an origin is selected → clear everything
- else → no-op

### 3. Pure helpers (`web/src/lib/selection.ts`, new)

Following the pickfeature/coverage pattern — logic unit-testable without a map:

- `emptyClickAction(hasDest: boolean, hasOrigin: boolean) ->
  "clearDest" | "clearAll" | "noop"`
- `swapDest(destinations: {id: string}[], oldOriginId: string) -> string | null`
  — `oldOriginId` if present among the new origin's destinations, else null.

### 4. Wiring

- `App.tsx`: `swapSelection()` (async: `api.getReach(destId)` → `setReach` +
  `setSelectedDest(swapDest(...))`); pass `onEmptyClick` to MapView and the two
  new callbacks to JourneyCard.
- `Map.tsx`: in the existing click handler, the `!pick` branch calls
  `props.onEmptyClick()` instead of returning silently.

### 5. Testing

- Unit tests for `emptyClickAction` (3 states) and `swapDest` (present/absent).
- No pipeline/server changes. Visual verification is the user's.

## Out of scope

- Second-click-promotes (rejected: invisible, accidental triggers).
- Status-bar placement for promote/swap (journey card is where attention is).
- Touch/mobile affordances — revisit with branding (backlog D).
