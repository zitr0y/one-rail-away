# Target Chooser Fix (AE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bug where picking "City (all stations)" in the target chooser changes the origin, and sort the target chooser choices by raw trains-to-reach from the current origin, then connection count, with absent destinations sorting last.

**Architecture:** Update `web/src/components/Map.tsx` and `web/src/lib/overlap.ts` to ensure target mode drops city entries, sorts by raw trains-to-reach from the reach file, and maintains the correct origin chooser behavior.

**Tech Stack:** React, TypeScript, Vitest, MapLibre GL.

## Global Constraints

- Item AE (from docs/superpowers/feedback-backlog.md): Target chooser in click-disambiguation changes the ORIGIN (bug). When bunched dots open the station chooser while picking a TARGET, selecting 'City (all stations)' changes the start/origin. Agreed fix direction (2026-07-14): when the chooser is opened for a target pick, (a) drop the city '(all stations)' entry entirely from the list; (b) sort the remaining stations by trains-to-reach from the CURRENT origin (fewest trains first), then by connection count. The origin chooser behaviour stays exactly as it is today.
- Trains-to-reach for a station comes from the currently loaded reach data (the reach file keyed by destination station id — a destination absent from reach data sorts last).
- All tests must pass, typecheck and build must pass.
- Commit with message 'fix(web): target chooser no longer offers city entry or reorders by origin reach (AE)' plus a body explaining the bug and fix. Do not push.

---

### Task 1: Update Overlap Functions and Types

**Files:**
- Modify: `web/src/lib/overlap.ts`
- Modify: `web/src/lib/overlap.test.ts`

**Interfaces:**
- `rawMinTrains(reach: ReachFile | null): Map<string, number>`
- Update `rankTargetChoices(choices: StationChoice[], minTrainsFiltered: Map<string, number>, minTrainsRaw: Map<string, number>): TargetChoice[]`

- [ ] **Step 1: Write rawMinTrains and update rankTargetChoices in overlap.ts**
- [ ] **Step 2: Update overlap.test.ts to test new ranking sorting logic**
- [ ] **Step 3: Run vitest for overlap tests to verify they pass**
  Run: `npx vitest run web/src/lib/overlap.test.ts`
- [ ] **Step 4: Commit intermediate changes**

---

### Task 2: Update Map Component to Integrate the Fix

**Files:**
- Modify: `web/src/components/Map.tsx`

**Interfaces:**
- Call updated `rankTargetChoices` with both filtered and raw trains maps.

- [ ] **Step 1: Update showOverlapChoice in Map.tsx to pass raw min trains map**
- [ ] **Step 2: Run all web tests**
  Run: `cd web && npm test -- --run`
- [ ] **Step 3: Commit**

---

### Task 3: Verification & Integration

- [ ] **Step 1: Verify typecheck & build**
  Run: `cd web && npm run build`
- [ ] **Step 2: Commit final commit with the required message format**
