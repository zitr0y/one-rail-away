# Feedback backlog — OPEN items only

Living backlog of user-testing feedback and deferred work. Convention: shipped or
rejected items are **deleted** (git history keeps them), never tombstoned. Each item
needs brainstorming with the user before implementation unless marked otherwise.
Feed research verdicts (Norway, Czechia, Hungary, Belgium, Ouigo España, …) live in
the verdict table of [`new-feed-recipe.md`](new-feed-recipe.md).

Letters are stable ids; the highest used so far is AX.

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
  animation. Shares ground with items I and W.
- Road labels/shields (z12+) were not faded in the road de-emphasis — revisit if
  they shout at street zoom.

## I. Reach-line geometry — direction reopened (2026-07-15 feedback)

**History:** straight per-destination lines → X trunk-merge (shared stop-sequence
segments deduped via `segmentsGeoJSON`, shipped 2026-07-13) → real OSM rail geometry
(`ose paths` → `rail_paths.json`, shipped 2026-07-14).

**New feedback (train-nerd round, 2026-07-15): the OSM-routed paths are not good
enough.** Some hops render as straight lines even though neighbouring hops on
practically the same line follow track; subtler cases route along the WRONG rails —
around Düsseldorf-Holthausen trains follow the subway or the cargo-yard tracks
instead of the passenger line. Root causes: OSM connectivity/classification is
imperfect and chasing per-corridor correctness for train nerds is a treadmill.

**Direction to brainstorm:** possibly go BACK to smoothed "subway map style" lines —
but properly drawn as line trees (a→b→c as one polyline through the served stops,
not independent a→b and a→c fans). The X segment-dedup already provides the shared
trunks, so smoothing must respect shared segments (smooth the tree, not each
journey). That should give clean curves without straight-line fallback. Decision
needed with the user: fix OSM routing (better rail filtering, penalize
subway/freight tags, connectivity repair) vs. smoothed trees vs. hybrid (OSM where
confident, smoothed otherwise). Note the earlier "paths not rendering" report is
superseded — paths render now; the issue is quality.

Related: AL (paths RAM budget), AJ (rider steering off geometry stubs).

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

The 2026-07-15 static audit items (AT–AX + AL RAM fixes) are shipped. If the
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
- **OpenRailwayMap / OSM rail** — partly consumed already (`ose paths`). Still
  useful to fill MISSING station locations / cross-check coordinates (relates AP).

## U. City-union follow-ups

Intra-city transfer edges shipped 2026-07-16 (35 curated pairs, 17 cities;
spec `specs/2026-07-16-intra-city-transfers-design.md`). Remaining:

- **Needs a server recompute to go live** — reach files only carry transfers
  after the pipeline reruns (Monday cron or manual run). After that, verify a
  through-Paris journey on prod; Milano/Lisboa/Porto entries stay dormant
  until Trenitalia/CP are in a build (they warn-and-skip today).
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

## AJ. Rider still swings near stations (low priority)

Station-approach stubs (median 14 m) point sideways off the running line and the
~350 m `BEARING_WINDOW_KM` look-ahead still sees them near stops. Options: widen
the window near leg ends, damp rotation in the dwell approach, or steer by track
while drawing to the station. User: "not too bad".

## AL. `ose paths` must fit in <5 GB RAM

Production box has 7 GB total / ~5 GB free; `ose paths` peaks at 5.9 GB RSS, so
`rail_paths.json` is built on a workstation and committed as an artifact. Goal:
whole stage under 5 GB so the server cron can do a genuine full recompute and the
committed artifact goes away. Memory sinks: `read_rail_network` holds all 8.6M node
locations in Python dicts; ideas: stream per-country and merge border-crossing
ways, numpy/compact arrays for coords, drop node locations once contracted edges
hold polylines, batch hop routing.

The audit's concrete fixes (snap_stations grid prefilter, in-place union-find
path compression) shipped 2026-07-15 in cf2e077; the <5 GB target is NOT yet
re-measured on the server — do that before deleting this item.

## AM. Station ids are not stable across feed refreshes (breaks every shared link)

`x:db_fern:569849` was Berlin Hbf in one build and an unrelated minor station in
the next (Berlin Hbf became `x:db_fern:414176`). Every shared/bookmarked URL
silently points at a DIFFERENT station after a refresh; committed sample reach
files go stale; any future saved state is unsafe. Fix direction: canonical ids from
stable keys (UIC where present, else hash of normalized name + rounded coords) plus
a `station_id_aliases` map so retired ids keep resolving. The merge step already
reconciles identity; it's just not what the public id is keyed on.
**Do before inviting people to share links.** Relates AD.

---

# Train-nerd feedback round (dad, 2026-07-15)

Seven items; the path-routing one is folded into item I above.

## AN. Mobile layout

The site is not adjusted to phones at all. Direction to brainstorm: on mobile,
hide the UI by default except the ACTIVE box (start or target), with a
handle/arrow to pull the full panel up (bottom-sheet pattern). Needs a design
round; touch targets and the click-disambiguation popup (AE) are affected too.

## AO. Frequency info is not understandable — visualise it

"6/7 sampled days", "available on every sampled day", "24.9 trains per day" are
not straightforward to a first-time reader. Idea (dad's wish): a compact,
colourful visualisation of how many connections run per sampled day, and within
each day split into morning / afternoon / evening. Clicking it expands the full
connection tables — available, but never in your face (overload). Data check
needed: reach files currently carry counts + a best journey, not per-departure
buckets — the pipeline likely needs to emit departure-time histograms per
destination. Relates AQ (same data), AF (seasonal wording), B's cautious-sampling
language (the design constraint "evidence, not promise" still holds).

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
morning departures). Requires per-journey departure times in the reach data
(currently only the best sampled journey is retained per destination) — likely the
same pipeline change AO needs. UI: fits the planner panel; consider interaction
with the 1/2/3-trains selector and V (URL params).

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
