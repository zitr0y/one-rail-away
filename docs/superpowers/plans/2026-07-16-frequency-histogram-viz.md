# Frequency Histogram Visualisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit an optional per-destination sampled-date × feed-local-hour connection histogram from the same departure population as the existing direct-frequency counts, then render it as an accessible, theme-aware daypart heat strip that expands the existing connection details.

**Architecture:** Keep `compute_reachability` and its best-journey selection byte-semantically unchanged. Add a separate RAPTOR evidence pass keyed by each distinct first train departure from the origin; that pass records whether each destination is reachable and whether it is reached directly, but never multiplies a departure for alternative onward trains or footpaths. `pipeline/compute.py` will derive both its existing direct counts and the new 24-hour rows from that one evidence population, excluding the `extra_trips` probe. `Destination` will serialize a validated optional `histogram`, and `TripDetails` will sum its hours into three client-side dayparts, render theme-token heat levels, and use the strip button to toggle the existing `.legs` connection list. Old reach files retain the current text and expanded-list behavior.

**Tech Stack:** Python 3.14, Pydantic 2.13, pytest, React 19, TypeScript 6, Vitest 4, CSS custom properties.

## Global Constraints

- The approved design at `docs/superpowers/specs/2026-07-16-frequency-viz-design.md` is authoritative, with the supervisor's explicit daypart correction taking precedence: morning is hours 0–11, afternoon 12–17, evening 18–23.
- All new tests use synthetic station ids, synthetic dates, and directly constructed `Trip` objects. Never use an id from `data/out`, a checked-in live feed, or `tests/test_international.py`.
- A connection is identified by its distinct first train departure event from the origin. It is counted once per destination/date even if several onward trains, transfer paths, or best-journey tiers reach that destination.
- Direct counts are the direct subset of that same connection population. Do not calculate histogram and `direct_per_day` from independent scans.
- Histogram departure hours are feed-local. Preserve minutes-since-midnight and bucket with `(departure_min // 60) % 24`; add no timezone conversion and do not shift 00:00–04:59 to another date.
- A transfer footpath can make a first-train departure reach another train, but it never creates a departure label and never increments a histogram cell by itself.
- Include every sampled key from `trips_by_date` as a histogram row once a destination has any sampled connection; zero rows are meaningful. Never include the `extra_trips` pseudo-date. Omit the entire field when every sampled row is zero.
- Keep `compute_reachability`, `direct_per_day`, every `Frequency` field, best-journey tie-breaking, journey/transfer-leg schemas, and server artifact pass-through unchanged.
- The web computes dayparts from the 24 bins. Do not add pre-aggregated dayparts to the reach schema and do not implement backlog item AQ's time filter.
- Do not change `server/app.py`, schema-version metadata, map geometry, generated `data/out/*`, or live configuration. Do not push commits.
- Baseline recorded by the supervisor after intra-city transfers: `tests/test_cities.py` 9, `tests/test_models.py` 4, `tests/test_raptor.py` 17, `tests/test_compute.py` 17, and web 190 cases across 23 files. `uv run pytest --collect-only -q` collects 260 cases before this plan.

---

### Task 1: Add a validated, omission-safe histogram to the reach model

**Expected diff surface:**
- Modify: `pipeline/models.py`
- Modify: `tests/test_models.py`
- No other files.

**Public contract introduced:**

```python
HourlyCount = Annotated[int, Field(ge=0)]
HourlyBins = Annotated[list[HourlyCount], Field(min_length=24, max_length=24)]


class Destination(BaseModel):
    id: str
    direct_per_day: int
    journeys: list[Journey]
    frequency: "Frequency | None" = None
    histogram: dict[str, HourlyBins] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
```

Normalize an all-zero dictionary to `None` with a `field_validator(..., mode="after")`, so omission is a model invariant rather than a caller convention. A dictionary with at least one non-zero cell keeps all supplied date rows, including all-zero rows.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add three failing model tests**

Add exactly these cases to `tests/test_models.py` (4 -> 7):

