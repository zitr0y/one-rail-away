# User feedback backlog (2026-07-09 testing session)

The user's first hands-on testing round produced 9 feedback items. Items 1, 3, 5, 9
(plus a wrong-country bug found while investigating) are being fixed by
`docs/superpowers/plans/2026-07-09-feedback-bug-batch.md`. **Everything below is NOT
yet addressed and must not get lost.** Each needs brainstorming with the user before
implementation (established process convention).

## Investigation findings that inform these items (2026-07-09, this session)

- Feeds model international trains as separate per-country trips; the bug batch joins
  them (`pipeline/through.py`).
- The EC 95 Berlin↔Warszawa German half (Rzepin→Berlin Gesundbrunnen) runs **0×** on
  the sampled Tuesday 2026-07-14 (construction; feed replaces it with Rzepin↔
  Frankfurt(Oder) shuttles). One sampled day silently loses whole corridors → item B.
- Coverage truth: only DB/SNCF/ÖBB/SBB/NS are ingested. Stations in PL/CZ/IT/HU/ES
  exist only as cross-border "leaks" from those feeds. Madrid, Porto, all of Renfe/CP/
  Trenitalia/PKP/ČD/MÁV interiors simply don't exist in the data → items A and E.
- Station `country` was assigned from the feed, not geography (Praha tagged "DE") —
  fixed in the bug batch; item E (greying) builds on the corrected field.

## A. Add more national feeds — ongoing (Renfe + PKP shipped)

Next candidates and research verdicts live in `docs/superpowers/new-feed-recipe.md`.
Denmark (Rejseplanen GTFS) is MEDIUM and verified open (direct URL, 57.5 MB, no
registration, HEAD-checked 2026-07-11). Each new feed un-greys a country (see the
two-tier veil). Competitor note: Ouigo España publishes GTFS on
nap.transportes.gob.es; iryo does not.

## B. Multi-day sampling / service frequency (user item 6)

Currently one representative Tuesday. Problems: weekend-only trains invisible;
construction weeks (see EC 95 finding above) silently delete corridors; no way to say
"3× a week". User's sketch: also show per-week frequency ("3×/day" vs "3×/week"),
render infrequent connections dashed/weaker, maybe frequent ones thicker — worried
about becoming non-minimalist, wants design discussion. Likely approach: RAPTOR over
several sample days (e.g. Tue + Sat, or 7 days) and aggregate per destination.
Costs: compute time scales with days sampled (~15 min/day currently).

**Seasonal / part-year trains (added 2026-07-09):** trains that only run part of the
year — e.g. the night trains from NL/Germany/Austria toward Rome — are invisible if the
sampled day(s) fall outside their season, and misleading if inside it (shown as if
year-round). Sampling within one week does NOT solve this; it needs a season-aware idea:
sample weeks spread across the year, or read GTFS calendar spans to tag connections
"seasonal", and decide how the UI shows them (e.g. distinct style + "runs May–Sep"
label). Discuss together with the frequency display above — same data model, same
brainstorm.

## C. Dot sizing / clustering / city grouping (user item 4) — C1 DONE, C2 tried+rejected, C3 open

C1 (dots sized by n_dest) + capital stars shipped 2026-07-11
(spec 2026-07-11-dots-clustering-design.md). C2 clustering shipped and was
removed same day (killed the density picture). C3 city-union still needs its
own brainstorm; may absorb the declutter goal.

