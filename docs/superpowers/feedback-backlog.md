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

A static efficiency audit (3 parallel agents, 2026-07-15) produced concrete
output-identical items **AT–AX** plus RAM ideas folded into AL — do those first.
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

- **Intra-city transfers (user decision, 2026-07-13):** label-only "local transit"
  was reverted; the PROPER fix is fake intra-city transfer edges in the pipeline —
  short hops between same-city stations (from `cities.toml` groups) injected as
  transfer edges so RAPTOR routes through them (also fixes Lille→Forbach via the
  Paris Nord→Est transfer). Pipeline change + recompute.
- **Multilingual city exonyms:** the city "all stations" option matches EN exonyms
  but not others — German "Warschau" finds Warsaw stations but not "Warszawa (all
  stations)". Add DE/FR/IT/ES/… exonyms to the city-option matcher
  (`server/app.py::EXONYMS` is extensible).
- Nit: a city-union origin pins only ONE member dot visible at low zoom, so sibling
  termini can fade — thread member ids into the map's always-visible set.

## V. Default-stops parameter + domain routing

URL parameter for the default number of trains (1/2/3) preselected on load.
**nonstopeurope.eu** (user owns it) forwards with nonstop (1 train) preselected;
**onestopeurope.eu** defaults to onestop. Frontend URL/param handling.

## W. Logo drive-off animation

On header-logo hover/click: the train (NOT the wordmark) winks, drives off screen
right, reappears from the left; rails extend ahead of it; the endstop circle fades
out. CSS/SVG on the inline lockup in `web/src/App.tsx`; respect
prefers-reduced-motion. Relates D Phase 3.

## Z. Station naming + city groups sweep

- **"Ostbahnhof"** (`x:db_fern:226810`) is München Ostbahnhof with the city prefix
  stripped — rename via `pipeline/station_names.toml` (user-confirmed 2026-07-13).
  Beware `Graz Ostbahnhof` is a different station. (Id may have churned — see AM;
  key the override accordingly.)
- **München city group** (Hbf + Ostbahnhof + Pasing if present) in `cities.toml`.
- **Sweep for other ungrouped multi-station cities**: Prague (≥4 stations), Hamburg,
  Frankfurt, Köln, Wien, Milano, … Same C3 mechanism. Rome is item AG.

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

## AE. Target chooser in click-disambiguation changes the ORIGIN (bug)

When bunched dots open the station chooser while picking a **target**, selecting
"City (all stations)" changes the start. Agreed direction (2026-07-14): target
chooser drops the city entry entirely; sort by trains-to-reach from the current
origin, then by connection count. Origin chooser unchanged.

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

## AG. Rome needs a city grouping

Termini, Tiburtina, … are ungrouped. Same mechanism as Z sweep.

## AH. Lisbon and Copenhagen are missing capital stars

Both render without the `capital-stars` marker (`is_capital` presumably unset).

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

**Concrete wins from the 2026-07-15 audit (~2–3 GB combined, likely enough to hit
the target; mechanical, output-identical — no brainstorm needed):**

- `railpaths.py:214-222` (`snap_stations`): builds an STRtree over `Point` objects
  for nearly all 8.6M rail nodes, one shapely `Point` per Python-loop iteration
  (~200 B each → **~1.5–2 GB** + tens of seconds), to answer ~1,500 box queries
  (one per hop station, 1 km radius). Invert it: bucket the hop stations into a
  0.02° grid, one pass over `node_locs` keeps only nodes inside some station's
  box, then run the existing per-station exact-haversine best-per-component
  selection on that tiny subset. Caveat: identical except *exact* float-haversine
  distance ties, whose winner today already depends on shapely's internal query
  order (current behaviour is not order-stable there either); with distinct
  coordinates such ties are practically impossible. Strictly-conservative
  fallback: keep the tree but construct via bulk `shapely.points()` — bit-identical
  and still removes most of the construction cost.
- `railpaths.py:190` (`connected_components`): `{node: find(node) for node in
  parent}` materialises a second 8.6M-entry dict (**~0.5–1 GB transient**) while
  `parent` + `size` are still alive. Path-compress in place and return `parent`
  (same node→root mapping). Also: component sizes are tallied twice over 8.6M
  entries (`railpaths.py:550-552` and `:210-212`) — tally once and pass in; and
  `components` stays referenced in `build_rail_paths` (`railpaths.py:560-569`)
  after its last use in `snap_stations` — `del` it after snapping.

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