1. `test_destination_histogram_serializes_and_round_trips_exact_schema`
   - Construct a synthetic `Destination` with two ISO-date keys and exactly 24 non-negative integers per row.
   - Put counts in hour 0, 11, 12, 17, 18, and 23 so boundary data survives unchanged.
   - Assert `model_dump(by_alias=True)["histogram"]` equals the input dictionary exactly, then round-trip through `ReachFile.model_dump_json` / `ReachFile.model_validate_json` and assert exact equality again.
2. `test_destination_omits_absent_and_all_zero_histogram`
   - Serialize one destination with no histogram and one with two all-zero 24-bin rows.
   - Assert `"histogram"` is absent from both serialized destination dictionaries, not present as `null` or `{}`.
3. `test_destination_histogram_rejects_wrong_length_or_negative_bins`
   - In one pytest case, use `pytest.raises(ValidationError)` for a 23-bin row, a 25-bin row, and a 24-bin row containing `-1`.

- [ ] **Step 2: Run the focused tests and confirm the expected failures**

```bash
uv run pytest tests/test_models.py -q
```

Expected before implementation: the histogram keyword is ignored/absent from serialization, so the exact-schema test fails; malformed rows are not yet validated. Do not proceed if an existing transfer-model test fails.

- [ ] **Step 3: Implement the aliases, field, validation, and omission policy**

Import `Annotated` and `field_validator`. Add `HourlyCount` / `HourlyBins` beside the reach-file models, then add `Destination.histogram` exactly as above after `frequency`.

The validator must return `None` only when the value is `None`, empty, or every integer in every row is zero:

```python
@field_validator("histogram", mode="after")
@classmethod
def omit_empty_histogram(cls, value):
    if not value or not any(count for row in value.values() for count in row):
        return None
    return value
```

Do not validate calendar membership or timezone here; the model validates only the non-negative 24-bin row shape. Do not move the field into `Frequency`.

- [ ] **Step 4: Verify the focused model file**

```bash
uv run pytest tests/test_models.py -q
```

Expected: `7 passed` (4 before, 7 after; +3).

---

### Task 2: Collect each origin train departure once without changing best journeys

**Expected diff surface:**
- Modify: `pipeline/raptor.py`
- Modify: `tests/test_raptor.py`
- No model, compute, or web files yet.

**Public contract introduced:**

```python
class DepartureEvidence(NamedTuple):
    departure_min: int
    direct: bool


def compute_departure_evidence(
    trips: list[Trip],
    origin: str,
    max_trains: int = 3,
    transfer_min: int = 10,
    footpaths: list[ResolvedTransfer] | None = None,
) -> dict[str, list[DepartureEvidence]]:
    """One entry per distinct first train departure that can reach each destination."""
```

The returned list may contain repeated `departure_min` values when two distinct trips depart in the same minute. It is stable in source trip-index order. `direct=True` means that same first train calls at the destination after boarding at the origin.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add three failing synthetic RAPTOR tests**

Append exactly these cases to `tests/test_raptor.py` (17 -> 20):

1. `test_departure_evidence_keeps_distinct_direct_trips_at_the_same_minute`
   - Construct three direct trips from `origin` to `destination`: two depart at minute 480 and one at minute 795.
   - Assert the evidence is exactly `[DepartureEvidence(480, True), DepartureEvidence(480, True), DepartureEvidence(795, True)]` in trip order.
   - Assert ordinary `compute_reachability` still selects the same fastest direct journey as it did before this helper exists.
2. `test_departure_evidence_counts_one_origin_departure_once_across_onward_options`
   - One first train departs `origin` at 480 and reaches `junction`; two legal onward trains reach `destination` at different times.
   - Assert `destination` contains exactly `[DepartureEvidence(480, False)]`, not two records, while `junction` has the same departure marked `direct=True`.