Station dots are tiny and hard to click. User ideas, in their words:
- bigger dots for stations with more connections ("more connections is already a
  useful proxy/metric") and/or capitals;
- stations too close together at some zoom levels could bunch together and be
  chosen by name from the bunch;
- multiple main stations of one city (e.g. Brussels Midi/Nord) should be selectable
  by the city name and show the **union** of all their connections — "otherwise the
  options are artificially cut off".
The union idea has data-model implications (city entity above stations) — brainstorm
before building.

**Intra-city "local transit" reachability (added 2026-07-12):** when the origin is
one of a city's stations, the OTHER stations of the same city currently show as
"Not reachable" or "two stops+" in the To search (e.g. from one Paris station, the
other Paris stations look far). They should instead be treated as reachable with a
short hop — label it **"local transit"** (we don't model the metro/tram, but
intra-city travel is obviously possible). Applies to Paris, Brussels
(Midi/Nord/Central), and other multi-"central"-station cities. Part of the
city-grouping brainstorm (C3 / the union idea) — needs a city→stations grouping to
know which stations share a city.

**Hide small location dots at smaller zoom levels (added 2026-07-12):** at zoomed-out
views the small (low-connection) dots crowd the map; consider fading/hiding them below a
zoom threshold and revealing them as the user zooms in, so only major hubs/capitals show
at a glance. A declutter approach that overlaps C3 — decide together with the city-union
idea whether this replaces or complements it.

## D. Branding / map styling (user item 7) — PHASE 1 + PHASE 2 SHIPPED

Phase 1 spec: `docs/superpowers/specs/2026-07-11-branding-design.md`.
Phase 2 spec: `docs/superpowers/specs/2026-07-12-branding-phase2-design.md`,
plan `docs/superpowers/plans/2026-07-12-branding-phase2.md`.

- Phase 1 (light identity) + calibration shipped 2026-07-11.
- **Phase 2 (dark mode + mascot rider) shipped 2026-07-12** (commits
  de6ffa8..e236fb2, Flash-executed, controller-reviewed, 89 web tests green,
  NOT yet pushed). Deep-night basemap + theme toggle (`prefers-color-scheme`
  + persisted `ose-theme`), per-theme overlay tokens, CSS-var panel chrome;
  C0 mascot loops the selected journey line (rotate+flip, transfer pauses,
  reduced-motion parks at destination).

Open user-judged tuning (all AWAITING the user's visual calibration pass —
none auto-resolved, all easy to nudge):
- **Dark starting hexes** — `themeTokens("dark")` in `web/src/lib/colors.ts`
  (stationDot `#5B7FDB`, veil `#6B7590`, rider cream) and the
  `[data-theme="dark"]` CSS block (panel `#0B1533` etc.) are starting points.
- **Mascot traverse speed** — `TRAVERSE_MS = 7000` in `web/src/lib/ride.ts`
  is a flagged TUNING POINT; user unsure fixed-vs-length-scaled ("we shall
  find out"). Fallback (documented): ~5–10 s clamped scaling.
- **Mascot rotation sign** — `riderTransform` math is tested but only visual
  check confirms MapLibre's rotation direction; a wrong sign is a one-line fix.
- Open from Phase 1: bucket-0 yellow on cream (spec TUNING POINT) — not yet
  objected to.

- **Phase 3 (still out of scope):** mascot bends along the actual route
  geometry / logo draw-itself animation. Shares ground with item I.
User's sketch: EU-train theme, cute EU train in the logo that could "bend along the
chosen route if exists". Map style should follow the identity (OpenFreeMap styles can
be customized). Tagline is fixed: "nonstopeurope with onestopeurope".

## I. Corridor bundling for reach lines (added 2026-07-10)

User: Paris shows ~15 separate straight lines fanning over southern France; "I feel like
they all go via Lyon or Vichy and should be just 2-4 lines with breakouts." Data check
confirms the trains are genuinely direct (Paris→Valence TGV 16×/day NONSTOP, Mâcon-Loché
6×, Le Creusot 3× — all via=[]), so each polyline is a single straight segment; the trains
physically share the LGV corridor but our lines don't. Fix directions to brainstorm:
(a) route along real rail geometry (GTFS shapes.txt if the feeds carry it, or OSM rail),
(b) algorithmic edge bundling, (c) force lines through nearest corridor waypoints. Big
visual win, medium-to-large effort. Related to D (map styling).

## K. Alternative / supplementary data sources (added 2026-07-11)

User pointer via chronotrains' attribution: "data from the Deutsche Bahn through
Direkt Bahn Guru … Night train data from Back On Track." Research candidates:
- **FlixTrain / FlixBus** — Flix publishes open GTFS; FlixTrain would add real
  long-distance coverage in DE, FlixBus could be a separate (bus) layer or out
  of scope — decide product-wise first.
- **Direkt Bahn Guru** (direct-connection dataset derived from DB) — possible
  cross-check or gap-filler for direct connections.
- **Back On Track** night-train data — could tag/add night trains (relates to
  the seasonal-trains discussion in item B).
Research first (licensing, format, freshness), then per-source brainstorm.

## L. Fade off-trajectory stations when a journey is selected (added 2026-07-11)

When a specific trajectory is selected, non-selected LINES already dim to 0.04
(shipped 2026-07-11) — but station dots/reach-dots not on the selected journey
stay at full opacity. Dim those too (grey all-stations dots and non-journey
destination dots), so the selected journey pops. Likely a small change in the
same shape as baseLineOpacity: data-driven circle-opacity keyed on the
selected journey's station ids (origin, legs' stops, destination).

