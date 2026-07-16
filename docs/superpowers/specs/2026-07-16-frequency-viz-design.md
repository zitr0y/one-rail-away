# Frequency visualisation + departure-time data (backlog item AO, enables AQ) — design

Approved by user 2026-07-16 (design round in-session). Research input:
agent data-flow study 2026-07-16 (scratchpad `ao-data-findings.md`; key facts
restated here so this spec is self-contained).

## Problem

Frequency copy ("24.9 trains per day", "6/7 sampled days") is not understandable
to first-time users (dad feedback, 2026-07-15). Wanted: a compact, colourful
per-day visualisation, split morning/afternoon/evening, expandable to the full
connection tables — informative but never in your face.

## Decisions (user-approved)

1. **Pipeline emits a day×hour histogram** per destination (counts of sampled
   departures per sampled day × hour of day). +24 KB gzip on the largest origin
   (Frankfurt Hbf, 61→~85 KB gzip, +39%). Rationale: feeds the daypart viz
   (client sums hours into buckets) AND gives AQ (departure-time filter) an
   hour-granular basis for filtering counts. Known limit, accepted: it cannot
   recompute the *best journey* per time window — if AQ later needs that, a
   full departure list (+77%) is the upgrade path.
2. **Viz form: 7×3 heat strip.** One small row per sampled day, split into
   morning / afternoon / evening cells; colour intensity = connection count.
   Clicking expands the existing full connection tables (available, not
   in-your-face).

## Facts about the current code (from the research pass)

- RAPTOR already iterates all sampled departures but keeps only the fastest
  journey per train-count tier (`pipeline/raptor.py:230`) — so a compute
  change is required to retain departure counts, not just a serialization one.
- Reach files are written per origin by `pipeline/compute.py` (`_aggregate_reach`
  / `_write_reach`); the web app reads frequency fields in the trip/planner
  components.
- **Trap:** GTFS times are parsed as local minutes-since-midnight with no
  timezone normalization (`pipeline/gtfs.py:74-77`). Histogram hours will be
  *feed-local* hours. Accepted for v1 (dayparts are local-time concepts anyway);
  the cross-timezone bug is tracked separately in the backlog.

## 1. Pipeline

- During per-date reachability, record for each reached destination the
  departure time (origin departure, minutes since midnight, feed-local) of
  every distinct direct-or-routed connection counted for that date — the same
  population `direct_per_day`/frequency counts draw from, so the viz never
  contradicts the existing numbers.
- Aggregate into `histogram: {date: [24 ints]}` (sampled dates as keys, hour
  buckets) per destination; omit the field entirely when all-zero to bound
  size. Sparse zeros compress well; do not invent a denser encoding until
  measured need.
- `direct_per_day`, best-journey selection, and all existing fields unchanged.

## 2. Web UI

- Dayparts: morning = hours 5–11, afternoon = 12–17, evening = 18–23
  (0–4 counts into evening of the previous day? No — keep 0–4 in morning
  bucket of the same day for v1 simplicity; night trains are a curiosity here,
  not a correctness case).
- The heat strip replaces the raw "6/7 sampled days" line in the destination
  details: 7 day-rows (or however many sampled days exist) × 3 cells, colour
  scale from theme tokens (respect dark mode), a11y: each cell gets an
  aria-label "Tue morning: 4 connections".
- Clicking the strip toggles the full connection table (already exists).
- Keep the cautious-sampling language nearby (item B constraint: "evidence,
  not promise") — the strip shows *sampled* connections.
- Schema handling: `histogram` is optional; old reach files without it render
  the current text fallback (no hard schema version bump).

## 3. Testing

- Pipeline: synthetic fixture with known departures across 2 sampled dates →
  assert exact histogram matrices, assert omission when empty, assert
  `direct_per_day` unchanged.
- Web: heat strip renders from a fixture histogram (bucket sums, aria-labels,
  fallback path without histogram field). Synthetic ids only (item AD rule).

## Out of scope

- AQ's actual filter UI (separate design; this spec only guarantees the data).
- Timezone normalization (tracked in backlog smaller notes).
- Seasonal wording rework (item AF) — the strip may make gaps visible; fine.
- Any change to journey/transfer legs (item U owns that schema).
