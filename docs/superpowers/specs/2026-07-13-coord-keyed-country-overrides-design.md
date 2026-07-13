# Coordinate-keyed country overrides

**Date:** 2026-07-13
**Status:** Approved, ready for implementation plan

## Problem

`pipeline/station_countries.toml` keys per-station country overrides on canonical
station ids. Those ids are feed-derived and churn between GTFS snapshots:

- `8014586` (Konstanz Hbf) has churned twice — once documented in the toml comment
  (`x:db_fern:185018 -> 8014586` after the 2026-07-10 alias merge), and again in
  feeds fetched 2026-07-13.
- `x:db_fern:391436` (Weil am Rhein) is the `x:<feed>:<stop_id>` fresh-id fallback;
  the db_fern internal id no longer exists in the current feed.

Each churn makes the override key "stale", and `pipeline/build.py:151-154` responds
with `raise SystemExit(1)`, taking down the entire weekly refresh. A stale country
override is not user-visible wrongness — it is a geographic hint that no longer
matches a station — so a hard abort is too costly. (A stale *name* override is
different: it produces a visibly wrong station name, so it keeps its hard abort.)

Root cause: overrides are keyed on an unstable identifier. Coordinates of a real
station are stable across snapshots even when its feed-derived id changes.

## Fix

Key country overrides on geographic coordinates. Match each override to the nearest
station within a fixed radius. An override that matches no station warns and the
build proceeds.

### 1. TOML schema — array of tables

`pipeline/station_countries.toml` changes from an id-keyed `[countries]` table to a
list of `[[override]]` tables:

```toml
[[override]]
name    = "Konstanz Hbf"   # human label only; NOT used for matching
lat     = 47.65874
lon     = 9.177333
country = "DE"
# evidence: town straddles the Bodensee shoreline at the DE/CH border; the 50m
# Natural Earth polygon match flips the station DE -> CH. Feed coords are ~284m
# from Konstanz Hbf's real OSM position (47.6612, 9.1763) -- the station is in DE.
```

- `lat`/`lon` are the station's **feed coordinates** (the values already recorded
  in each override's evidence comment), NOT the OSM "real" position. We match
  against what the feed emits.
- All 5 existing overrides migrate 1:1, preserving their evidence comments:
  Konstanz Hbf, Weil am Rhein, Venezia Santa Lucia, Hendaye, Viana do Castelo.
- `name` is a human label for readability and log messages only; it is never used
  for matching.

### 2. New model — `pipeline/models.py`

```python
class CountryOverride(BaseModel):
    name: str
    lat: float
    lon: float
    country: str
```

### 3. Matching — `pipeline/geo.py`

`assign_countries` signature changes:

```
overrides: dict[str, str]  ->  overrides: list[CountryOverride]
```

New module constant:

```python
OVERRIDE_RADIUS_M = 500  # comfortably above coord jitter, below border-station spacing
```

Algorithm, per override:

1. Compute haversine distance from the override coord to every station.
2. Find the nearest station.
3. If the nearest is within `OVERRIDE_RADIUS_M`, set that station's country to the
   override's `country` (override still wins over the polygon lookup). Emit the same
   `id (name): OLD -> NEW` change-log line as today.
4. If the nearest is beyond the radius (or there are zero stations), emit a warning
   line — `unused override 'Konstanz Hbf' (47.6..): no station within 500m` — and
   continue. No abort.
5. Ambiguity guard: if more than one station falls within the radius, emit a warning
   naming the candidates and assign the nearest. Curated border data should not
   trigger this, but we surface it rather than silently pick.

Polygon assignment for non-overridden stations is unchanged. The returned
change-log list now also carries the warning lines.

A small haversine helper lives in `geo.py` (pure Python, consistent with the
existing dependency-light point-in-polygon code).

### 4. `pipeline/build.py` stale block

- Load the new schema: `tomllib.loads(...).get("override", [])` -> list of
  `CountryOverride`.
- Remove `country_overrides` from the stale-abort loop (lines 145-147). Staleness
  is now surfaced as a warning by `assign_countries`.
- **Keep** the `SystemExit(1)` for stale `station_names.toml` keys (still id-keyed;
  a wrong display name is user-visible and worth blocking).

### 5. Tests (TDD — write first)

`tests/test_geo.py`:
- Rewrite `test_assign_countries_override_wins` to use a coord-keyed
  `CountryOverride` instead of `{"a": "CH"}`.
- Add: override within radius assigns country.
- Add: override with no station within radius warns and does not raise; other
  stations still get polygon countries.
- Add: two stations within radius -> ambiguity warning, nearest wins.

`tests/test_build.py`:
- Replace `test_station_countries_stale_id_fails_build` with
  `test_station_countries_unmatched_override_warns_not_aborts` (build completes,
  warning present in output).
- Keep `test_station_names_stale_id_fails_build` unchanged (name overrides still
  hard-abort).
- Update `empty_overrides` fixture if it writes a `[countries]` table, so it emits
  the new `[[override]]`-less (empty) shape.

## Out of scope

Per the approved "durable fix only" decision:

- Re-fetching db_fern or chasing this week's Konstanz/Weil ids.
- A `--allow-stale` CLI flag.
- UIC-code keying (coord proximity covers both Konstanz *and* Weil am Rhein, whereas
  UIC keying would not cover Weil am Rhein, which has no UIC code).

## Verification

- `pytest tests/test_geo.py tests/test_build.py` passes.
- A local `ose build` against the Jul-7 `db_fern.zip` completes and logs the five
  overrides as coordinate matches (they resolve today), with no stale abort.
- Server unblock path is unchanged: `git pull && ~/run-trains-pipeline.sh`.
