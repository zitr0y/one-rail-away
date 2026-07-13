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

Station dots are tiny and hard to click. Progress:
- bigger dots for stations with more connections / capitals — **C1 SHIPPED**.
- multiple stations of one city selectable by **city name** showing the **union**
  of their connections — **C3 SHIPPED 2026-07-13** (curated `cities.toml` →
  `data/out/cities.json`, 15 cities; `cityunion.ts::unionReach` merges by
  destination keeping fewest-trains-then-shortest-duration; `/api/cities`). Nit
  DEFERRED: a city-union origin pins only ONE member dot visible at low zoom, so
  sibling termini can fade — thread member ids into the map's always-visible set.
- intra-city **"local transit"** label for same-city siblings with no direct reach
  entry — **SHIPPED 2026-07-13** (`planner.ts::destOptions`).
- **hide small dots at low zoom** (declutter) — **SHIPPED 2026-07-13**
  (`dots.ts::stationDotOpacityByZoom`; n_dest≥150@z4 … all@z9, TUNING POINTS).
- STILL OPEN: stations too close together should **bunch** and be chosen by name
  from the cluster on click (a click-disambiguation UI, distinct from the union —
  for when several stations overlap at a zoom level). Not built.

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

**De-emphasise roads in map styling (added 2026-07-13):** roads carry little meaning
for a rail-reachability product; consider styling them more faintly (lower opacity /
thinner / muted colour) so rail lines and station dots read as the primary layer.
Part of the OpenFreeMap style customisation under this item; do per-theme (light + dark).

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

## N. Trainline booking handoff — landing-page fallback shipped (2026-07-13)

The old `trainline.eu/search/{origin}/{destination}/{date}/` path is not a
reliable live search handoff. The CTA now opens the ordinary Trainline landing
page, intentionally without claiming to prefill the selected journey or date.

The full investigation and the required future Partnerize/affiliate/widget
work are recorded in
[`research/2026-07-13-trainline-booking-handoff.md`](research/2026-07-13-trainline-booking-handoff.md).
Do not reintroduce query parameters or an affiliate code until Trainline has
provided an approved integration format.

## O. Reachability previews on hover (added 2026-07-13)

Consider a lightweight hover preview for a station: reveal its reachable area or
connection summary before committing it as the origin, so exploratory map use feels
faster. Design the preview to stay visually quiet and avoid competing with selected
journeys or the planner panel.

## P. Performance optimisation pass (added 2026-07-13)

Reserve a dedicated optimisation pass as the map and feed coverage grow. Profile the
full interaction path (initial data load, map layers, hover/select updates, search,
reach-file fetching, and route rendering), then prioritise the largest measured
bottlenecks. The work should keep the app responsive with substantially more stations
and connections. It is needed regardless of whether hover previews are built; any
future hover preview must simply avoid adding an expensive per-pointer computation.

## Q. Log unfit / dropped data during build (observability) (added 2026-07-13)

Trains and feeds change constantly, so the pipeline must SURFACE anything it
can't place instead of silently dropping it. Whenever build/merge/filter drops
a trip (<2 stops, stub, filtered by route_allow), can't merge a station
(near-duplicate with a different name — the validator blind spot), can't
geo-assign a country (the "no polygon match" warnings seen adding Denmark
2026-07-13; Fredericia retained feed country DE), or a new feed introduces an
unrecognised route category / stop-id shape, it should LOG it to a structured,
persistent place (e.g. `data/out/unfit.json` or a build report), not just a
transient stderr warning. Goal: a standing "here is what today's feeds threw at
us that we didn't model" list we can review and adapt to. Builds on the existing
validator-blind-spot and meta.json-under-reports notes below.

## R. Future-proof for EU mandatory mobility data APIs (added 2026-07-13)

The EU is moving toward mandatory operator data/APIs; user flagged
https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng as the pointer. NOTE: verify
the actual instrument — 2024/1689 is the AI Act; the mobility-data mandate is
more likely the ITS Directive revision / Multimodal Travel Information Services
delegated regulation or the proposed Multimodal Digital Mobility Services (MDMS)
regulation. Research which regulation actually mandates what (real-time +
booking data via national access points), timelines, and whether it unlocks
cleaner official feeds than the current national-GTFS patchwork. The rule also
pushes **single-seller through-ticketing** — buy a whole multi-leg journey from
one seller with start-to-end / missed-connection money-back guarantees. That
"buy all tickets from one seller" model is an appealing product direction for
onestopeurope's booking handoff (relates to N and S): if such sellers/APIs
emerge, prefer one that covers the whole planned journey with a guarantee.
Relates to K (data sources) and Q (adapting to new data shapes).

## S. Rail Europe (ticket seller + API) & OpenRailwayMap (added 2026-07-13)

- **Rail Europe** — evaluate as (a) a booking handoff / ticket seller,
  alternative or complement to Trainline (item N), and (b) a data API more
  generally (coverage, fares, connections). Research their partner/affiliate
  and API terms; compare booking-handoff quality to the current Trainline
  landing-page fallback.