## M. Unified journey-planner panel, upper-left (added 2026-07-12)

User wants the scattered controls consolidated into one journey-planner card in
the upper-left corner, shaped like a real trip planner:
- **From** field — fills automatically when you select a station on the map
  (currently map-click sets origin but the panel doesn't show it as an editable
  field); also typeable.
- **To** field — optional; lets you type a destination directly instead of only
  clicking the map. Selecting a dest on the map fills it.
- **Swap** — reverse From/To (swap already exists in the status bar / journey
  card; fold it into the panel).
- **Trip details + booking** — the JourneyCard (duration, legs, book link) moves
  to sit *below* the From/To fields in the same panel, instead of a separate
  bottom-left card.
Effectively merges SearchBox + status bar + JourneyCard into one left-column
planner. Brainstorm the layout (interacts with StopToggle/TimeSlider placement,
and with item L dimming). Design-first; no data changes.

## N. BUG: Trainline booking link is broken (added 2026-07-12)

The "book" deep link in the JourneyCard currently does not resolve to a valid
Trainline booking (reported broken 2026-07-12). Booking is the product's CTA —
verify the deep-link URL format / params against Trainline's current scheme and
fix. Check `web/src/components/JourneyCard.tsx` (link construction) and any
station-code mapping it depends on. Bug, not design — fix directly when picked
up; flagged here so it isn't lost.

## Smaller deferred notes

- **Ł-norm fix (from PL ingestion review 2026-07-11):** NFKD cannot decompose
  stroke letters (ł/Ł, also ø, đ), so `_norm` drops them — "Główny" →
  "gowny" never matches "Glowny". 33 of 44 PKP aliases exist ONLY for this.
  Mapping ł→l (etc.) in `_norm`, guarded by the existing <500 m rule, would
  auto-merge most and shrink the alias block. Document beside the ue/oe/ae
  limitation in `_norm`'s docstring when done.
- **Validator blind spot (renfe T3 + review 2026-07-11):** `validate()` only
  flags <500 m duplicates whose names normalize EQUAL; the renfe French stops
  ("Marseille St Charles" vs "Saint-Charles") passed a "clean" build and were
  caught only by a manual any-name scan. Consider a <100 m any-name cross-feed
  warning in validation.
- **meta.json under-reports feeds:** `data/out/meta.json` lists only the five
  original feeds — renfe/pkp were curl'd targeted (per recipe) and never enter
  `fetch_meta.json`, which compute copies. Fix when meta drives any UI.
- Search only finds stations that have reach files (`has_reach` gate in
  `server/app.py::search`) — fine today, revisit when coverage grows.
- Cross-feed duplicate trains observed (ICE 82 Paris–Frankfurt appears in both SNCF
  and DB feeds as separate trips) — may double-count `direct_per_day`; worth checking
  when touching compute.
- Pre-existing deferred minors from the build ledger still open: `remap_trips` in-place
  mutation trap, dead `uic_regex` comment, O(n²) validate check, search `limit`
  validation, map `easeTo` re-centering on every filter change.
- Final-review note (sncf-labels): document near through.py that SNCF ICE numbers
  (95xx) are disjoint from db_fern ICE numbers — a future feed refresh with a shared
  number would silently start joining.
