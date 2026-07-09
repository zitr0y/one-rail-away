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

## Smaller deferred notes

- Search only finds stations that have reach files (`has_reach` gate in
  `server/app.py::search`) — fine today, revisit when coverage grows.
- Cross-feed duplicate trains observed (ICE 82 Paris–Frankfurt appears in both SNCF
  and DB feeds as separate trips) — may double-count `direct_per_day`; worth checking
  when touching compute.
- Pre-existing deferred minors from the build ledger still open: SNCF train labels are
  opaque line codes (top user-visible), `remap_trips` in-place mutation trap,
  dead `uic_regex` comment, O(n²) validate check, search `limit` validation,
  `web/README.md` boilerplate, map `easeTo` re-centering on every filter change.
