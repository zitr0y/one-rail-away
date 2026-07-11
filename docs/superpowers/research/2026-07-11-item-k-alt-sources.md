# Item K — Alternative / supplementary data sources: research verdicts

Research date: 2026-07-11. Follows the verdict format from `new-feed-recipe.md`.

---

## 1. FlixTrain / FlixBus open GTFS

| Fact | Detail | Status |
|------|--------|--------|
| Download URL (EU) | `https://gtfs.gis.flix.tech/gtfs_generic_eu.zip` | **VERIFIED** — HEAD 200, `content-type: application/zip`, 31.6 MB, `last-modified: Sun, 05 Jul 2026 21:15:40 GMT`, served via CloudFront/S3 |
| Download URL (US) | `http://gtfs.gis.flix.tech/gtfs_generic_us.zip` | READ-ABOUT (Transitland Atlas `flix.tech.dmfr.json`, not HEAD-checked) |
| Download URL (GB) | `http://gtfs.gis.flix.tech/gtfs_generic_gb.zip` | READ-ABOUT (MobilityDatabase catalog) |
| Transitland IDs | `f-u-flixbus` (EU), `f-9-flixbus` (US) | **VERIFIED** — read from `transitland-atlas/feeds/flix.tech.dmfr.json` |
| Registration required | No | **VERIFIED** — direct curl, no auth |
| Also on transport.data.gouv.fr | "Réseau européen FlixBus et FlixTrain" dataset page | READ-ABOUT — the page hosts the same data; the direct download URL rotates per update |

### FlixTrain separable from FlixBus?

**Yes — two reliable methods** (READ-ABOUT, corroborated by multiple sources):

| Method | FlixBus | FlixTrain |
|--------|---------|-----------|
| `agency_id` in `agency.txt` | separate agency entry | separate agency entry |
| `route_type` in `routes.txt` | `3` (Bus) | `2` (Rail) — possibly extended types `100`–`109` |

For our pipeline: filter `routes.txt` on `route_type != 3` (same pattern as existing
`route_allow`). Alternatively filter on `agency_id`.

### License

- **ODbL** (Open Database License, share-alike) per the transport.data.gouv.fr metadata.
  READ-ABOUT — this is the most authoritative license statement found; the `gtfs.gis.flix.tech`
  endpoint itself has no embedded license. Recommend checking `feed_info.txt` inside the
  downloaded ZIP for any `feed_publisher_url` / `feed_license_url` fields.
- FlixBus does **not** officially market the GTFS as "open data" — it is published for EU NAP
  compliance (Delegated Regulation 2017/1926) and consumed by aggregators. No explicit
  CC BY; the ODbL tag comes from the French portal.

### Update cadence

~Weekly (READ-ABOUT). Observed dates on gouv.fr: 2026-06-07, 2026-06-28, 2026-07-05.
The `last-modified` header on the verified URL confirms 2026-07-05.

### Difficulty: EASY

Standard GTFS zip, no registration, stable direct URL, separable by `route_type`.
Our existing pipeline already handles multi-agency/multi-mode feeds (SNCF precedent).
Only needs `route_allow` pattern for rail types and an `agency_id` or `route_type` filter.

### Integration notes

- FlixTrain runs in DE (Berlin–Stuttgart, Hamburg–Köln, etc.) + SE (Stockholm–Göteborg).
  Would add open-access long-distance rail lines that DB Fernverkehr GTFS does not carry.
- The feed is EU-wide and huge (31+ MB); aggressive filtering essential.
- ODbL share-alike is more restrictive than CC BY 4.0 (used by most of our feeds).
  Need to evaluate whether the project's output constitutes a "derivative database" under
  ODbL. If so, the whole output DB would need ODbL or compatible licensing. **Discuss with
  user before integrating.**

> **Recommendation:** Integrate — EASY technically, but license (ODbL share-alike) needs a
> product-level decision before proceeding.

---