- **Flix as ticket seller** — if/when FlixBus is added (F2 bus overlay), we will
  likely need Flix's own booking/seller handoff for those tickets (Trainline/Rail
  Europe may not resell FlixBus). Unclear whether FlixTrain also needs it or is
  resold elsewhere — verify. Booking-handoff item, relates to N.
- **OpenRailwayMap** (OSM-based rail data) — use to fill MISSING railway
  station locations / cross-check station coordinates, and as the OSM-rail
  geometry source floated in item I (corridor bundling) if we ever route lines
  along real track. Research licensing (ODbL) and extract format (Overpass /
  planet rail layer). Relates to I and to the coverage gaps in A/K.

## U. C3 testing round 2 — reverts + reworks (2026-07-13)

Second browser test after the C3 fix batch. Two fixes REVERTED (didn't achieve
the goal), two kept, plus reworks:
- **Local transit — REVERTED** (revert of 90e967a). Label-only doesn't help:
  selecting a same-city sibling still routes the absurd real journey (Paris Gare
  de Lyon → Paris Austerlitz = 14h via Montpellier night train). PROPER FIX (user
  decision): add **fake intra-city transfer connections in the pipeline data** —
  short hops (~every few min) between same-city stations (from cities.toml groups)
  injected as transfer edges so RAPTOR routes through them cleanly. This ALSO fixes
  the Lille→Forbach detour (Paris Nord→Est transfer). Pipeline change + recompute.
- **Zoom declutter — REVERTED to near-inert** (revert of ba79538; original
  150/50/10 restored, effectively invisible). User dislikes that ES/FR empty out
  while DE/AT/PL stay overfull — uneven station density. REWORK: make it
  **density-aware** (normalise by local/country density, not a global n_dest
  threshold). Disabled for now; bundle with a density calc.
- **City exonyms — KEPT (d24160b), needs more:** works for EN (Brussels, Vienna…)
  but the CITY "all stations" option doesn't match other-language exonyms — e.g.
  German **"Warschau"** finds the Warsaw stations but not "Warszawa (all stations)".
  Add multilingual exonyms (DE/FR/IT/ES/... → native) to the city-option matcher.
  Also RELABEL "Paris — all stations" (em dash) → **"Paris (All stations)"** (user
  preference).
- **Corridor bundling — KEPT (e81c086) but insufficient:** Paris–Lyon region still
  a clusterfuck; only marginally better. Rework: many lines converge Paris→Lyon;
  needs better bundling (more corridors, or a real edge-bundling/geometry approach,
  possibly density-aware). See item I.

## W. Logo drive-off animation (2026-07-13)

Hovering/clicking the header logo triggers a playful animation (relates to D
Phase 3 — the inline lockup SVG in `web/src/App.tsx`):
- the **train logo only** (NOT the wordmark text) **winks**, then **drives off
  screen to the right and reappears from the left**;
- the **rail tracks expand ahead of it** (extend forward as it drives);
- the **stop circle** (the endstop after the text) **fades out** when the
  animation triggers.
CSS/SVG animation on the lockup sub-elements; respect prefers-reduced-motion.

## V. Default-stops parameter + domain routing (2026-07-13)

Add a parameter for the default number of stops (1/2/3 trains) preselected on load.
Domain routing: **nonstopeurope.eu** forwards to onestopeurope with **nonstop
(1 train)** preselected; **onestopeurope.eu** defaults to **onestop**. (User owns
nonstopeurope.eu.) Frontend URL/param handling.

## T. Search & planner UX polish (added 2026-07-13)

- **Station-search exonyms** — typing an English/common name should find the
  native station (e.g. "Rome" → Roma, general beyond the city-search exonyms
  added this session). Extend the server EXONYMS map (server/app.py) and/or the
  client search so common exonyms resolve for ALL stations, not only the 15
  grouped cities.
- **Clearing the origin promotes the destination** — when the user deletes/clears
  the From (start) station while a To (destination) is set, move the destination
  into the From box (so you can keep exploring from there) instead of resetting
  both. Small planner-state change in App/JourneyPlanner.
- **Mark stepovers/transfers on the map** — when a journey has a change of train,
  the interchange (stepover) station should be visually marked on the map (e.g. a
  distinct node/ring on the route line at each transfer), so multi-leg journeys
  are legible. Route lines already carry per-leg geometry (journeyLegPaths); the
  transfer point is the boundary between consecutive legs.
- **Map city-selection** (from 2026-07-13 testing) — cities are only selectable
  via the search today; clicking a city's member station on the map does not offer
  the whole-city union. Consider: clicking a member offers "select all of <City>".
  Design-first; interacts with the C3 union flow.

## X. Reach lines splay one polyline per stop instead of one shared trunk (added 2026-07-13)

