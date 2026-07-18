# Feedback backlog — OPEN items only

Living backlog of user-testing feedback and deferred work. Convention: shipped or
rejected items are **deleted** (git history keeps them), never tombstoned. Each item
needs brainstorming with the user before implementation unless marked otherwise.
Feed research verdicts (Norway, Czechia, Hungary, Belgium, Ouigo España, …) live in
the verdict table of [`new-feed-recipe.md`](new-feed-recipe.md).

Letters are stable ids; the highest used so far is AY.

## A. Add more national feeds — ongoing

Shipped so far: DB long-distance, SNCF, ÖBB, SBB, NS, Rejseplanen (DK), FlixTrain,
CP (PT), Trenitalia (IT), Renfe (ES), PKP (PL). Current inventory and gaps:
`docs/data-sources.md`. Next candidates and researched verdicts:
[`new-feed-recipe.md`](new-feed-recipe.md) (Norway/Czechia/Hungary/Belgium/Ouigo
España all verified UNFIT 2026-07-14 with revisit conditions). Each new feed
un-greys a country (two-tier veil). Competitor note: iryo publishes no GTFS.

## D. Branding — open tuning + Phase 3

Phases 1+2 (light identity, dark mode, mascot rider, road de-emphasis) are shipped.
Still open:

- **User-judged tuning, awaiting visual calibration pass** (all easy to nudge):
  dark-theme hexes (`themeTokens("dark")` in `web/src/lib/colors.ts` +
  `[data-theme="dark"]` CSS block), mascot traverse speed (`TRAVERSE_MS = 7000` in
  `web/src/lib/ride.ts`; fallback ~5–10 s length-scaled), mascot rotation sign
  (`riderTransform`), Phase-1 bucket-0 yellow on cream.
- **Phase 3:** mascot bends along the actual route geometry / logo draw-itself
  animation. Shares ground with item W.
- Road labels/shields (z12+) were not faded in the road de-emphasis — revisit if
  they shout at street zoom.

## K. Alternative / supplementary data sources

FlixTrain is shipped (see A). Remaining candidates:
- **FlixBus** — separate (bus) overlay or out of scope; product decision first.
  If added, mode filtering policy is item AS, seller handoff is item S.
- **Direkt Bahn Guru** (direct-connection dataset derived from DB) — cross-check /
  gap-filler for direct connections.
- **Back On Track** night-train data — tag/add night trains.
Research first (licensing, format, freshness), then per-source brainstorm.

## N. Trainline booking handoff — affiliate integration pending

The CTA currently opens the plain Trainline landing page (deliberate fallback, no
prefill claims). The real integration (Partnerize affiliate / widget / approved
deep-link format) is future work; investigation and requirements in
[`research/2026-07-13-trainline-booking-handoff.md`](research/2026-07-13-trainline-booking-handoff.md).
Do not reintroduce query parameters or an affiliate code until Trainline has
provided an approved format. Alternatives: item S (Rail Europe, Flix).

## O. Reachability previews on hover

Lightweight hover preview for a station: reveal its reachable area or connection
summary before committing it as origin, so exploratory use feels faster. Must stay
visually quiet next to selected journeys and the planner. Constraint from P: no
expensive per-pointer computation.

## P. Performance optimisation pass

The 2026-07-15 static audit items (AT–AX) are shipped. If the
post-AT build is still slow, the next lever is polars `scan_csv` + semi-join on
active trip ids for the stop_times parse (trap: polars doesn't `.strip()` cell
whitespace — replicate strip semantics or output identity breaks).
P stays open for the *measured* follow-up as map and coverage grow: profile
initial load, map layers, hover/select updates, search, reach-file fetching,
route rendering; prioritise measured bottlenecks. Needed regardless of O.

## Q. Log unfit / dropped data during build (observability)

Whenever build/merge/filter drops a trip (<2 stops, stub, route_allow), can't merge
a near-duplicate station with a different name (validator blind spot), can't
geo-assign a country, or a feed introduces an unrecognised route category /
stop-id shape, LOG it to a structured persistent place (e.g. `data/out/unfit.json`
or a build report), not transient stderr. Goal: a standing "what today's feeds
threw at us that we didn't model" review list. Relates to AC/AD hardening and AP.

## R. Future-proof for EU mandatory mobility-data APIs