3. `test_departure_evidence_footpath_reaches_but_never_duplicates_a_departure`
   - One train reaches `south`, a synthetic 20-minute `metro` footpath reaches boarding readiness at `north`, and two legal onward trains reach `destination`.
   - Assert `destination` is absent without the footpath and equals `[DepartureEvidence(1435, False)]` with it.
   - This 23:55 departure deliberately proves the helper preserves unwrapped feed-local minutes; also assert the transfer does not create a second evidence record.

Use only `_stop` and directly constructed synthetic `Trip` objects. No GTFS fixture or production id is allowed in these three tests.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

```bash
uv run pytest tests/test_raptor.py -q
```

Expected before implementation: import/attribute failure because `DepartureEvidence` and `compute_departure_evidence` do not exist. The existing 17 best-journey/footpath cases must still pass.

- [ ] **Step 3: Seed one immutable label per first train departure**

Add the evidence helper without calling or changing `compute_reachability`:

1. Reuse `_index(trips)` and enumerate `by_station.get(origin, ())` in ascending trip index.
2. For each trip, use its first stop whose station is `origin` as that trip's single departure event. The label identity is the internal `(trip_index, board_index)` pair, not the minute value.
3. Seed round-one train arrivals from every later stop on that same trip. Mark those downstream destinations direct for that label. Exclude `origin` itself.
4. Keep each label's earliest train arrival per station, but keep labels independent; never let an earlier label erase a later origin departure.
5. Record a label at most once per destination across all rounds. Preserve `direct=True` if the first train directly served that destination, even if a later round can also return there.

This implements the documented existing meaning of `_direct_counts`: distinct trips, with mid-route boarding allowed. Do not key labels by `departure_min`, train display name, or `trip_id`, because any of those can collide.

- [ ] **Step 4: Propagate each label through later train rounds and fresh footpaths**

For rounds 2 through `max_trains`, apply the same readiness rules as `_raptor` independently for each label:

1. Start readiness at each prior train arrival plus `transfer_min`.
2. Relax each configured footpath once in both directions from the prior train-arrival dictionary; candidate readiness is `arrival + seconds // 60`.
3. Do not use newly relaxed targets as sources, so footpaths cannot chain.
4. A footpath target becomes evidence only after an onward train is boarded and alights; a footpath can never be the first or last leg.
5. Scan only trips calling at a ready station, in ascending trip index, and use `ready_time <= stop_departure` exactly like `_raptor`.
6. Carry prior train arrivals forward between rounds and stop early for a label when a round produces no new train arrival.

Factor a small private readiness/candidate helper only if it can be shared without changing `Parent` or `_raptor` tie-breaking. Otherwise keep the evidence propagation isolated and covered by the boundary/footpath tests. Do not materialize `Journey`, `Leg`, or `TransferLeg` objects in this pass.

- [ ] **Step 5: Verify evidence and unchanged journey behavior**

```bash
uv run pytest tests/test_raptor.py -q
```

Expected: `20 passed` (17 before, 20 after; +3). The original `compute_reachability` return type and every pre-existing journey assertion remain unchanged.

---

### Task 3: Derive direct frequency and exact sampled-date histograms from one population

**Expected diff surface:**
- Modify: `pipeline/compute.py`
- Modify: `tests/test_compute.py`
- No changes to worker signatures, `server/app.py`, or artifact helpers.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add one reusable two-date graph writer and three failing compute tests**

Use a private helper in `tests/test_compute.py` that writes only synthetic `stations.json`, `trips.json`, and (when required) a synthetic `cities.toml`. Keep all dates as literal ISO strings and all station ids as words such as `origin`, `junction`, `south`, `north`, and `destination`.

Add exactly these cases (17 -> 20):

1. `test_compute_writes_exact_two_date_hourly_histogram_without_changing_frequency`
   - Date `2026-07-14` has direct `origin -> destination` trips departing at 00:15, 11:45, and 12:05; date `2026-07-15` has one at 18:30.
   - Run `compute_all(..., workers=1)` and inspect `reach_origin.json`.
   - Assert histogram keys are exactly those two dates in sample order, each row has length 24, and the matrices equal literal expected lists: Tuesday has `1` at hours 0, 11, and 12; Wednesday has `1` at hour 18; every other cell is zero.
   - Assert `direct_per_day == 2`, `frequency.direct_trips == 4`, `direct_days == 2`, and `direct_per_active_day == 2.0`, pinning all existing direct-frequency arithmetic.
