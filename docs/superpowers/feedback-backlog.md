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

## A. Add more national feeds (user item 2 — "Barcelona only shows France")

From Barcelona only the SNCF corridor shows; Madrid/Porto are unfindable because Spain/
Portugal aren't ingested at all. Candidate feeds to research (all publish GTFS): Renfe
(ES), CP (PT), Trenitalia/RFI (IT), PKP Intercity (PL), ČD (CZ), MÁV (HU), DSB (DK).
Each new feed needs: entry in `feeds.toml` with evidence comments, route_allow filter
for long-distance only, merge aliases for border stations (`station_aliases.toml`), and
a full pipeline re-run. Expect merge/station-name collisions — read
`.superpowers/sdd/progress.md` Session 4 + final-review-triage notes before touching
merge code.

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

## C. Dot sizing / clustering / city grouping (user item 4)

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

## D. Branding / map styling (user item 7)

Water should read differently from stations; overall corporate identity still needed.
User's sketch: EU-train theme, cute EU train in the logo that could "bend along the
chosen route if exists". Map style should follow the identity (OpenFreeMap styles can
be customized). Tagline is fixed: "nonstopeurope with onestopeurope".

## E. Grey out countries not in the system (user item 8)

Make it visually clear which countries are (not yet) covered, without implying
unreachability — could be "not yet in our system". Needs: corrected geographic
`country` field (done in bug batch), a notion of "covered country" (probably: countries
whose national feed we ingest, i.e. feeds.toml, NOT countries that merely have leaked
stations), and a map fill layer. Interacts with A (each new feed un-greys a country).

## F. Selection UX: unselect + origin/destination clicking (added 2026-07-09 evening)

User report: "unselecting a station/selecting a new station is wonky by clicking. You can
always select a new station via the search bar, but not via clicking — you'll be stuck in
the choose-next-station/nothing-happens state. Should probably have an unselect button on
the footer (status bar). Also selecting one station and then another does not always show
the connection — sometimes it just switches to the new station."

Likely mechanism (verify when picking this up): in `web/src/components/Map.tsx` the
`all-stations` and `reach-dots` layers overlap once a reach is loaded — a colored
destination dot usually ALSO has an all-stations dot underneath, and MapLibre fires a
click handler per layer, so one click can trigger BOTH `onSelectOrigin` (switching
origin!) and `onSelectDestination`. Whether you see "connection" or "switched station"
depends on handler order/feature hit — matches the "sometimes" behavior. Fix sketch:
single click handler with `queryRenderedFeatures` + explicit precedence
(destination-dot wins while a reach is active), plus an unselect (×) affordance in the
status bar and Escape-to-unselect.

## G. Merge-logic gap: UIC-registered stops never proximity-merge (found 2026-07-10)

Systemic (documented in station_aliases.toml's header, hit again during the SBB filter
fix): a stop that registers via UIC-regex extraction becomes canonical directly —
name+proximity matching never runs for it, so it duplicates any existing non-UIC
canonical station (evidence: 48 SNCF `StopArea:OCE…`-vs-bare-UIC pairs + Konstanz when
French Intercités briefly entered via the Swiss feed; each currently needs a manual
alias). Design options: (a) sncf `uic_regex` extracting the 7-digit code from
`StopArea:OCE<8digit>` ids — SNCF stations then UIC-merge automatically, but ALL SNCF
canonical ids change (regenerate everything, check nothing hardcodes them); (b) make
merge fall back to name+proximity before minting a fresh UIC canonical. Read
`.superpowers/sdd/progress.md` Session 4 + final-review-triage before touching merge.

## H. Cheap FR coverage win: SNCF Intercités are filtered out (found 2026-07-10)

The sncf feed's route_allow currently keeps TGV-style only; France's Intercités network
(POLT Paris–Limoges–Toulouse, Nantes–Lyon, Paris–Clermont, night Intercités…) exists in
the sncf feed but is dropped. They're real long-distance trains — ingesting them
meaningfully densifies France without adding any new feed. (They also exist duplicated
inside the Swiss feed under labels like "IC190A", agency 87_LEX — do NOT ingest them from
there; provenance belongs with SNCF.) Likely wants G solved first (their stops must merge
cleanly). Relatedly: SNCF train labels task (`.superpowers/sdd/sncf-labels-findings.md`)
touches the same load path — consider doing together.

## I. Corridor bundling for reach lines (added 2026-07-10)

User: Paris shows ~15 separate straight lines fanning over southern France; "I feel like
they all go via Lyon or Vichy and should be just 2-4 lines with breakouts." Data check
confirms the trains are genuinely direct (Paris→Valence TGV 16×/day NONSTOP, Mâcon-Loché
6×, Le Creusot 3× — all via=[]), so each polyline is a single straight segment; the trains
physically share the LGV corridor but our lines don't. Fix directions to brainstorm:
(a) route along real rail geometry (GTFS shapes.txt if the feeds carry it, or OSM rail),
(b) algorithmic edge bundling, (c) force lines through nearest corridor waypoints. Big
visual win, medium-to-large effort. Related to D (map styling).

## J. Highlight the selected journey — DONE 2026-07-10

Shipped (merge b01fb6f): selected journey's line 4px full-opacity on a dedicated
`reach-lines-selected` layer, others dim to 0.12; dots untouched. Thick-line styling is
provisional — revisit for an animated train when branding (D) lands.
Spec: `docs/superpowers/specs/2026-07-10-journey-highlight-design.md`.

## Smaller deferred notes

- Search only finds stations that have reach files (`has_reach` gate in
  `server/app.py::search`) — fine today, revisit when coverage grows.
- Cross-feed duplicate trains observed (ICE 82 Paris–Frankfurt appears in both SNCF
  and DB feeds as separate trips) — may double-count `direct_per_day`; worth checking
  when touching compute.
- Pre-existing deferred minors from the build ledger still open: `remap_trips` in-place
  mutation trap, dead `uic_regex` comment, O(n²) validate check, search `limit`
  validation, map `easeTo` re-centering on every filter change.
- ~~SNCF train labels~~ DONE 2026-07-10 (merge f9ca9f1): brand+number via
  `stop_id_brand` + trip_headsign ("TGV INOUI 9704", "IC 50" Paris–Bruxelles); join
  safety verified (201 non-SNCF joins unchanged, 0 SNCF-touching).
- Pipeline QoL DONE 2026-07-10 (merge 4b9ca46): `ose compute` now parallel
  (`--workers`, default one per CPU) and prunes stale reach files (stale files broke
  has_reach-from-disk when canonical ids change). The 46-min compute run on 2026-07-10
  was on battery power; mains + parallelism should be minutes.
- Final-review note (sncf-labels): document near through.py that SNCF ICE numbers
  (95xx) are disjoint from db_fern ICE numbers — a future feed refresh with a shared
  number would silently start joining.