# Efficiency audit round (2026-07-15)

Static audit by 3 parallel agents (pipeline / frontend / serving); all findings
verified against code on disk, pipeline+server numbers measured on the real data.
Every item below is **mechanical and output-identical (byte- or pixel-) — no
brainstorm needed**, but each fix must prove identity (compare artifacts / visual
behaviour before–after). Umbrella: item P.

## AT. Build: parse each GTFS feed once, not 8× — ~1 h → few minutes

`ose build` re-parses every GTFS zip once per sample date. Three compounding
defects on the same bytes:

1. **Per-day full re-parse.** `pipeline/build.py:39-43` (`_load_feed_samples`)
   calls `gtfs.py:157-323` (`load_feed`) once per 7 service-week dates + 1
   absent-services probe; each call re-opens the zip and fully re-parses
   `routes.txt`, `trips.txt`, `stop_times.txt`, `stops.txt` — only the
   active-service set differs per day. Measured: sbb `stop_times.txt` is 2,323 MB
   (~40M rows) at 0.12M rows/s ≈ 5.4 min/parse × 8 ≈ **~43 min for sbb stop_times
   alone**, inside one worker (feeds parallelise across workers, so the slowest
   feed gates the build). Fix: a multi-date `load_feed_days(zip_path, cfg, days)` —
   parse calendars once, derive per-day active-service sets, stream stop_times
   once keeping rows whose trip is active on *any* requested day, then emit
   per-day `(stops, trips)` by filtering in memory. Row encounter order is
   preserved → per-day trip order, stop order, labels, name pools bit-identical.
   **Trap:** `remap_trips` (`build.py:72`) mutates `StopTime.station` in place and
   `build.py:277` sets `trip.feeds` — per-day `Trip`/`StopTime` objects must be
   fresh instances, never shared across dates.
2. **Calendar files parsed ~10× serially in the parent** before workers start.
   `build.py:186-192` (`feed_windows`) and `build.py:218-222` →
   `gtfs.py:112-134` (`services_absent_from_week`), which re-runs
   `feed_validity_window` (window already computed by build.py) and calls
   `_active_services` once per sample date — each re-reading `calendar.txt` +
   `calendar_dates.txt` from the zip. sbb `calendar_dates.txt` is 249 MB ≈ 60 s
   per parse → **~10 min serial parent time** for sbb alone. Fix: parse the two
   calendar files once per feed into plain lists; compute window + all ids +
   per-day active sets from memory; pass the precomputed window in. Set
   arithmetic is order-independent → provably identical. Also movable into the
   per-feed worker for free parallelism.
3. **`_rows` is 2.4× slower than needed on the hottest loop.** `gtfs.py:73-77`
   materialises a DictReader dict per row then copies it into a second dict with
   `.strip()` on every value — before the trip filter at `gtfs.py:211` discards
   the vast majority of rows. Measured on sbb stop_times (2M rows): 16.2 s vs
   6.7 s for `csv.reader` + header-resolved column indices + check
   `trip_id`/`service_id` first + strip only cells actually read. Stripped values
   identical → identical output.

Same per-day re-parse pattern in the NeTEx loader: `pipeline/netex.py:59-62`
re-runs `ET.parse` on the gzipped Trenitalia publication once per date (7×) and
rebuilds the static tables; only the `runs(daytype)` date check varies. Parse
once, evaluate day-bitmaps per date. (Only bites when the trenitalia fetch
succeeds — zip currently absent from `data/raw/`.)

Alternative implementation for (1)+(3): polars `scan_csv` on the hot files with a
semi-join against active trip ids — see the polars/parquet note at the end of this
section.

## AU. Map: stop rebuilding ~1M coords of reach-lines per slider tick — draws 1 line

The dominant frontend cost, all in the same `syncData`/`syncHighlight` pair in
`web/src/components/Map.tsx` (fix together; pixel-identical):

1. **`reach-lines` source built for ALL destinations, only one ever drawn.**
   `Map.tsx:375-376` → `geojson.ts:168-187` (`linesGeoJSON`) builds full
   LineStrings for all ~1,178 destinations — with rail paths ≈ 850k coord pairs
   (~10–15 MB of JS arrays) — then `setData` structured-clones it to the MapLibre
   worker and geojson-vt re-tiles it. Runs on every `maxMinutes` slider input
   (step=60 → ~14 ticks/drag), every stop-toggle, and on railPaths arrival. But
   the only consumer, layer `reach-lines-selected` (`Map.tsx:114-127`), is always
   filtered to a single destination id (`""` when none selected). Fix: a
   `selectedDest`-keyed effect that computes only the selected destination's line
   (`journeyLegPaths` for its `bestJourney`) and `setData`s a 1-feature
   FeatureCollection. ~1000× less geometry per update; likely hundreds of ms per
   tick today.