## 2. Direkt Bahn Guru

| Fact | Detail | Status |
|------|--------|--------|
| GitHub repo | `juliuste/direkt.bahn.guru` | **VERIFIED** — archived, read-only |
| API repo | `juliuste/api.direkt.bahn.guru` | **VERIFIED** — archived, ISC license |
| Archived date | ~2025-07-20 (last push), marked archived 2026-05-10 | **VERIFIED** — GitHub API |
| API endpoint | `https://api.direkt.bahn.guru/` | **VERIFIED DEAD** — curl returns exit code 60 (SSL error), size 0 |
| Website | `https://direkt.bahn.guru/` | **VERIFIED DEAD** — not responding |
| Suggested alternative | `https://github.com/ton-An/station_reach` | READ-ABOUT (linked from archived README) |
| Code license | ISC (permissive) for the frontend, GPL-3.0 for the frontend repo | **VERIFIED** — GitHub API |
| Data license | None / proprietary DB data | READ-ABOUT — the data came from an unofficial, reverse-engineered Deutsche Bahn HAFAS API |

### What it was

A **live query wrapper** around a legacy, unofficial DB HAFAS API. For a given origin station,
it returned all directly reachable destinations (no transfers) with journey durations.
It was **not a static dataset** — no CSV/JSON/GTFS dump was ever published. Data was
near-real-time (schedules for upcoming 1–2 weeks).

### How chronotrains used it

Chronotrains queried the Direkt Bahn Guru API to get direct connections + durations, then
pre-computed travel-time isochrones (with 20-min interchange assumption) and stored them as
GeoJSON in PostgreSQL/Supabase. The chronotrains data was therefore a **snapshot**, not
live. Chronotrains itself is "all rights reserved" — no data can be extracted from it.

### Current status: DEAD

The upstream DB legacy API was shut down / changed. The Direkt Bahn Guru project lost its
data source and was archived. No data can be obtained from it. The chronotrains project
still shows a working map but its data is a frozen snapshot — not queryable or downloadable.

### Difficulty: N/A — unusable

> **Recommendation:** Skip — the project is dead, the API is offline, and no static data
> dump exists. Our GTFS-based approach already covers the same ground (DB Fernverkehr feed)
> with richer, more current data.

---

## 3. Back On Track night-train data

| Fact | Detail | Status |
|------|--------|--------|
| GitHub repo | `Back-on-Track-eu/night-train-data` | **VERIFIED** — active, 256 commits |
| Last commit | `2026-07-11T14:29:13Z` "Auto update 2026-07-11" | **VERIFIED** — GitHub API |
| Update cadence | Automated, ~daily | **VERIFIED** — commits on 2026-07-11, 2026-07-09, 2026-07-08 |
| License | **GPL-3.0** (data repo) | **VERIFIED** — GitHub repo metadata |
| Map license | CC-BY-NC-ND 4.0 (visual map only) | READ-ABOUT (back-on-track.eu) |
| Format | JSON files in `data/latest/` | **VERIFIED** — fetched and parsed |
| Data API (Google Apps Script) | `script.google.com/macros/s/AKfycbw.../exec?table=<name>` | **VERIFIED** — GET returns 200 + JSON (149 KB for routes); HEAD returns 403 (expected for Apps Script) |
| Raw GitHub URLs | `raw.githubusercontent.com/Back-on-Track-eu/night-train-data/main/data/latest/*.json` | **VERIFIED** — 200, same data |

### Data contents (verified — fetched and parsed)

| Table | Count | Key fields |
|-------|-------|------------|
| `agencies.json` | 30 operators | `agency_id`, `agency_name`, `agency_url`, `agency_state` |
| `routes.json` | 205 night train lines | `route_id`, `agency_id`, `route_short_name`, `route_desc` (full stop list!), `route_type` (always 2), `is_active`, `origin_trip_0`, `destination_trip_0`, `countries`, `classes`, `source` |
| `stops.json` | 28,785 stops | (GTFS-style: name, lat/lon, station codes) |
| `trips.json` | trip-level detail | |
| `trip_stop.json` | stop sequences + times | |
| `calendar.json` / `calendar_dates.json` | service calendars | |
| `view_ontd_map.json` | pre-processed map data | |

