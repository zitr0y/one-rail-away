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

## A. Add more national feeds — ongoing (Renfe + PKP + Denmark/DSB + FlixTrain + Portugal/CP shipped)

Denmark is now covered by the Rejseplanen DSB feed: IC, ICL, ECE, RJ, and RE
(including regional RE after the 2026-07-13 filter correction). FlixTrain and the
official CP Portugal feed are also shipped. CP is a direct, registration-free GTFS
download from `publico.cp.pt`; it includes AP, IC, IR, and R services and carries a
rolling publication horizon, which the per-feed coverage-aware sampler excludes from
out-of-horizon denominators. Italy is now covered by the official Trenitalia Italian
NAP NeTEx L1 publication: FR/FA/FB/EC/IC/ICN/EN/EXP, with the source’s explicit
“No licence – No contract” metadata retained as a commercial-reuse caveat. Further
national feeds remain ongoing; next candidates and research verdicts live in
`docs/superpowers/new-feed-recipe.md`. Each new feed un-greys a country (see the
two-tier veil). Competitor note: Ouigo España publishes GTFS on
nap.transportes.gob.es; iryo does not.

## B. Multi-day sampling / service frequency (user item 6) — SHIPPED 2026-07-13

The pipeline now samples deterministic Tuesday + Saturday probes in January,
April, July, and October (8 dates across the anchor year). Each date retains its
own graph and RAPTOR result; aggregation picks the best route per train-count
tier, never joins legs from different dates. Reach destinations carry sampled
availability, direct-trip evidence, active sample months, and only a rounded
weekly estimate. The map renders limited/seasonal sampled connections dashed;
the planner says e.g. "about 3× per week" and identifies the sampled months.
Tuning point: `pipeline/sampling.py` (`SEASON_MONTHS`, `SAMPLE_WEEKDAYS`).
Probes outside a route feed's published GTFS horizon are excluded from its
denominator, and a route with fewer than three covered probes is labeled limited
feed coverage rather than seasonal. Limitation: sparse probes cannot prove an
exact timetable or a continuous season, so the UI deliberately avoids claiming
operating dates.

**Follow-up fix 2026-07-14:** coverage is now checked independently for every
feed before parsing a probe: out-of-horizon dates are logged once per feed and
skipped, never treated as zero-service evidence. Frequency denominators retain
only the relevant route feeds' usable probes, even when other feeds cover a
different horizon. Independent feed loading now runs in separate processes;
the parent merges results in a fixed order for deterministic output.

**Performance follow-up 2026-07-14:** profiling showed `ose compute` already
keeps its reachability work in worker processes; its parent-only tail is about
2 seconds. The reported long single-core interval after feed sampling was in
`ose build`: station merge and duplicate validation repeatedly scanned all
stations. Both now index stations by normalized name while preserving insertion
and report order. On the 2,442-station production graph, validation fell from
43.467 seconds to 0.018 seconds (~2,400×), and merge profiles at 0.080 seconds.

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

## C. Dot sizing / clustering / city grouping (user item 4) — C1 DONE, C2 tried+rejected, remainder SHIPPED

C1 (dots sized by n_dest) + capital stars shipped 2026-07-11
(spec 2026-07-11-dots-clustering-design.md). C2 clustering shipped and was
removed same day (killed the density picture). C3 city-union and the remaining
click-disambiguation work are shipped; neither changes the density picture.

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
- stations too close together now present a quiet, name-sorted station chooser on
  click when several visible dots overlap (with a small click tolerance); hits
  are deduplicated by station id and a lone station still selects directly —
  **SHIPPED 2026-07-14**.

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

**De-emphasise roads + surface railways/borders — SHIPPED 2026-07-13, user-calibrated
(2 rounds):** all `highway_*`/`tunnel_*` line layers carry flat `line-opacity`
**0.25 light / 0.2 dark**. The basemap `railway` layer (real OSM rail) now starts at
**z8** (was 13; tiles carry no rail below ~z8) with width ramp 0.75@z8→7@z20,
colored to outrank roads: `#B0A99B` light / `#4C639A` dark, opacity 0.9. Country +
state boundary colors strengthened (`#A9A294`/`#B3AC9E` light, `#55689C`/`#49598A`
dark). All TUNING POINTS. Road labels/shields (z12+) not faded — revisit if they
shout at street zoom.

## I. Corridor bundling for reach lines (added 2026-07-10)

**Direction agreed with user (2026-07-13, after the X trunk-merge):** route reach
lines along REAL rail geometry (OpenRailwayMap/OSM rail extract — see item S),
not a spline through stops; synthetic curves that don't follow track are exactly
what the user dislikes. The X fix helps here: the base layer now draws deduped
per-hop segments (`segmentsGeoJSON`), so real geometry can be attached per
physical hop (station-pair → track path lookup) instead of per journey. Curated
`corridors.ts` becomes a stopgap to retire.

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
  (The "Paris (All stations)" relabel shipped 2026-07-13 with item T Unit 3.)
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

## T. Search & planner UX polish — SHIPPED 2026-07-13

All four sub-features shipped (commit dc208e6; spec + plan 2026-07-13-planner-
search-ux-polish). Follow-on/adjacent work lives in items Y (search ranking by
importance — "rome" still surfaces Romanshorn over Roma), X (reach-line splay),
and U (multilingual city exonyms). Curated exonyms are extensible in
`server/app.py::EXONYMS`; the transfer-ring style and the city-choice popup are
flagged tuning points awaiting the user's visual calibration.

