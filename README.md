# onestopeurope

> nonstopeurope with onestopeurope

Pick a European station. See every station you can reach with at most one, two,
or three trains — colored by travel time — and click through to book.

## Quickstart

    uv sync && (cd web && npm install)
    just dev          # API on :8000, web on :5173 (sample data included)

## Refresh the data

    just pipeline     # fetch GTFS feeds -> build graph -> compute reachability

Runs weekly by hand for now. Feeds are declared in `feeds.toml`; station-merge
overrides live in `station_aliases.toml`.

Current coverage (2026-07 run): DE (gtfs.de long-distance), FR (SNCF
TGV/OUIGO/Intercités/Lyria), AT (ÖBB), CH (SBB), NL (NS/ovapi) — about 1,050
merged stations and 4,100 trips per sample day.

## How it works

- `pipeline/` downloads national long-distance GTFS feeds, merges stations
  across feeds (UIC codes, proximity + normalized names, aliases), and runs a
  RAPTOR search (max 3 trains, 10-min minimum transfer) independently for eight
  deterministic probes: Tuesday + Saturday in January, April, July, and October.
  The best sampled route is retained and reach JSON reports cautious availability
  evidence only for probes covered by every GTFS feed used by that route; "per
  week" is a rounded direct-service sample estimate, not a timetable promise.
- `server/` is a thin FastAPI that serves the precomputed JSON in `data/out/`.
- `web/` is Vite + React + MapLibre GL (OpenFreeMap tiles).

## Development

    just test         # Python tests
    (cd web && npm test)
    just lint

VS Code: "Full stack" launch config debugs API + browser together.

Design docs: `docs/superpowers/specs/`, plans: `docs/superpowers/plans/`.