User report: a single train that stops at many stations renders as a SEPARATE
"offspring" line from the origin per stop, not as one line threading through the
stops it serves. From Nijmegen you see one line ending at Arnhem, another
"going around Arnhem" to Dieren, another to Zutphen, another to Deventer — all
the same physical train. Looks bad and is likely part of the southern-France
mess (relates to item I).

**Data is NOT the cause (verified 2026-07-13).** Nijmegen's `reach_*.json`
journeys carry correct `via` lists: Dieren `via=[Arnhem]`, Zutphen
`via=[Arnhem, Dieren]`, Deventer `via=[Arnhem, Dieren, Zutphen]`. The stop
sequence is right in the data.

**It's a RENDERING problem** in `web/src/lib/geojson.ts::linesGeoJSON`: it emits
ONE independent LineString per destination and `journeyLegPaths` chaikin-smooths
each separately. So the shared trunk (Nijmegen→Arnhem) is drawn once per
downstream destination, and per-line smoothing rounds the Arnhem corner
differently each time, so overlapping trunks splay into a fan instead of
collapsing to a single trunk. Fix directions to brainstorm:
- **Merge into a tree**: group reach journeys by shared stop-sequence prefix and
  draw each physical segment (A→B) exactly once; destinations become endpoints on
  the shared trunk. Biggest, cleanest win.
- Or dedupe/snap overlapping segments before rendering.
- Reconsider per-line smoothing so shared segments can't diverge.

NOTE this differs from item I's Paris case: there the trains are genuinely direct
(`via=[]`), so there is no shared stop-sequence in the data to merge — that needs
real rail geometry / edge bundling. Same "too many lines" symptom, two mechanisms.
Do both under one brainstorm; a tree-merge here plus corridor geometry there.

## Y. Search ranking by station importance/size (added 2026-07-13)

Search ties are currently broken by NAME LENGTH (shorter wins) after the
prefix/substring tier — see `server/app.py::search` sort key `(tier, len(name))`.
So a minor station with a shorter name outranks the major hub the user meant:
typing "barce" surfaces **Barcelos** over **Barcelona**; typing "rome" surfaces
**Romanshorn** over **Roma** (noted while adding the Unit-3 exonyms). Rework the
ranking to weight station importance/size, e.g. `n_dest` (reach breadth, already
on stations and used for dot sizing) and/or capital/`n_routes`, so big hubs win
same-prefix ties. Keep prefix-over-substring as the primary tier; add an
importance term before (or instead of) name length. Small server change; add
ranking tests. Improves the exonym results from item T Unit 3 too.

## Z. "Ostbahnhof" is München Ostbahnhof; add a München city option (added 2026-07-13)

Two parts:
- **Naming/merge:** the station shown as bare **"Ostbahnhof"** (`x:db_fern:226810`,
  48.128, 11.605) is **München Ostbahnhof** with its city prefix stripped — it sits
  right beside `München Hbf` (`x:db_fern:127002`, 48.14, 11.56). It should carry the
  "München" prefix so it's findable/groupable (fix via `pipeline/station_names.toml`
  override), and if a second feed carries the same station under another name/id they
  should merge (validator blind spot: different names, <500 m — see the note below and
  item Q observability). Watch out: `Graz Ostbahnhof` (AT) is a DIFFERENT station.
- **City option:** add **München** to `pipeline/cities.toml` grouping München Hbf +
  München Ostbahnhof (and München-Pasing etc. if present) so the C3 city-union works
  for Munich like it does for Paris. Relates to C3 (`cities.toml` → `cities.json`) and
  item T Unit 4 (map city-selection popup).

## AA. Dark-mode veil tooltip unreadable — white text on white background (added 2026-07-13)

In dark mode the hover tooltip over the greyed-out (unreachable) countries is
unreadable: the text turns white (theme text var) but the tooltip **background stays
white**. The veil popup is a MapLibre `Popup` (`veilPopup`, created in
`web/src/components/Map.tsx` ~L129–138, copy from `web/src/lib/coverage.ts`
`veilTooltip`). MapLibre's default popup chrome is white and isn't themed. Fix: add a
theme-aware background (+ border/arrow) for the veil popup content in `web/src/index.css`
under the `[data-theme="dark"]` block (target the popup's container class, e.g. a
dedicated class set via the popup's `className`, or `.maplibregl-popup-content`). Ensure
the popup tip/arrow colour matches. Small CSS fix.

## Smaller deferred notes

- **Outdated logo/brand assets cleanup (added 2026-07-12):** several brand files
  linger unused after the logo went inline in `web/src/App.tsx`. `web/public/
  logo-mascot.svg` and `logo-mascot-light.svg` are referenced nowhere;
  `logo-train-light.svg` and `logo-lockup.svg` were already deleted. Audit
  `web/public/*` + `design/logo/*` and drop what nothing imports (keep the
  Inkscape source `onestopeurope-lockup-A1.svg` and `favicon.svg`). The header
  logo needs a real ExtraBold: ship `barlow-…-800.woff2` (only 400/600/700 are
  bundled) so the wordmark can use weight 800 instead of falling back to 700.

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