2. `test_compute_histogram_counts_a_routed_footpath_departure_once`
   - On one sampled date, one train departs `origin`, reaches `south`, uses the configured fresh `south -> north` footpath, and has two feasible onward trains from `north` to `destination`.
   - Assert the destination histogram sum is exactly one in the first train's departure hour, `direct_per_day == 0`, `frequency.direct_trips == 0`, and the selected journey still contains train/transfer/train with `trains == 2`.
3. `test_compute_omits_histogram_for_extra_only_destination`
   - Give every sampled date an empty trip list and put one direct synthetic trip only in `extra_trips`.
   - Assert the destination remains serialized (existing coverage behavior), `direct_per_day == 0`, and the JSON destination has no `histogram` key.

- [ ] **Step 2: Run the focused tests and confirm the expected failures**

```bash
uv run pytest tests/test_compute.py -q
```

Expected before implementation: the destination JSON has no histogram; the 17 existing compute cases still pass aside from the already-known intermittent Python 3.14 multiprocessing flake in `test_compute_all_sets_is_capital`. If that exact test flakes, rerun it alone and do not alter feature code.

- [ ] **Step 3: Replace the independent direct scan with shared departure evidence**

Import `compute_departure_evidence` beside `compute_reachability`. Remove `_direct_counts` and its `Counter` import after all call sites are replaced.

Inside `_aggregate_reach`, retain the existing per-date `compute_reachability(...)` call exactly for best journeys. For the same `trips`, `station_id`, and `footpaths`, call `compute_departure_evidence(...)` once, then populate both structures from each returned `DepartureEvidence`:

```python
directs: dict[str, dict[str, int]] = {}
histograms: dict[str, dict[str, list[int]]] = {}

for dest, departures in departure_evidence.items():
    direct_count = sum(item.direct for item in departures)
    if direct_count:
        directs.setdefault(dest, {})[day] = direct_count
    bins = [0] * 24
    for item in departures:
        bins[item.departure_min // 60 % 24] += 1
    if any(bins):
        histograms.setdefault(dest, {})[day] = bins
```

This replacement, rather than a second trip scan, is the invariant that prevents histogram/direct contradictions. Do not add footpaths to a count, count each onward alternative, or derive counts from the winning `Journey.legs`.

- [ ] **Step 4: Attach complete sampled-date rows while excluding `extra_trips`**

Keep `extra_evidence = compute_reachability(extra_trips or [], ...)` exactly as journey-only evidence. Do not call `compute_departure_evidence` for `extra_trips`.

When constructing each sampled destination, build rows in `sample_dates` order:

```python
zero_row = [0] * 24
histogram = {
    day: histograms.get(dest, {}).get(day, zero_row).copy()
    for day in sample_dates
}
```

Pass `histogram=histogram` to `Destination`; Task 1's validator omits it when all rows are zero. Use a fresh/copy row so no destination or date shares a mutable list. Leave covered-date selection, `_frequency`, `direct_per_day = round(freq.direct_per_active_day or 0)`, best-tier collapse, and `_write_reach` unchanged.

- [ ] **Step 5: Verify focused pipeline files and serialized output**

```bash
uv run pytest tests/test_models.py tests/test_raptor.py tests/test_compute.py -q
```

Expected: `47 passed` (7 models + 20 RAPTOR + 20 compute). If the exact known capital multiprocessing test flakes, rerun `tests/test_compute.py::test_compute_all_sets_is_capital` alone; any other focused failure is new and must stop implementation.

---

### Task 4: Render an accessible theme-token daypart heat strip and toggle details

