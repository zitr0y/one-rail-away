# Data sources

Everything this project ingests, and everything we wanted but could not get.

- **Timetable config is `feeds.toml`** — that file is the source of truth and carries
  the full per-feed forensics (route filters, stop-id quirks, licence caveats). This
  page is the human index; don't duplicate detail here, link to it.
- Per-feed research verdicts live in `docs/superpowers/feedback-backlog.md`; the
  process for adding a feed is `docs/superpowers/new-feed-recipe.md`.

## In use — timetable feeds

Eleven feeds covering **ten countries**. Long-distance rail only: each feed's
`route_allow` / `trip_allow` selects intercity products and excludes commuter,
metro, tram, bus and ferry.

| Feed | Country | Products kept | Licence |
|---|---|---|---|
| `db_fern` | DE | ICE, EC/ECE, NJ, RJ/RJX, TGV, EST | CC BY 4.0 — *verify commercial terms* |
| `flix` | DE | FlixTrain (FLX10/20/30) | ODbL 1.0 |
| `sncf` | FR | TGV INOUI, OUIGO, Lyria, Intercités (+ de nuit), ICE, IC | ODbL |
| `oebb` | AT | RJX, RJ, ICE, EC, IC, EN, NJ, D | CC BY 4.0 |
| `sbb` | CH | ICE, EC, TGV, RJ, NJ, IC/IR (incl. domestic IC1/IR16) | Open data (opentransportdata.swiss) |
| `ns` | NL | Intercity, ICE, Eurostar, Nightjet | CC0 |
| `rejseplanen` | DK | IC, ICL, ECE, RJ, RE | Open data — *verify reuse terms* |
| `cp` | PT | AP, IC, IR, R | "No licence – No contract" (PT NAP) — *attribution: CP* |
| `trenitalia` | IT | FR, FA, FB, EC, IC, ICN, EN, EXP | "No licence – No contract" (IT NAP) — *attribution: Trenitalia* |
| `renfe` | ES | AVE, AVE INT, ALVIA, AVLO, Intercity, EUROMED, TRENCELTA | Spanish public-sector reuse — *attribution: Renfe* |
| `pkp` | PL | EIP, EIC, IC, TLK, LEO, RJ, EC, EN | CC BY 4.0 / PKP PLK (mkuran.pl) |

`trenitalia` is NeTEx L1 (gzipped XML); every other feed is a GTFS zip.

**Several licences are not settled for commercial use** (`db_fern`, `rejseplanen`,
`cp`, `trenitalia` — see the caveats above). Re-check each before monetizing.

## In use — geodata

| Source | Used for | Licence |
|---|---|---|
| **OpenStreetMap** via Geofabrik per-country extracts | Real rail geometry (`ose paths` → `rail_paths.json`). Cached rail-only in `data/osm/` | ODbL — **attribution required**, rendered in the map's attribution control |
| **OpenFreeMap** planet vector tiles (OpenMapTiles schema, OSM data) | Basemap | ODbL (OSM) |
| **Natural Earth II** shaded relief raster (served by OpenFreeMap) | Terrain shading | Public domain |

Everything in `data/out/` (`stations.json`, `reach_*.json`, `cities.json`,
`coverage.json`, `rail_paths.json`) is **derived by our own pipeline**, not ingested.

## Wanted — not obtained

### Countries on the map with no feed of their own

These have stations only because a neighbour's feed carries international trains
through them ("leaks"). They are greyed by the coverage veil: you can travel *to*
them, but we cannot compute journeys *from* them.

| | | | |
|---|---|---|---|
| CZ 42 stations | SI 20 | HU 14 | UA 13 |
| BE 10 | SK 8 | HR 5 | LU 1 |
| RO 1 | LI 1 | LT 1 | **GB 1** |

**Great Britain is the biggest hole**: the only GB station on the map is London
St Pancras, leaked via Eurostar. No British national rail feed is integrated.

### Operators missing inside countries we *do* cover

A country being "covered" does not mean every train in it is on the map. Several of
our sources carry **only the incumbent**, so open-access competitors are invisible —
a route they serve can look worse than it really is, or vanish entirely.

Verified single-operator sources (checked in the live feeds' `agency.txt` / NeTEx):
`trenitalia` (Trenitalia only), `renfe` (RENFE OPERADORA only), `cp` (CP only).

| Country | We have | Missing | Status |
|---|---|---|---|
| IT | Trenitalia | **Italo (NTV)** — the main high-speed competitor | not researched |
| ES | Renfe | Ouigo España | GTFS exists on the Spanish NAP; not integrated |
| ES | Renfe | iryo | no public GTFS (checked 2026-07-10) |
| AT | ÖBB | WESTbahn (Vienna–Salzburg) | not researched |
| FR | SNCF | Trenitalia France (Frecciarossa Paris–Lyon–Milan) | not researched |
| CZ/SK | *(no feed)* | RegioJet, Leo Express | not researched |

"Not researched" means exactly that — nobody has checked whether a usable feed exists.
These are the cheapest wins on this page.

Multi-operator sources, for contrast: `pkp` (PKP IC + Leo Express + RegioJet patterns),
`rejseplanen` (26 agencies incl. DSB), `sbb`, `ns`, `db_fern` (+ `flix` for FlixTrain).

### Researched and rejected (with reasons)

Full verdicts in `docs/superpowers/feedback-backlog.md`.

- **Norway (Entur)** — *blocked, not licence.* The national aggregated GTFS is freely
  available under NLOD (commercial use OK with attribution). But it models
  rail-replacement buses *inside* the rail routes with no trip-level mode marker we
  can filter on, so shipping it would draw bus diversions as train corridors.
  Revisit if Entur exposes a rail-only feed or a usable trip-level marker.
- **Czechia**, **Hungary**, **Belgium** — researched 2026-07-14, each rejected for
  source-specific reasons; see the backlog verdicts.
- **Ouigo España** — GTFS exists on the Spanish NAP; not yet integrated.
- **iryo** (ES) — publishes no public GTFS. No scraping or proprietary APIs attempted.

### Data we want but have no source for

- **Which services are genuinely seasonal.** We deliberately call *nothing* seasonal
  (backlog **AF**): the previous GTFS-calendar heuristic was so wrong it flagged
  Dortmund–Munich (17 trains/day) as seasonal. Real seasonal services — some
  Nightjets, Alpine and summer-only routes — are a short list that needs to be
  **curated from outside our feeds**. No feed we have expresses this reliably.
- **Which physical track a train actually uses.** Feeds give calling points, never
  track. `ose paths` *infers* the route (speed-weighted A* over OSM rail), which is
  right almost always but can pick a high-speed line where a slower service really
  takes the classic route. The legs' `dep`/`arr` times could disambiguate this and
  nobody has to give us the data — see the note in `pipeline/railpaths.py`.

---

*Adding a feed? Follow `docs/superpowers/new-feed-recipe.md`, then update this page
and `feeds.toml` together.*