## X. Reach lines splay one polyline per stop instead of one shared trunk — SHIPPED 2026-07-13

Fixed as diagnosed below, both halves (no user brainstorm — explicit "just do it"):
- `journeyLegPaths` keeps served stops as EXACT vertices (chaikin no longer cuts
  the corner at a via stop, which was what splayed identical trunks). Nonstop
  legs still follow curated corridors, chaikin-smoothed.
- New `geojson.ts::segmentsGeoJSON` + `legSegments`: the base line layer now
  draws direction-normalized, deduped stop-to-stop segments (new map source
  `reach-segments`) — each physical hop drawn once, bucket = fastest journey
  through it, width class = most direct. Per-destination `linesGeoJSON` remains
  only for the selected-journey highlight (filter-by-id) and the rider, which
  share geometry with the segments by construction.
- Verified on Berlin Hbf reach: trunks collapse to a tree with per-segment color
  progression outward. Item I (genuinely-direct Paris fan) remains open — that
  half needs corridor geometry, see NOTE below.

### Original report (kept for context)

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

## Y. Search ranking by station importance — SHIPPED 2026-07-13

Sort key is now `(prefix-before-substring, capitals-first, -n_dest, name-length)`
(commit b42de81). Fixed "barce"→Barcelona and "rome"→Roma; capitals-on-top is a
general win. NOTE: `n_dest` alone would have ranked Romanshorn ABOVE Roma (it has
more reach), so `is_capital` carries the Roma case — which fully resolves anyway
once Italian data lands.

## Z. "Ostbahnhof" is München Ostbahnhof; add a München city option (added 2026-07-13)

Two parts:
- **Naming/merge:** the station shown as bare **"Ostbahnhof"** (`x:db_fern:226810`,
  48.128, 11.605) is **München Ostbahnhof** with its city prefix stripped — it sits
  right beside `München Hbf` (`x:db_fern:127002`, 48.14, 11.56). **Rename it to
  "München Ostbahnhof"** (user-confirmed 2026-07-13) so it's findable/groupable (fix
  via `pipeline/station_names.toml` override keyed on `x:db_fern:226810`), and if a
  second feed carries the same station under another name/id they
  should merge (validator blind spot: different names, <500 m — see the note below and
  item Q observability). Watch out: `Graz Ostbahnhof` (AT) is a DIFFERENT station.
- **City option:** add **München** to `pipeline/cities.toml` grouping München Hbf +
  München Ostbahnhof (and München-Pasing etc. if present) so the C3 city-union works
  for Munich like it does for Paris. Relates to C3 (`cities.toml` → `cities.json`) and
  item T Unit 4 (map city-selection popup).
- **More multi-station cities need groups (added 2026-07-13):** the 15-city
  `cities.toml` is missing obvious multi-station cities. **Prague** has ≥4 (Praha hl.n.,
  Praha-Holešovice, Praha-Podbaba, Praha-Libeň) and needs a group too. Do a sweep for
  other ungrouped multi-station cities (Hamburg, Frankfurt, Köln, Wien, Milano, etc.)
  and add the clear ones. Same C3 mechanism.

## AA. Dark-mode veil tooltip unreadable — SHIPPED 2026-07-13

Fixed as sketched: the popup gets `className: "veil-popup"`; `index.css` themes
`.veil-popup .maplibregl-popup-content` (background/color/shadow via theme vars)
plus all 8 anchor-side `.maplibregl-popup-tip` border colours. Verified computed
styles in dark mode (#0B1533 surface, #E8ECF7 text, tip matches). NOTE: local
`data/out` subset has no coverage.json, so the real veil can't render locally —
verified via injected popup markup instead.

## AB. all-stations fade/pin opacity expression is invalid — SHIPPED 2026-07-13

`allStationOpacityExpression` now keeps `zoom` as the input of the outer
`interpolate`; each zoom-stop output uses a zoom-free id `match`. This retains
the established zoom decluttering, fades non-pinned stations during reach and
journey views, and pins the origin plus journey stations at 0.7. Focused tests
assert the generated expression has no nested `zoom` and retains both fade and
pin branches.

## Smaller deferred notes

- **Click-disambiguation popup ranking (added 2026-07-14):** when clicking
  bunched-up station dots, put the "City (all stations)" entry first and in
  **bold** when one exists, then sort the remaining stations by connection count,
  matching the ranking already used by search. This refines item C, whose current
  interaction the user otherwise likes.

- **Pre-existing flaky compute test on Python 3.14 (found 2026-07-13):**
  `tests/test_compute.py::test_compute_all_sets_is_capital` FAILS on `main`
  (independent of any recent change) with `capitals.toml: no station matches
  LA='Alpha Hbf'`. Cause: the test does `os.chdir(tmp_path)` then runs
  `compute_all`, but Python 3.14 no longer defaults `multiprocessing` to `fork`,
  so worker processes don't inherit the changed cwd and read the wrong (or no)
  `capitals.toml`. codex also saw compute tests fail under a sandboxed
  forkserver. Fix by passing an explicit path into the capitals loader (don't
  rely on cwd) or setting the mp start method in the test. Not caused by search
  or the item-T work.

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
