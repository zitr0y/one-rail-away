# Friendly Booking Date Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw booking date field with a large blue, friendly date selector that opens the native calendar on demand.

**Architecture:** Pure date helpers convert the ISO booking value into relative/friendly text and calendar-day offsets. `TripDetails` uses those helpers to render previous, current-date, and next controls, while keeping a rendered native date input as the source of calendar selection and the existing Trainline URL contract.

**Tech Stack:** React 19, TypeScript, CSS custom properties, Vitest.

## Global Constraints

- Do not add a date-picker dependency.
- Default to tomorrow, label it `Tomorrow`, and disable the previous-day button on today.
- The centre control opens the browser's native calendar; use `showPicker()` with click fallback.
- Make the previous, centre, and next controls large, rounded, brand blue buttons with white content.
- Remove the booking checkout fine print.
- Keep direct calendar selection, URL encoding, affiliate parameters, and reachability behaviour unchanged.

---

### Task 1: Friendly calendar helpers and blue date selector

**Files:**
- Modify: `web/src/lib/booking.ts`
- Modify: `web/src/lib/booking.test.ts`
- Modify: `web/src/components/TripDetails.tsx`
- Modify: `web/src/components/TripDetails.test.tsx`
- Modify: `web/src/index.css`

**Interfaces:**
- Produces: `shiftDate(date: string, offsetDays: number): string`.
- Produces: `friendlyDateLabel(date: string, today?: string): string`.
- Consumes: `bookingDate` ISO state inside `TripDetails`; `bookingUrl(origin, destination, bookingDate, REF)` remains unchanged.

- [x] **Step 1: Write failing helper and component-markup tests**

In `web/src/lib/booking.test.ts`, import `shiftDate` and `friendlyDateLabel`; add:

```ts
it("moves ISO dates by local calendar days", () => {
  expect(shiftDate("2026-07-13", -1)).toBe("2026-07-12");
  expect(shiftDate("2026-07-31", 1)).toBe("2026-08-01");
});

it("uses friendly labels around today", () => {
  expect(friendlyDateLabel("2026-07-12", "2026-07-12")).toBe("Today");
  expect(friendlyDateLabel("2026-07-13", "2026-07-12")).toBe("Tomorrow");
  expect(friendlyDateLabel("2026-07-14", "2026-07-12")).toBe("Tue 14 Jul");
});
```

Replace the visible-input assertions in `TripDetails.test.tsx` with assertions
for `aria-label="Previous day"`, `aria-label="Next day"`, centre text
`Tomorrow`, the preserved `type="date"` input and `min="2026-07-12"`, and
the `/2026-07-13/` booking path. Assert that `Pick your time at checkout` is
absent.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- booking.test.ts TripDetails.test.tsx`

Expected: FAIL because the helper exports and new date-selector markup do not
exist.

- [x] **Step 3: Implement the pure date helpers**

In `web/src/lib/booking.ts`, parse ISO dates at local noon, then implement:

```ts
export function shiftDate(date: string, offsetDays: number): string {
  return localDate(offsetDays, new Date(`${date}T12:00:00`));
}

export function friendlyDateLabel(date: string, today = localDate()): string {
  const day = (value: string) => Date.UTC(...value.split("-").map((part, index) =>
    index === 1 ? Number(part) - 1 : Number(part)));
  const difference = (day(date) - day(today)) / (24 * 60 * 60 * 1000);
  if (difference === 0) return "Today";
  if (difference === 1) return "Tomorrow";
  return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" })
    .format(new Date(`${date}T12:00:00`)).replace(",", "");
}
```

- [x] **Step 4: Implement the date-selector component**

In `TripDetails.tsx`, import `useRef`, `friendlyDateLabel`, and `shiftDate`.
Keep the native `input[type=date]` rendered with the current `value`, `min`, and
`onChange`, but make it visually hidden and give it a ref. Replace the current
label with three buttons: previous calls `setBookingDate(shiftDate(bookingDate,
-1))`, next calls it with `1`, and centre calls `inputRef.current?.showPicker()`
with `inputRef.current?.click()` fallback. Disable previous when
`bookingDate === today`; remove the fine-print paragraph.

- [x] **Step 5: Add blue control styling**

Replace the `.booking-date` rules with a three-column `.booking-date-picker`
grid. Make all buttons blue (`#003399`), white, rounded, at least 44px high,
and use the existing hover/focus style conventions. Make the centre button the
widest column and leave the hidden native input rendered but not visible.

- [x] **Step 6: Run focused tests to verify they pass**

Run: `npm test -- booking.test.ts TripDetails.test.tsx`

Expected: all helper and TripDetails booking-date tests pass.

- [x] **Step 7: Run full verification**

Run: `npm test && npm run build && npm run lint && git diff --check`

Expected: all tests pass, build succeeds, oxlint reports no findings, and the
diff has no whitespace errors.

- [x] **Step 8: Commit the implementation**

```bash
git add web/src/lib/booking.ts web/src/lib/booking.test.ts web/src/components/TripDetails.tsx web/src/components/TripDetails.test.tsx web/src/index.css docs/superpowers/plans/2026-07-12-friendly-booking-date-picker.md
git commit -m "feat: simplify booking date selector"
```