Research which EU instrument actually mandates operator data/APIs (user pointer was
2024/1689, but that's the AI Act — likely the ITS Directive MMTIS delegated
regulation or the MDMS proposal): what's mandated (real-time + booking via national
access points), timelines, whether it unlocks cleaner official feeds. The
single-seller through-ticketing push (whole journey from one seller with
missed-connection guarantees) is an appealing booking-handoff direction (relates N,
S). Relates K, Q.

## S. Booking/seller + rail-data ecosystem research

- **Rail Europe** — evaluate as booking handoff / ticket seller (alternative or
  complement to Trainline, item N) and as a data API (coverage, fares,
  connections). Research partner/affiliate + API terms.
- **Flix as ticket seller** — if FlixBus ships (K), its tickets likely need Flix's
  own handoff (Trainline/Rail Europe may not resell FlixBus); verify whether
  FlixTrain is resold elsewhere.
- **OpenRailwayMap / OSM rail** — still useful to fill MISSING station locations / cross-check coordinates (relates AP).

## U. City-union follow-ups

Intra-city transfer edges shipped 2026-07-16 (35 curated pairs, 17 cities;
spec `specs/2026-07-16-intra-city-transfers-design.md`). **Confirmed working
mid-journey in user testing 2026-07-16** (Agen → Dunkerque correctly shows
"~55 min metro to Paris Gare du Nord" between the two TGVs). Remaining:

- Milano/Lisboa/Porto entries stay dormant until Trenitalia/CP are in a build
  (they warn-and-skip today).
- Same-city origin→destination queries are absurd — split out as AY.
- Nit: a city-union origin pins only ONE member dot visible at low zoom, so sibling
  termini can fade — thread member ids into the map's always-visible set.

## W. Logo drive-off animation

On header-logo hover/click: the train (NOT the wordmark) winks, drives off screen
right, reappears from the left; rails extend ahead of it; the endstop circle fades
out. CSS/SVG on the inline lockup in `web/src/App.tsx`; respect
prefers-reduced-motion. Relates D Phase 3.

## Z. Station naming + city groups sweep

- **Sweep for other ungrouped multi-station cities**: Prague (≥4 stations), Hamburg,
  Frankfurt, Köln, Wien, Milano, … Same C3 mechanism (München + Roma shipped
  2026-07-16; München Ostbahnhof rename shipped with them).

## AC. Keep serving good data when upstream feeds break

A DB/SNCF station-id change made the live build abort and silently fall back to the
five-stop example dataset. Degrade gracefully: keep serving the last known-good
dataset, quarantine/skip only the affected feed with a loud warning, fail the build
only when output would be substantially degraded. Relates Q, AD.

## AD. Harden against station-id churn — no hardcoded live ids

Tests must not hardcode live feed ids (use synthetic fixtures or match on stable
properties); the pipeline should treat id churn as normal — stable internal ids
keyed on name+geo with feed ids as volatile aliases, so an upstream renumber is
absorbed. User explicitly rejected id-chasing (the 036a1fb test "fix"). Consider
doing AD + AC as one hardening pass. Relates AM.

## AF. Seasonal services: currently detect NOTHING — needs a trustworthy replacement

The original GTFS-calendar heuristic flagged 64% of Dortmund's destinations
seasonal (incl. Dortmund→München, 122 trains/week) because DB defines services per
timetable period; it was **dropped entirely** (bb2d23b), so today nothing is
called seasonal. Real seasonal services (some Nightjets, Alpine/summer routes) do
exist. Replacement directions: derive from OBSERVED operating days (union
day-of-week flags × date range + calendar_dates exceptions, flag only when that
union covers a small share of the feed window), and/or a short **curated**
seasonal list outside the feeds (see `docs/data-sources.md` "no source for").
Do NOT resurrect a calendar-span-vs-horizon constant. Feeds into AO's
presentation rework.

## AI. Density-aware station hiding on zoom

Portugal/Denmark expose essentially every regional stop → clutter. Current zoom
declutter is global-threshold and was reverted to near-inert (2026-07-13) because
ES/FR emptied out while DE/AT/PL stayed overfull. Rework must normalise by local
station density (hide low-importance stops where density is high, reveal on
zoom-in), not a global n_dest threshold. Will get MORE urgent if regional trains
land (AR).