**Expected diff surface:**
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/components/TripDetails.tsx`
- Modify: `web/src/components/TripDetails.test.tsx`
- Modify: `web/src/index.css`
- No map, API, planner, or pipeline files.

**Type contract introduced:**

```typescript
export type HourlyHistogram = Record<string, number[]>;

export interface Destination {
  id: string;
  direct_per_day: number;
  journeys: Journey[];
  frequency?: Frequency | null;
  histogram?: HourlyHistogram;
}
```

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add four failing `TripDetails` cases**

Add `// @vitest-environment jsdom` at the top of `web/src/components/TripDetails.test.tsx` so one interaction case can mount React state. Add exactly these cases (7 -> 11):

1. `it("renders feed-local histogram hours in the three exact dayparts", ...)`
   - Use synthetic dates `2026-07-14` and `2026-07-15` and literal 24-bin rows with boundary counts at hours 0, 11, 12, 17, 18, and 23.
   - Render static markup and assert exact cell labels including `Tue morning: 4 connections`, `Tue afternoon: 5 connections`, and `Tue evening: 6 connections`; assert Wednesday's three zero/non-zero labels too.
   - Assert the visible row labels are `Tue` then `Wed`, proving chronological ISO-key sorting, and assert the cautious text contains `Sampled timetable evidence` and `not a promise`.
2. `it("assigns zero-to-four heat levels relative to the busiest daypart", ...)`
   - Use daypart totals 0, 1, 2, 4 and assert rendered cells have `frequency-heat-level-0`, `-1`, `-2`, and `-4` according to the quantizer below.
   - Assert cells carry no inline literal background colour; CSS theme tokens own their colours.
3. `it("clicking the heat strip toggles the existing connection list", ...)`
   - Mount `TripDetails` with `createRoot` and `act`, using a histogram-bearing synthetic destination.
   - Assert the strip button starts with `aria-expanded="false"`, its `aria-controls` points to the connection-list id, and the `.legs` list is initially hidden.
   - Click once and assert `aria-expanded="true"` plus visible train rows; click again and assert it collapses. Unmount in cleanup.
4. `it("falls back to current frequency text and expanded connections without a histogram", ...)`
   - Render a destination with `frequency` but no `histogram`.
   - Assert no heat strip exists, the exact current `frequencyLabel(dest)` text is present, and the existing `.legs` list is rendered expanded.

- [ ] **Step 2: Run the focused web test and confirm the expected failures**

```bash
cd web
npx vitest run src/components/TripDetails.test.tsx
```

Expected before implementation: TypeScript rejects the histogram fixture or no heat-strip markup/toggle exists. The existing seven booking, transfer, and frequency-label cases must remain green.

- [ ] **Step 3: Add the optional web type and pure daypart helpers**

Add `HourlyHistogram` and optional `Destination.histogram` to `web/src/lib/types.ts`; do not change `Frequency` or `ReachFile`.

In `TripDetails.tsx`, define these exact client-side buckets and deterministic English weekday labels:

```typescript
const DAYPARTS = [
  { name: "morning", start: 0, end: 12 },
  { name: "afternoon", start: 12, end: 18 },
  { name: "evening", start: 18, end: 24 },
] as const;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
```

- Sort `Object.entries(histogram)` by ISO date before rendering.
- Require 24 bins defensively at runtime; if any row is not an array of length 24 or contains a non-finite/negative value, treat the whole histogram as absent and use the legacy fallback rather than partially rendering corrupt evidence.
- Sum `[start, end)` for each daypart. Derive weekday with `new Date(`${date}T00:00:00Z`).getUTCDay()` so client locale/timezone cannot shift the label.
- Find the maximum of all daypart totals. Heat level is `0` for a zero count; otherwise `Math.max(1, Math.ceil(count / maximum * 4))`, producing integer levels 1–4 relative to this destination's busiest cell.

- [ ] **Step 4: Integrate the strip without changing the legacy path**

