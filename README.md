# onestopeurope

> nonstopeurope with onestopeurope

Pick a European station. See every station you can reach with at most one, two,
or three trains — colored by travel time — and click through to book.

## Quickstart

    uv sync && (cd web && npm install)
    just dev          # API on :8000, web on :5173 (sample data included)

## Refresh the data

    just pipeline     # fetch -> build graph -> compute reachability -> rail geometry

Runs weekly via cron on the production host (fetch → build → compute; see
`docs/superpowers/feedback-backlog.md` item AL for why `ose paths` runs on a
workstation instead). Feeds are declared in `feeds.toml`; station-merge
overrides live in `station_aliases.toml`. Everything lands in `data/out/`, which is
gitignored apart from a handful of committed sample files — **a fresh clone has only
those samples, so a host must run this pipeline** (or be given a populated
`data/out/`) before the site shows real data.

The last stage, `uv run ose paths`, derives real railway geometry from
OpenStreetMap so reach lines follow actual track. On a **first** run it needs:

- **~35–45 min** wall time, dominated by downloading ~24 GB of Geofabrik extracts
- **~6 GB free disk**, not 24 GB: each country's extract is downloaded, filtered to
  rail-only, and deleted before the next one, so only the largest single extract
  (France, ~5 GB) is ever on disk at once. What persists is a ~100 MB rail-only
  cache in `data/osm/`.
- **~8 GB RAM** (peak RSS ~5.9 GB while routing the European rail graph)

Later runs reuse the `data/osm/` cache and take a few minutes. Without this stage
the site still works — reach lines just fall back to straight lines between stations.

Current coverage (2026-07 run): DE (gtfs.de long-distance + FlixTrain), FR (SNCF),
AT (ÖBB), CH (SBB), NL (NS/ovapi), DK (Rejseplanen), PT (CP), IT (Trenitalia),
ES (Renfe), PL (PKP). Neighbouring countries appear only where an international
train reaches them. Full inventory and known gaps: [`docs/data-sources.md`](docs/data-sources.md).

## How it works

- `pipeline/` downloads national long-distance GTFS feeds, merges stations
  across feeds (UIC codes, proximity + normalized names, aliases), and runs a
  RAPTOR search (max 3 trains, 10-min minimum transfer) independently for each
  day of one deterministic consecutive service week per feed, chosen inside that
  feed's published calendar horizon. The best sampled route is retained and reach
  JSON reports cautious availability evidence only for days covered by every GTFS
  feed used by that route; "per week" is a rounded direct-service sample
  estimate, not a timetable promise. Services absent from the selected week are
  still retained so destinations only they serve stay on the map, without
  counting toward sampled-week frequency.
- `server/` is a thin FastAPI that serves the precomputed JSON in `data/out/`.
- `web/` is Vite + React + MapLibre GL (OpenFreeMap tiles).

## Development

    just test         # Python tests
    (cd web && npm test)
    just lint

VS Code: "Full stack" launch config debugs API + browser together.

**What data we use — and what we still want:** [`docs/data-sources.md`](docs/data-sources.md).

Design docs: `docs/superpowers/specs/`, plans: `docs/superpowers/plans/`.