## AM. Station ids are not stable across feed refreshes (breaks every shared link)

`x:db_fern:569849` was Berlin Hbf in one build and an unrelated minor station in
the next (Berlin Hbf became `x:db_fern:414176`). Every shared/bookmarked URL
silently points at a DIFFERENT station after a refresh; committed sample reach
files go stale; any future saved state is unsafe. Fix direction: canonical ids from
stable keys (UIC where present, else hash of normalized name + rounded coords) plus
a `station_id_aliases` map so retired ids keep resolving. The merge step already
reconciles identity; it's just not what the public id is keyed on.

2026-07-17 escalation: an id rotation left 32 station_aliases.toml targets
(`pkp:* -> x:db_fern:<dead id>`) pointing at ghosts; the aliased pkp stops
minted duplicate stations and the sharpened `_norm` made `validate()` abort
every pipeline run. Mitigated in `merge.py` (stale x:-alias targets fall back
to proximity when the target feed is already processed), but alias pairs whose
names DON'T normalize equal (Kyiv/Lviv Cyrillic-vs-Latin, translated exonyms)
still silently split into doubled stations when their target id rotates —
invisible to validation. The real fix remains stable canonical ids; until
then, stale alias targets should be re-audited after each db_fern refresh.
**Do before inviting people to share links.** Relates AD.

---

# Train-nerd feedback round (dad, 2026-07-15)

Seven items; the path-routing one shipped as smoothed line trees 2026-07-17.

## AN. Mobile layout — rework shipped 2026-07-18, awaiting phone verification

Bottom sheet shipped (spec `specs/2026-07-16-mobile-layout-design.md`). All
dimensions are centralized constants in `web/src/lib/mobileLayout.ts` (collapsed
112/136 px, expanded 88dvh, swipe threshold 32 px) — calibration is a one-line
change each.

2026-07-18 rework (deployed to production, user verifies on phone): handle +
open/close merged into one capsule (chevron gone); minimized sheet shows only
the armed field (root cause was author CSS beating `[hidden]`); swap button
overlays the fields' right edge; header floats over the map and collapses to a
logo pill on first map gesture / sheet expand (tap to reopen); attribution
starts compact (ⓘ); example-connection legs always visible in trip details.

## AO. Frequency heat strip — shipped 2026-07-16, live after recompute

7×3 day×daypart heat strip + day×hour histograms in reach files (spec
`specs/2026-07-16-frequency-viz-design.md`). Evidence pass roughly doubles
compute-stage time — watch under P.

**Layout rework shipped 2026-07-17** (spec
`specs/2026-07-17-frequency-heat-strip-redesign-design.md`): transposed grid
(days on x-axis), sunrise/sun/moon daypart icons with words on desktop (hidden
on the mobile sheet), 0→max legend, validated brand-blue ramp, per-cell
tooltips. Awaiting user visual calibration on desktop + phone.

## AP. Auto-flag / auto-merge station near-duplicates (Stuttgart case)

Stuttgart shows 4 stations of which 3 are just platforms — on the LIVE map, so the
existing merge machinery didn't catch them. Wanted: automatic flagging of suspect
near-duplicates (different names <100 m, platform-like names, same-name clusters)
surfaced for decisions, and/or auto-merging where safe. Builds on the validator
blind spot note below and Q (persistent build report). Cross-feed aliasing exists
(`station_aliases.toml`); this is about SAME-feed platform granularity and about
surfacing rather than silently passing validation.

## AQ. Departure-time filter

A scale/slider to restrict shown connections to certain starting times (e.g. only
morning departures). Groundwork shipped with AO (2026-07-16): reach files now
carry day×hour departure histograms, enough for an hour-granular COUNT filter.
A filter that recomputes the *best journey* per time window would need the full
departure list instead (+77% reach-file size, see AO spec decision 1). UI: fits
the planner panel; consider interaction with the 1/2/3-trains selector and V
(URL params).

## AR. Regional trains (feasibility research first)

Dad wants regional trains. Reality check needed before any brainstorm:
- **Scale:** in DE alone this multiplies stations and trips massively (gtfs.de
  regional feed vs the current long-distance one); compute cost for RAPTOR ×
  stations × sampled week, reach-file count/size, AL's 5 GB server budget, AI's
  clutter problem.