Use `useId` for the connection-list id and `useState(false)` for histogram-bearing destinations. Reset collapsed state in the existing origin/destination effect so changing a selection never inherits the previous destination's expanded state.

When valid histogram data exists:

- Keep the duration and train-count text, but omit `frequencyLabel(dest)` from that line because the heat strip replaces the raw frequency copy.
- Render a `type="button"` heat-strip control with `aria-expanded`, `aria-controls`, and a concise accessible name.
- Render one row per sampled date, a visible weekday label, and three non-interactive cells. Every cell gets exactly `aria-label={`${weekday} ${daypart}: ${count} connections`}` and class `frequency-heat-level-${level}`.
- Put nearby visible copy: `Sampled timetable evidence, not a promise.`
- Keep the existing `<ol className="legs">` and its train/transfer rendering unchanged, but hide it while collapsed and reveal it when the strip is expanded.

When histogram is absent or invalid, preserve the current duration string with `frequencyLabel(dest)` and render `.legs` expanded with no toggle. Booking-date and Trainline controls remain outside the toggle and unchanged in both paths.

- [ ] **Step 5: Add exact light/dark theme tokens and compact strip layout**

In `web/src/index.css`, add these token names under both existing theme scopes:

```css
:root {
  --frequency-heat-0: #f3f4f6;
  --frequency-heat-1: #dbeafe;
  --frequency-heat-2: #93c5fd;
  --frequency-heat-3: #3b82f6;
  --frequency-heat-4: #1d4ed8;
}
[data-theme="dark"] {
  --frequency-heat-0: #1a2a55;
  --frequency-heat-1: #243b6b;
  --frequency-heat-2: #28559a;
  --frequency-heat-3: #3478cf;
  --frequency-heat-4: #60a5fa;
}
```

Style the button as a full-width, keyboard-focusable control using existing surface/text/border tokens. Each row is a four-column grid (`weekday` + three equal cells), each level class uses only its matching `var(--frequency-heat-N)`, and the darkest light-theme cells / brightest dark-theme cells retain readable contrast. Do not use `prefers-color-scheme`, inline RGB values, opacity-only colour, animation, a legend, or a new dependency.

- [ ] **Step 6: Verify focused rendering, lint, and production typing**

```bash
cd web
npx vitest run src/components/TripDetails.test.tsx
npm run lint
npm run build
```

Expected: `11 passed` in `TripDetails.test.tsx` (7 before, 11 after; +4), then lint and TypeScript/Vite build exit cleanly.

---

### Task 5: Final focused, full-suite, and scope verification

**Expected diff surface:**
- None. This is verification only; do not edit files to make commands pass.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Run the exact new synthetic contract tests together**

```bash
uv run pytest \
  tests/test_models.py::test_destination_histogram_serializes_and_round_trips_exact_schema \
  tests/test_models.py::test_destination_omits_absent_and_all_zero_histogram \
  tests/test_models.py::test_destination_histogram_rejects_wrong_length_or_negative_bins \
  tests/test_raptor.py::test_departure_evidence_keeps_distinct_direct_trips_at_the_same_minute \
  tests/test_raptor.py::test_departure_evidence_counts_one_origin_departure_once_across_onward_options \
  tests/test_raptor.py::test_departure_evidence_footpath_reaches_but_never_duplicates_a_departure \
  tests/test_compute.py::test_compute_writes_exact_two_date_hourly_histogram_without_changing_frequency \
  tests/test_compute.py::test_compute_histogram_counts_a_routed_footpath_departure_once \
  tests/test_compute.py::test_compute_omits_histogram_for_extra_only_destination \
  -q
```

Expected: `9 passed`.

- [ ] **Step 2: Run all focused backend feature files and touched-file Ruff**

```bash
uv run pytest tests/test_cities.py tests/test_models.py tests/test_raptor.py tests/test_compute.py -q
uv run ruff check \
  pipeline/models.py pipeline/raptor.py pipeline/compute.py \
  tests/test_models.py tests/test_raptor.py tests/test_compute.py
```

