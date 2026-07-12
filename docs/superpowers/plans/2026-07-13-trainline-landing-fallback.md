# Trainline Landing Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send the booking CTA to a reliable Trainline landing page and retain the future partner-integration requirements in project documentation.

**Architecture:** The booking helper exposes only the supported temporary destination, the canonical Trainline homepage. A research note records the verification evidence and the later Partnerize/widget integration path; the feedback backlog links to that note.

**Tech Stack:** TypeScript, Vitest, Markdown documentation.

## Global Constraints

- Do not claim that the Trainline landing page is prefilled with route or date data.
- Do not retain an unsupported affiliate query parameter.
- Keep all future affiliate/deep-link requirements in `docs/superpowers/`.

---

### Task 1: Replace the broken deep link and document the partner path

**Files:**
- Modify: `web/src/lib/booking.ts`
- Modify: `web/src/lib/booking.test.ts`
- Modify: `web/src/components/TripDetails.tsx`
- Modify: `web/.env.example`
- Modify: `web/README.md`
- Modify: `docs/superpowers/feedback-backlog.md`
- Create: `docs/superpowers/research/2026-07-13-trainline-booking-handoff.md`

**Interfaces:**
- Produces: `bookingUrl(): string`, returning the canonical Trainline landing URL.
- Consumes: `TripDetails` calls `bookingUrl()` for its external CTA.

- [x] **Step 1: Write the failing booking-link test**

Replace the current `bookingUrl` tests with:

```ts
it("uses Trainline's reliable public landing page", () => {
  expect(bookingUrl()).toBe("https://www.thetrainline.com/");
});
```

- [x] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- booking.test.ts`

Expected: FAIL because `bookingUrl` still requires route/date arguments and
returns the deprecated `trainline.eu/search` path.

- [x] **Step 3: Simplify the helper and CTA call site**

Replace `bookingUrl` with:

```ts
export function bookingUrl(): string {
  return "https://www.thetrainline.com/";
}
```

Remove `VITE_TRAINLINE_REF` and its call-site constant; change TripDetails to
use `bookingUrl()`.

- [x] **Step 4: Document the decision and future work**

Write the research note with the failed legacy route, Chronotrains referral
redirect behaviour, temporary homepage fallback, and the Partnerize registration,
approved link/widget, and prefilled-journey validation steps. Update backlog item
N to link to it; remove the stale affiliate environment variable from the web
README and example file.

- [x] **Step 5: Run verification**

Run: `npm test && npm run build && npm run lint && git diff --check`

Expected: all tests pass, build succeeds, oxlint reports no findings, and no
whitespace errors occur.

- [x] **Step 6: Commit**

```bash
git add web/src/lib/booking.ts web/src/lib/booking.test.ts web/src/components/TripDetails.tsx web/.env.example web/README.md docs/superpowers/feedback-backlog.md docs/superpowers/research/2026-07-13-trainline-booking-handoff.md docs/superpowers/plans/2026-07-13-trainline-landing-fallback.md
git commit -m "fix: use Trainline landing page for booking"
```