- **Consistency:** other countries ALREADY include regional-ish products (DK RE,
  PT R/IR, PL); in some networks there is no clean long-distance/regional split.
- **Product:** should be a toggle if it ships, not a default.
Deliverable: a sizing/feasibility research doc, then decide.

## AS. Mode/route dominance policy (FlixBus 8 h vs train 3 h)

If a bus (or a slow alternative train route) takes 8 h where a train takes 3 h,
what do we show and what do we filter? Needs an explicit dominance/filtering
policy: e.g. drop options slower than k× the fastest, or per-mode toggles, or show
the fastest per mode. Applies today to alternative train routes and becomes acute
if FlixBus (K) or regional trains (AR) land. Product decision with the user.

---

# Self-test feedback round (aaron, 2026-07-16)

Three items: heat-strip layout folded into AO, smoothed-paths decision folded
into I, plus:

## AY. Same-city origin→destination journeys are absurd

Paris Gare du Nord → Paris Montparnasse renders as a 4 h 11 min, 3-TGV loop via
Lille Flandres and Massy TGV instead of "take the metro ~25 min" (or being
suppressed entirely). The intra-city transfer edges (U) work fine as
*mid-journey* legs; the failure is when origin and destination are in the same
city union — RAPTOR happily finds a train-only route and never considers the
walk/metro edge as the whole answer. Decide with the user: show the transfer
edge as the journey, or treat same-union queries as degenerate (message instead
of route). Relates U, AS (dominance policy — a 4 h train loop is dominated by a
55 min metro).

# Smaller deferred notes

- **Timezone bug — cross-timezone journey times off by 1 h:** GTFS times are
  parsed as local minutes-since-midnight with no timezone normalization
  (`pipeline/gtfs.py:74-77`), so ES↔PT (CET vs WET) itineraries are wrong by
  an hour. Found during AO data research 2026-07-16. Affects any
  cross-timezone leg; fix before trusting durations near Iberia's border.
- **Medina del Campo AV coordinates wrong:** placed 21 m from the classic
  station in our data; really ~3.3 km away (found in the 2026-07-16 U sweep).
  Fix source coords / merge logic; also a platform-duplicate lookalike for AP.

- **Flaky compute test on Python 3.14:**
  `tests/test_compute.py::test_compute_all_sets_is_capital` fails on `main` —
  `os.chdir(tmp_path)` + no-fork multiprocessing means workers read the wrong
  `capitals.toml`. Fix: pass an explicit path into the capitals loader or set the
  mp start method in the test.
- **Validator blind spot:** `validate()` only flags <500 m duplicates whose names
  normalize EQUAL ("Marseille St Charles" vs "Saint-Charles" passed clean).
  Consider a <100 m any-name cross-feed warning. Now largely subsumed by AP.
- **meta.json under-reports feeds:** targeted-curl'd feeds never enter
  `fetch_meta.json`, which compute copies. Fix when meta drives any UI.
- Search only finds stations with reach files (`has_reach` gate in
  `server/app.py::search`) — revisit when coverage grows.
- **Cross-feed duplicate trains** (ICE 82 Paris–Frankfurt in both SNCF and DB
  feeds) may double-count `direct_per_day` — check when touching compute.
- Deferred minors from the build ledger: `remap_trips` in-place mutation trap, dead
  `uic_regex` comment, O(n²) validate check, search `limit` validation.
- **Rider animation micro-waste** (2026-07-15 audit; low at current data scale):
  `ride.ts:70-74` `segmentIndexAt` linear-walks `cumKm` from index 1, called 3×
  per frame via `positionAtKm` (`ride.ts:164,171-172`) plus `phases.find`
  (`:156-157`), 60 fps for as long as a destination stays selected — binary
  search or cache the last index (positions are monotonic within a loop). Grows
  with denser OSM geometry (item I may change this code anyway). Also
  `syncRider` (`Map.tsx:558-561`) tears down and rebuilds marker + timeline on 7
  deps even when the resolved journey is unchanged — caveat: dedupe-by-identity
  also stops the (likely unintended) visible animation restart on filter ticks,
  technically a visible change.
- Document near `through.py` that SNCF ICE numbers (95xx) are disjoint from
  db_fern ICE numbers — a future refresh with a shared number would silently join.