Expected: `56 passed` (9 cities + 7 models + 20 RAPTOR + 20 compute), then Ruff exits cleanly. If and only if `test_compute_all_sets_is_capital` hits the known Python 3.14 multiprocessing flake, rerun that exact test alone and record the flake; do not treat any other focused failure as pre-existing.

- [ ] **Step 3: Run all web tests, lint, and production build**

```bash
cd web
npm test -- --reporter=dot
npm run lint
npm run build
```

Expected: `194 passed` across the same 23 files (190 before, 194 after; +4), lint exits cleanly, and TypeScript/Vite production build succeeds.

- [ ] **Step 4: Run the full Python suite with the recorded baseline exceptions**

```bash
uv run pytest -q
```

Stable expected collection after implementation: 269 cases, normally `265 passed, 4 failed`, with all four failures confined to the already-recorded live-data/station-id churn cases in `tests/test_international.py`. A fifth failure is acceptable only when it is the known intermittent Python 3.14 multiprocessing flake `tests/test_compute.py::test_compute_all_sets_is_capital` and that test passes when rerun alone. Any other failing test, any additional international failure, or either known category failing for a new assertion is not pre-existing and must stop the implementation.

- [ ] **Step 5: Audit scope, schema, and semantics**

```bash
git diff --name-only
git diff --check
```

Expected implementation/test diff (plus this plan file if implementation occurs in the same worktree):

```text
pipeline/compute.py
pipeline/models.py
pipeline/raptor.py
tests/test_compute.py
tests/test_models.py
tests/test_raptor.py
web/src/components/TripDetails.test.tsx
web/src/components/TripDetails.tsx
web/src/index.css
web/src/lib/types.ts
```

Confirm `pipeline/cities.py`, `server/app.py`, web map/API/planner files, config, and generated artifacts are untouched. Inspect one synthetic reach JSON and confirm: every retained histogram row has exactly 24 non-negative integers; its sum equals distinct first-train departures reaching that destination; direct counts equal the `direct=True` subset; an extra-only destination omits the field; transfer legs did not add counts; existing best journeys and direct-frequency values match their pinned assertions.

## Expected Test Delta

- Python: +9 cases, 260 -> 269 collected.
  - `tests/test_cities.py`: +0 (9 -> 9).
  - `tests/test_models.py`: +3 (4 -> 7).
  - `tests/test_raptor.py`: +3 (17 -> 20).
  - `tests/test_compute.py`: +3 (17 -> 20).
- Web: +4 cases, 190 -> 194 across 23 files.
  - `web/src/components/TripDetails.test.tsx`: +4 (7 -> 11).
- Combined delta: +13 test cases.

## Planner Notes

1. The authoritative spec's detailed UI paragraph says morning starts at hour 5, but its own note keeps hours 0–4 in morning; the supervisor explicitly requires morning 0–11. This plan uses 0–11 everywhere.
2. “Distinct direct-or-routed connection” does not define whether alternative downstream itineraries multiply a count. This plan chooses one record per distinct first train trip departure from the origin per destination/date. It matches the documented direct-trip population, retains same-minute trains as distinct, avoids combinatorial route counts, and ensures a transfer leg cannot double-count.
3. Histogram keys are every `trips_by_date` sampled date, including zero rows once any sampled evidence exists. The out-of-week `extra_trips` probe never contributes because it is map-coverage evidence, not sampled-frequency evidence.
4. The current web UI has an ordered `.legs` connection list, not a literal HTML table. “Toggle the existing full connection table” is implemented as collapsing/expanding that unchanged list; converting it to a table would be an unrelated semantic and styling change.
5. The spec does not define a global colour scale. This plan uses five destination-local levels normalized to the busiest visible daypart, which preserves monotonic intensity and works with fixed light/dark theme tokens without encoding arbitrary service thresholds.
6. GTFS values above 24:00 remain attached to their sampled service date and use clock hour modulo 24. This is the smallest feed-local interpretation and deliberately performs no timezone or previous/next-date reassignment.
