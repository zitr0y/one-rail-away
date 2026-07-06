# onestopeurope — Clean-Slate Restart Design

**Date:** 2026-07-07
**Status:** Approved by Aaron (brainstorming session)
**Replaces:** de-trains-speed-map (all existing code; git history preserved)

## One sentence

Pick a European station, instantly see every station you can reach with at most
1, 2, or 3 trains, colored by travel time, and click through to book.

**Name:** onestopeurope (domain: onestopeurope.eu)
**Tagline:** "nonstopeurope with onestopeurope"

## Why a restart

The previous project (de-trains-speed-map) reconstructed a network graph by
scraping the Deutsche Bahn Timetables API — a keyed XML live-departure-board
API never meant for this. That single wrong data source caused most of the tech
debt: train-number matching, related-EVA merging, hour-by-hour fetching, rate
limiting, a 42MB scraped-JSON cache, and docs describing features that never
shipped. The map (Leaflet, straight origin→destination lines colored by "aerial
speed") answered a question nobody asked.

Kept as concepts: precompute-then-serve-static architecture, long-distance
station filtering, station grouping (the "related EVAs" lesson generalizes to
EU station merging).

## Decisions (with alternatives considered)

| Decision | Chosen | Rejected |
|---|---|---|
| Scope | EU long-distance rail, growable feed set | DE-only; all German trains |
| Data source | Static national GTFS feeds, offline pipeline | Live DB API (old approach); Transitous/MOTIS runtime routing (wrong query shape: A→B, not A→everywhere) |
| Core metric | Total travel time (color), transfer count (toggle) | Aerial speed (old); frequency as primary |
| Line rendering | Stylized via-station polylines (real stop sequence, smooth subway-style strokes) | True rail geometry (heavy, busy); straight spokes (can't follow lines) |
| Architecture | Python pipeline → static JSON → thin FastAPI → client map | Fully static (no server); live routing API |
| Booking | One provider (Trainline) deep link, ref code as empty config value | Multiple providers; unparameterized stub |
| Restart mode | Clean slate in same repo, history preserved | New repo; incremental gut |
| Dates | No date picker. Representative travel day (next Tuesday); vendor handles real dates/prices at booking | Full date-aware planner |

## Product (v1)

- Landing: muted, minimal MapLibre map of Europe; search box with autocomplete;
  clickable markers for long-distance stations. onestopeurope wordmark + tagline.
- Select origin → reachable destinations as dots colored by total travel time
  (buckets, e.g. <3h / 3–6h / 6–10h / >10h), connected by stylized polylines
  through the journey's actual via-stations.
- Transfer toggle named for the brand: **Nonstop / One stop / Two stops**
  (= 1/2/3 trains). Default: Nonstop — the differentiator vs chronotrains.
  Stations newly reachable at higher tiers are visually distinct.
- Click destination → journey card: legs (e.g. "ICE 517 → TGV 9573"), sample
  times, total duration, transfer station(s), direct trains/day, and a
  **Book this trip** button → Trainline deep link (origin, destination, default
  date "tomorrow", affiliate ref from config — empty until acquired).
- Only other control: max-travel-time slider.
- Fixed minimum transfer time (10 min) baked into computation. Not a UI knob.
- Coverage note in UI listing included operators/countries.

**Cut from v1 (YAGNI):** live delays, prices, date picker, multiple booking
providers, accounts/favorites, regional trains, exports, heatmaps, configurable
transfer times, multi-route-per-destination ranking.

## Architecture

```
feeds.toml ──► pipeline (fetch → build → compute) ──► data/out/*.json
                                                          │
                       FastAPI (dumb file reader) ◄───────┘
                              │
                       web (Vite + React + MapLibre GL)
```

### Pipeline (`pipeline/`, Python 3.14, uv + pyproject.toml)

Three pure stages; files are the interface between them:

- `uv run ose fetch` — download GTFS zips per `feeds.toml` entry (URL, license,
  country, long-distance route filters). v1 feeds: gtfs.de long-distance (DE),
  SNCF (FR), ÖBB (AT), opentransportdata.swiss (CH), NS (NL). SNCB (BE) is the
  first post-v1 addition.
  Feeds download independently; one failure never aborts the run.
- `uv run ose build` — parse GTFS (csv/pandas or duckdb; no GTFS framework):
  - Filter to long-distance: `route_type` rail + per-feed route-name allowlist
    (ICE/IC/EC/TGV/RJ/NJ/EST/…) configured in `feeds.toml` — per-country quirks
    quarantined in config, not code.
  - Merge stations across feeds: UIC codes where available (usually embedded in
    rail stop_ids), fallback name + coordinate proximity (<500m), manual
    `station_aliases.toml` for stubborn cases. Border stations must merge or
    cross-feed transfers are invisible.
  - Extract one representative travel day (next Tuesday — avoids weekend and
    holiday gaps).
  - Output: station registry (id, name, lat, lon, country) + normalized trip
    table (trip → ordered stop times).
- `uv run ose compute` — RAPTOR capped at 3 rounds from every origin, 10-min
  minimum transfer. Per destination keep: best duration per round tier, winning
  journey legs (train name, times, transfer stations, ordered via-station list
  per leg — this draws the polylines), direct trains/day. Low thousands of
  stations → all-origins compute is minutes.

Output (`data/out/`):
- `stations.json` — registry + which stations have reachability files
- `reach_<station_id>.json` — one file per origin
- `meta.json` — computed_at, sample date, feed versions

Freshness: rerun weekly (`just pipeline` now; GitHub Action cron once
deployed). No runtime caching — the files are the cache.

### Server (`server/`, FastAPI, same uv workspace)

Reads `data/out/`, nothing clever:

- `GET /api/stations` — registry for markers/search
- `GET /api/stations/search?q=` — accent-insensitive, prefix-weighted name search
- `GET /api/reach/{station_id}` — precomputed file verbatim; client filters by
  tier/time (no query params)
- `GET /api/meta` — freshness for the "computed on …" footer
- Errors: 404 unknown station; 503 with clear message if pipeline never ran.
  CORS open in dev.

Booking deep link is built client-side (`booking.ts`: string formatting from
journey data + `VITE_TRAINLINE_REF` env var); server stays a file reader.

### Frontend (`web/`, Vite + React + TypeScript)

- **MapLibre GL JS** + free OpenFreeMap vector tiles (no key, no caps), custom
  muted grayscale style so the reachability layer is the only loud element.
  No Leaflet, no react-leaflet, no wrapper libs — integration is a ~50-line hook.
- Destinations and lines are two GeoJSON sources swapped on origin/toggle
  change. Polylines: rounded caps, curve smoothing, travel-time color ramp,
  thicker = direct. No clustering needed at this scale.
- State: plain React state + one fetch hook (~4 state variables: origin, tier,
  max-time, selected destination). No Redux/zustand/SWR.
- Components: `Map`, `SearchBox`, `StopToggle`, `TimeSlider`, `JourneyCard`,
  `Legend`.

## Repo layout & dev experience

```
onestopeurope/
├── pipeline/        # Python 3.14: fetch/build/compute (uv workspace)
├── server/          # Python 3.14: FastAPI (same workspace, shared models)
├── web/             # Vite + React + TS + MapLibre GL
├── data/            # raw/ graph/ out/ — gitignored except sample out/
├── feeds.toml
├── justfile         # just dev | pipeline | test
└── README.md        # short, honest, <100 lines
```

- `just dev` runs uvicorn + Vite together with prefixed logs.
- `.vscode/launch.json` compound config: F5 attaches Python + browser debuggers
  simultaneously.
- Sample `reach_*.json` for ~5 stations committed so a fresh clone shows a
  working map without running the pipeline.

## Error handling & testing

- Pipeline: per-feed failure isolation (skip + report); post-build validation
  fails loudly on nonsense (0,0 coordinates, negative travel times, obvious
  unmerged duplicates). Silent `except: pass` is banned.
- Server: pytest + TestClient against a fixture data dir.
- Pipeline: hand-written fixture GTFS (~10 stations, 2 "countries") with
  hand-verified 1/2/3-train reachability — the test that matters, because
  RAPTOR bugs are silent-wrong-answer bugs.
- Frontend: TS strict; vitest for journey/booking-link formatting. No e2e in v1.
- Tooling: ruff + pre-commit (Python), ESLint + Prettier (web).

## Migration

1. Commit current working tree as-is (history checkpoint).
2. Delete everything except `.git`, this spec, and `.env.example` shape.
3. Scaffold the layout above. Nothing from the old code is carried over;
   station-grouping and long-distance-filter *lessons* are encoded in the
   station-merge and feed-config design.

## Risks

- **Feed quality varies by country** (IT/ES notoriously spotty). Mitigation:
  curated growable feed list; UI states coverage honestly.
- **Station merging is the hard 20%.** Mitigation: UIC-first strategy, alias
  file escape hatch, validation step surfaces unmerged duplicates.
- **Trainline deep-link format may change/not prefill.** Mitigation: isolated
  in `booking.ts`; worst case link to search page with ref only.
- **gtfs.de long-distance feed licensing** (CC BY / non-commercial nuances) —
  verify terms before monetizing with ref codes; DELFI is the fallback source.