2. **Static sources rebuilt per tick.** `all-stations` + `capitals`
   (`Map.tsx:355-373`) depend only on `stations` but live in `syncData`, whose
   effect deps (`Map.tsx:387-389`) include `maxTrains`/`maxMinutes`/`railPaths` —
   two byte-identical FeatureCollections re-built and re-tiled per tick. Fix: own
   effect keyed on `props.stations` only.
3. **`shown()` recomputed 4× per update.** `geojson.ts:40-44` runs inside
   `linesGeoJSON` + `segmentsGeoJSON` + `destinationsGeoJSON` (3× per
   `syncData`), and `syncHighlight` (`Map.tsx:471-474`) builds a fourth complete
   `destinationsGeoJSON` (geometry + all properties) only to `.map` out
   `properties.id` for the star-opacity expression. Fix: compute
   `shown(reach, maxTrains, maxMinutes)` once per update, pass it into the
   builders; derive reachable ids as `shown.map(x => x.d.id)`.
4. **`hopCoords` allocates a reversed copy per hop per rebuild.**
   `geojson.ts:86` — `[...geometry].reverse()` for ~half the hops touched each
   update. Fix: precompute both orientations once when railPaths loads (the
   `App.tsx:35` transform is the natural spot). Mostly subsumed if (1) lands.

## AV. Server: pre-gzipped static artifacts + HTTP caching — ~1.8 s CPU/page view → ~0

Data changes only at the Monday 04:30 cron, yet `server/app.py` treats every
request as dynamic. Gzip on the wire already exists (`GZipMiddleware`,
`app.py:140`), so first-visit bandwidth is fine — the waste is server CPU and
repeat-visit traffic. Measured via TestClient (prod docker box is slower):
`/api/rail-paths` 1.04 s, `/api/coverage` 0.70 s, `/api/reach/{largest}` 70 ms,
`/api/stations` 48 ms, search 39 ms.

1. **Read → `json.loads` → FastAPI re-encode → `json.dumps` → gzip-9 per
   request, for byte-identical bytes every time.** `app.py:188-193`
   (`rail-paths`) + `:202-207` (`coverage`), fetched unconditionally on mount at
   `App.tsx:34` + `Map.tsx:66` → **~1.7 s server CPU per page view** plus tens of
   MB transient Python objects (matters on the 5 GB host). Same pattern on the
   hot interactive path `/api/reach/{id}` (`app.py:177-182`; city selection fans
   out N parallel reach fetches, `App.tsx:51`). Fix: all five verbatim-file
   endpoints (`rail-paths`, `coverage`, `reach`, `cities`, `meta`) → have the
   pipeline write `*.json.gz` at build time and serve with
   `FileResponse(..., headers={"Content-Encoding": "gzip"})` (sendfile, ~0 CPU);
   plain `FileResponse` on the raw file is the simpler 80% version. Client-parsed
   data identical.
2. **Zero HTTP caching anywhere** — no ETag/Last-Modified/Cache-Control, so every
   visit re-downloads ~2.3 MB gz (rail-paths + coverage + stations) and re-burns
   (1). `FileResponse` emits ETag + Last-Modified for free → 304s; add
   `Cache-Control: public, max-age=...` sized to the weekly cadence.
3. **Search / `/api/stations` re-parse per request.** `app.py:144-146` +
   `:151-153`: `_read(stations.json)` (~15 ms) + `_reach_ids_on_disk` re-glob of
   1,720 files (~20 ms) per call — the per-keystroke path (client debounce at
   `StationField.tsx:42`). Fix: in-process cache invalidated by file mtime
   (preserves derive-from-disk semantics).
4. **One-liner:** starlette `GZipMiddleware` defaults to `compresslevel=9`;
   level 6 measured 0.32 s vs 0.55 s on rail_paths for +0.1% size. Mostly
   subsumed by (1) but free insurance for whatever stays dynamic.

Deploy note: server-side this is a normal `git pull` + pipeline-script run in
`~/docker/one-rail-away` (no image rebuild), but (1) needs the pipeline to emit
`.json.gz` first — ship pipeline change and server change together.

## AW. Compute: index `_direct_counts` + lazy RAPTOR reconstruction