### Coverage (verified from agencies data)

30 operators across 25+ countries including: ÖBB (Nightjet), ČD, HŽPP, CFR, MÁV, PKP,
SJ, VR, Trenitalia, European Sleeper, Caledonian Sleeper, BDŽ, CFM, and more.

Sample routes:
- NJ 468/469: Wien–Bruxelles (ÖBB, countries: BE/DE/AT)
- NJ 408/409: Berlin–Zürich (ÖBB, countries: DE/CH)
- EN 442/443: Humennée–Praha (ČD, countries: CZ/SK)
- 1820/1821: Split–Zagreb (HŽPP, countries: HR)

### Data quality observations

- **GTFS-like structure** — tables mirror GTFS (agencies, routes, stops, trips, stop_times,
  calendar) but are JSON dicts keyed by ID, not CSV.
- `route_desc` contains the **full ordered stop list** as a text string — parseable but
  not machine-friendly. The `trip_stop.json` table is the structured equivalent.
- `is_active` field allows filtering to current services only.
- `classes` field (e.g. "seat, couchette, sleeper") — useful metadata for UI.
- 28,785 stops is surprisingly large — likely includes all station variants/translations.

### License implications

**GPL-3.0 on the data repo is copyleft.** If we incorporate their JSON data files
(even transformed), our derivative work may need to be GPL-3.0 compatible. This is
more restrictive than CC BY 4.0. The Back-on-Track team notes openness to inquiries
about commercial/alternative licensing.

The **CC-BY-NC-ND 4.0** only applies to the visual map product, not the underlying data.

### How it could tag/add night trains

Two integration strategies:

**A. Night-train overlay (supplementary layer):**
- Fetch `routes.json` + `trip_stop.json` + `stops.json`
- Match stops to our existing station data by name/coordinates
- Add a `is_night_train: true` tag to matched connections
- Render with distinct style (dashed lines, different color, 🌙 icon)
- Directly addresses item B (seasonal trains) — calendar data shows run periods

**B. Full GTFS-like ingestion:**
- Convert the JSON tables to our pipeline's expected format
- Would require a custom adapter (not standard GTFS zip)
- Adds routes we don't have from any other feed (domestic night trains in HR, RO, BG, etc.)
- Risk: GPL-3.0 license contamination

### Related resource

`perericr/night-trains-map` on GitHub — Shapefiles (.shp) of actual track geometry for
night train lines (READ-ABOUT). Could provide rail geometry for corridor rendering (item I).

### Difficulty: MEDIUM

The data is excellent and fresh, but: (a) non-standard format requires a custom adapter,
(b) GPL-3.0 license needs careful evaluation, (c) 28K stops need merging against our
existing station data.

> **Recommendation:** Integrate as a supplementary night-train tag layer (strategy A) —
> high value for the "seasonal trains" problem (item B) and night-train visibility.
> Discuss GPL-3.0 implications with user first; consider reaching out to Back-on-Track
> about licensing.

---

## Summary table

| Source | Difficulty | License | Format | Status | Recommendation |
|--------|-----------|---------|--------|--------|----------------|
| FlixTrain GTFS | EASY | ODbL (share-alike) | Standard GTFS zip | ✅ Live, 31.6 MB, HEAD-verified | Integrate — license decision needed |
| Direkt Bahn Guru | N/A | ISC (code) / none (data) | Dead API, no dump | ❌ Archived, API dead | Skip — superseded by our GTFS approach |
| Back On Track | MEDIUM | GPL-3.0 (data) | JSON (GTFS-like tables) | ✅ Active, auto-updated daily | Integrate as night-train overlay — license discussion needed |
