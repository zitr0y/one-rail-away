# Booking Date Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users select the date sent to Trainline when booking a valid displayed journey.

**Architecture:** `booking.ts` owns small local-calendar date helpers and receives an explicit booking date when constructing the documented Trainline URL. `TripDetails` owns the selected date for its currently rendered origin/destination pair, renders a native date input, and sends the selected value to the helper.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, CSS custom properties.

## Global Constraints

- Use a native `input[type=date]`; do not add a dependency.
- Default to tomorrow in the traveller's local calendar.
- Disable dates before today in the traveller's local calendar.
- Keep the selected date while the same origin/destination pair is displayed; reset it when either station changes.
- The selected date changes only the external Trainline search URL, never the reachability computation.
- Preserve URL encoding and the existing optional affiliate query parameter.

---

### Task 1: Date-aware booking URL and native booking control

**Files:**
- Modify: `web/src/lib/booking.ts`
- Modify: `web/src/lib/booking.test.ts`
- Modify: `web/src/components/TripDetails.tsx`
- Modify: `web/src/index.css`
- Create: `web/src/components/TripDetails.test.tsx`

**Interfaces:**
- Produces: `localDate(offsetDays?: number, now?: Date): string`, an ISO calendar date in local time.
- Produces: `bookingUrl(origin: Station, dest: Station, date: string, ref: string): string`.
- Consumes: `TripDetails` receives `origin`, `destination`, a valid `dest`, `maxTrains`, and `stationsById` from `JourneyPlanner`.

- [x] **Step 1: Write the failing date-contract tests**

Replace the current call sites in `web/src/lib/booking.test.ts` so the URL test passes a fixed `"2026-08-20"` booking date and expects it in the third search-path segment. Add local-calendar tests:

```ts
import { bookingUrl, localDate } from "./booking";

it("formats a local calendar date without UTC rollover", () => {
  const now = new Date("2026-07-12T23:30:00-02:00");
  expect(localDate(0, now)).toBe("2026-07-12");
  expect(localDate(1, now)).toBe("2026-07-13");
});
```

Create `web/src/components/TripDetails.test.tsx` using
`renderToStaticMarkup` from `react-dom/server` and Vitest fake timers fixed at
`2026-07-12T12:00:00`. Render the component with a one-leg eligible journey and
assert the markup includes a date input with `value="2026-07-13"`,
`min="2026-07-12"`, and a booking href ending in `/2026-07-13/`. Render the same
destination with `maxTrains={1}` when its only journey uses two trains, and
assert the markup has no `type="date"` input.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- booking.test.ts TripDetails.test.tsx`

Expected: FAIL because `localDate` is not exported and `bookingUrl` has no date argument.

- [x] **Step 3: Implement the date helpers and explicit URL argument**

In `web/src/lib/booking.ts`, use local date parts rather than `toISOString()` and require the selected date:

```ts
export function localDate(offsetDays = 0, now = new Date()): string {
  const date = new Date(now);
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function bookingUrl(origin: Station, dest: Station, date: string, ref: string): string {
  const params = new URLSearchParams();
  if (ref) params.set("aff", ref);
  const route = [origin.name, dest.name, date].map(encodeURIComponent).join("/");
  return `https://www.trainline.eu/search/${route}/${params.size ? `?${params}` : ""}`;
}
```

- [x] **Step 4: Run the focused test to verify it passes**

Run: `npm test -- booking.test.ts TripDetails.test.tsx`

Expected: all booking and TripDetails date tests pass.

- [x] **Step 5: Add the controlled native date input to TripDetails**

Import `useEffect` and `useState`, initialize `bookingDate` with `localDate(1)`, and reset it when the station pair changes:

```tsx
const [bookingDate, setBookingDate] = useState(() => localDate(1));
const today = localDate();

useEffect(() => {
  setBookingDate(localDate(1));
}, [origin.id, destination.id]);
```

Immediately before the booking anchor, render:

```tsx
<label className="booking-date">
  <span>Travel date</span>
  <input type="date" value={bookingDate} min={today}
         onChange={(event) => setBookingDate(event.target.value)} />
</label>
```

Pass `bookingDate` as the third argument to `bookingUrl`. Replace the old fine print with `Pick your time at checkout`.

- [x] **Step 6: Style the native control with existing panel tokens**

Add a compact `.booking-date` block to `web/src/index.css` using `var(--text-subtle)`, `var(--border)`, `var(--surface)`, `var(--text)`, and an 8px border radius. Keep the browser's native date affordance intact.

- [x] **Step 7: Run the complete web verification**

Run: `npm test && npm run build && npm run lint`

Expected: all tests pass, the production build succeeds, and oxlint reports no findings.

- [x] **Step 8: Commit the implementation**

```bash
git add web/src/lib/booking.ts web/src/lib/booking.test.ts web/src/components/TripDetails.tsx web/src/components/TripDetails.test.tsx web/src/index.css
git commit -m "feat: add booking date picker"
```