Two independent compute-step wins (the day-indexed RAPTOR scan itself was already
optimised 2026-07-14, don't re-touch):

1. **`_direct_counts` scans ALL trips for every origin.**
   `pipeline/compute.py:26-38`, called per origin per date (`compute.py:100`).
   Trips never serving `origin` contribute nothing, yet all stops are iterated
   with pydantic attribute access: 1,725 origins × 8 date-lists × ~60k stop
   entries ≈ **830M iterations, ~99.5% provably no-ops** (avg ~35
   trips/station of 6,461 trips). Fix: reuse `raptor._index(trips)` (already
   cached per trips list) — iterate only `by_station[origin]` trip indices in
   ascending order (a subsequence of the full scan order) over the tuple-ised
   `trip_stops`. Counter sums are order-independent → identical. ~200× on the
   function, est. 10–25% of compute-step runtime.
2. **RAPTOR materialises `Journey`/`Leg` pydantic objects for every candidate
   before checking if it can win.** `raptor.py:203-216`: ~1,000 dests × 3 rounds
   × up to 16 floors ≈ 30k reconstructions per origin-day ≈ order 400M pydantic
   constructions per full run (~1–2 µs each), but only the best per
   `(dest, trains)` survives the `duration_min <` check. Also `_reconstruct`
   walks the parent chain twice (`raptor.py:149` re-walks via
   `_origin_dep_minutes`). Fix: walk parents once to recover `first_dep` (no
   allocations), compute `duration = t - first_dep`, build legs/Journey only when
   the key is absent or strictly better. Same strict-`<` tie-break, same floor
   order → identical winners.

## AX. Frontend: reach fetch cache + request cancellation (includes a latent BUG)

`web/src/lib/api.ts:3-7` has no cache and no AbortController; call sites
`App.tsx:43` (`selectOrigin`), `:51` (`selectCityOrigin` — fetches every member
reach fresh), `:80` (`onClearOrigin` promote), `:104` (`swapSelection`).

- **Waste:** re-clicking the same origin, A↔B swap-and-back, or re-picking a city
  re-downloads + re-parses the same JSON (median reach 336 KB, max 1.2 MB gz
  62 KB).
- **BUG:** with no cancellation, two quick origin clicks race and the
  last-*resolved* (not last-requested) `setReach` wins → a stale reach can be
  displayed for the wrong origin.

Fix: small `Map<id, Promise<ReachFile>>` cache in api.ts (session-lifetime is
fine — data is weekly; drop entries on fetch failure so retries work) + a
request-generation counter or AbortController in App so only the latest selection
applies. Combines well with AV(2) — ETags make even cold refetches cheap.

**Polars/parquet note (2026-07-15, asked & answered):** no pandas/polars today —
pure stdlib csv + pydantic. Parquet intermediates: not worth it (after AT each
feed is parsed exactly once per weekly build; nothing re-reads the CSVs).
Polars: only ONE good spot — `scan_csv` + semi-join on active trip ids for
stop_times/trips/calendar_dates as an *alternative implementation* of AT(1)+(3),
likely another ~5-10× on parse+filter. Trap: polars doesn't `.strip()` cell
whitespace — must replicate current strip semantics on the used columns or output
identity breaks. Verdict: do AT in stdlib first; reach for polars only if the
post-AT build is still annoyingly slow.

---

## Smaller deferred notes

- **Flaky compute test on Python 3.14:**
  `tests/test_compute.py::test_compute_all_sets_is_capital` fails on `main` —
  `os.chdir(tmp_path)` + no-fork multiprocessing means workers read the wrong
  `capitals.toml`. Fix: pass an explicit path into the capitals loader or set the
  mp start method in the test.
- **Ł-norm fix:** NFKD can't decompose stroke letters (ł/Ł, ø, đ) so `_norm` drops
  them ("Główny" → "gowny"); 33 of 44 PKP aliases exist only for this. Map ł→l
  (etc.) in `_norm`, guarded by the <500 m rule; document beside the ue/oe/ae note.
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
- **Map `easeTo` re-centers on every filter change** (2026-07-15 audit detail):
  `Map.tsx:384` ends `syncData` with `m.easeTo({center: origin, zoom: 5})`, so a
  slider tick / stop-toggle yanks the view back if the user panned away. Fix:
  ref-track the last-eased origin id, easeTo only when `reach.origin` changes.
  NOTE: removes a visible (buggy) recenter — user sign-off, not silent.
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
