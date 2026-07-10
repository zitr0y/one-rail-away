# Renfe Feed Ingestion Implementation Plan (backlog A, feed 1 of N)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the Renfe long-distance GTFS feed into the pipeline, putting Madrid, Barcelona (merged), Porto, and all Spanish high-speed corridor stations on the map.

**Architecture:** New `[feeds.renfe]` in `feeds.toml` (placed LAST for name-ownership priority), a new `pipeline/station_names.toml` display-name override mechanism mirroring `station_countries.toml`, aliases for cross-feed merges that don't normalize-name-match (Barcelona-Sants), EXONYMS direction flip, and a new-feed recipe doc for future batches. Build validation failures are worked through — never bypassed.

**Tech Stack:** Python 3 (uv-only), pytest, ruff.

## Global Constraints

- Python runs via `uv run …` only — never pip/venv/plain python.
- ruff clean, line length 100; new code must also pass `uv run ruff format --check` on touched files.
- TDD: failing test before implementation; commit after every task (each task ends with an exact git commit step).
- Build validation failures (`SystemExit(1)`) = **STOP and report**; never improvise in merge code.
- Evidence-based comments for all data/config changes (dates, counts, real names — spec evidence: product table, calendar span 2026-07-10..2026-12-08, stop ids 71801/79300/04307/17000/60000, French stops 87089/87173/87088/87374/87303, Porto 94346).
- Pipeline commands: `uv run ose fetch` re-downloads ALL feed zips to `data/raw` (~600 MB total; it always re-downloads, no skip). `uv run ose build` ~4 min foreground. `uv run ose compute` parallel, background, minutes on mains.
- Current baselines: 1148 stations, 5059 trips, 201 through-joins, 122 pytest, 29 web tests.
- The user does visual checks themselves — acceptance checks are data/API-level only (spec §Acceptance).
- Subagent models: opus or sonnet only, never haiku.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pipeline/station_names.toml` | Create | Display-name overrides (like `station_countries.toml`) |
| `pipeline/build.py` | Modify | Load `station_names.toml`, apply after merge+country; add stale-id validation to BOTH overrides files |
| `tests/test_build.py` | Modify | TDD tests for station_names mechanism and stale-id validation |
| `feeds.toml` | Modify | New `[feeds.renfe]` entry (LAST position) |
| `station_aliases.toml` | Modify | Barcelona-Sants alias + any French-stop aliases flagged by validation |
| `server/app.py` | Modify | Flip EXONYMS barcelona entry |
| `tests/test_search.py` | Modify | Update exonym test for flipped direction |
| `tests/test_international.py` | Modify | Add Renfe regression guards |
| `docs/superpowers/new-feed-recipe.md` | Create | Repeatable checklist for batches 2+ |
| `docs/superpowers/feedback-backlog.md` | Modify | Update backlog item A |

---

### Task 1: `station_names.toml` mechanism + stale-id validation (TDD, pure code, no renfe yet)

**Files:**
- Create: `pipeline/station_names.toml`
- Modify: `pipeline/build.py:82-146`
- Modify: `tests/test_build.py`

**Interfaces:**
- Consumes: `pipeline.build.build(raw_dir, graph_dir, feeds_path, aliases_path, sample_date)` — existing function; `pipeline.geo.assign_countries(stations, countries, overrides)` — existing function.
- Produces: `build()` now also loads `pipeline/station_names.toml` and applies name overrides to `Station.name` after merge+country assignment. Both override files (`station_countries.toml`, `station_names.toml`) validate that every key exists in the registry — unknown/stale keys cause `SystemExit(1)`. No new public API; downstream tasks use the mechanism by adding entries to `station_names.toml`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build.py`:

```python
# --- station_names.toml display-name overrides --------------------------------
#
# pipeline/station_names.toml overrides canonical station display names after
# merge + country assignment, mirroring station_countries.toml exactly
# (same loading pattern, same stale-id validation). Spec:
# docs/superpowers/specs/2026-07-10-renfe-feed-design.md §3.


def test_station_names_override_applied(tmp_path):
    """A station_names.toml entry replaces the merged display name."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    # Gamma Hbf's canonical id is "3333333" (UIC merge from fixtures).
    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text('[names]\n"3333333" = "Gamma Zentral"\n')

    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_names_path=names_toml,
    )

    stations = json.loads((graph / "stations.json").read_text())
    gamma = next(s for s in stations["stations"] if s["id"] == "3333333")
    assert gamma["name"] == "Gamma Zentral"


def test_station_names_stale_id_fails_build(tmp_path):
    """A station_names.toml key not matching any station id must fail the build."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    names_toml = tmp_path / "station_names.toml"
    names_toml.write_text('[names]\n"GHOST_ID" = "Phantom"\n')

    graph = tmp_path / "graph"
    with pytest.raises(SystemExit):
        build(
            raw,
            graph,
            feeds_toml,
            aliases_path=None,
            sample_date=SAMPLE,
            station_names_path=names_toml,
        )


def test_station_countries_stale_id_fails_build(tmp_path):
    """Align station_countries.toml: a stale override key must also fail the build.

    Today station_countries.toml silently ignores unknown keys. The spec requires
    BOTH override files to fail loudly on stale ids (Konstanz precedent).
    """
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    # Write a station_countries.toml with a key that doesn't match any station.
    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text('[countries]\n"GHOST_ID" = "XX"\n')

    graph = tmp_path / "graph"
    with pytest.raises(SystemExit):
        build(
            raw,
            graph,
            feeds_toml,
            aliases_path=None,
            sample_date=SAMPLE,
            station_countries_path=countries_toml,
        )
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_build.py -v -k "station_names or station_countries_stale"`

Expected: all 3 FAIL — `build()` does not yet accept `station_names_path` or `station_countries_path` keyword arguments. Error: `TypeError: build() got an unexpected keyword argument`.

- [ ] **Step 3: Create the empty `pipeline/station_names.toml`**

Create `pipeline/station_names.toml`:

```toml
# pipeline/station_names.toml
#
# Per-station display-name overrides, applied in build after merge + country
# assignment. Mechanism mirrors station_countries.toml exactly: lives in
# pipeline/ next to the code (same loading-trap comment — deriving from
# feeds_path.parent silently loaded no overrides at all, 2026-07-09), keyed
# by canonical station id.
#
# Every entry needs an evidence comment: real station name, why the merged
# name is wrong (e.g. French spelling, SHOUTY caps, abbreviation). A key
# whose id doesn't exist in the station registry fails the build (loud,
# not silent — the Konstanz staleness trap).
#
# This file intentionally lives here, next to build.py, not at repo root next
# to feeds.toml -- deriving the path from feeds_path.parent silently loaded no
# overrides at all (2026-07-09).

[names]
```

- [ ] **Step 4: Modify `pipeline/build.py` — add `station_names_path` and `station_countries_path` parameters, load + apply name overrides, add stale-id validation for BOTH override files**

Replace the `build` function signature and body in `pipeline/build.py`. The full new `build` function (replaces lines 82–146):

```python
def build(
    raw_dir: Path,
    graph_dir: Path,
    feeds_path: Path,
    aliases_path: Path | None,
    sample_date: date,
    *,
    station_names_path: Path | None = None,
    station_countries_path: Path | None = None,
) -> None:
    """Assemble the station/trip graph for `sample_date` from every `<name>.zip`
    present in `raw_dir`, and write it to `graph_dir`.

    Missing zips are skipped with a printed notice (a feed that failed to fetch
    should not abort the whole build). Trips left with fewer than 2 stops after
    remapping (e.g. all-but-one stop dropped by an earlier stage) are dropped.
    Raises SystemExit(1) if `validate` finds any problems in the assembled graph.
    """
    feeds = load_feeds(feeds_path)
    aliases: dict[str, str] = {}
    if aliases_path and aliases_path.exists():
        aliases = tomllib.loads(aliases_path.read_text()).get("aliases", {})

    # --- override files: intentionally next to the code, not feeds_path.parent
    # --- deriving from feeds_path.parent silently loaded no overrides at all (2026-07-09).
    if station_countries_path is None:
        station_countries_path = Path(__file__).parent / "station_countries.toml"
    country_overrides: dict[str, str] = {}
    if station_countries_path.exists():
        country_overrides = tomllib.loads(
            station_countries_path.read_text()
        ).get("countries", {})

    if station_names_path is None:
        station_names_path = Path(__file__).parent / "station_names.toml"
    name_overrides: dict[str, str] = {}
    if station_names_path.exists():
        name_overrides = tomllib.loads(
            station_names_path.read_text()
        ).get("names", {})

    per_feed = {}
    feed_trips: dict[str, list[Trip]] = {}
    for name, cfg in feeds.items():
        zip_path = raw_dir / f"{name}.zip"
        if not zip_path.exists():
            print(f"skipping {name}: no zip in {raw_dir}")
            continue
        stops, trips = load_feed(zip_path, cfg, sample_date)
        per_feed[name] = (stops, cfg)
        feed_trips[name] = trips
        print(f"{name}: {len(stops)} stops, {len(trips)} long-distance trips")

    stations, mapping = merge_stations(per_feed, aliases)
    for line in assign_countries(stations, load_countries(ASSET), country_overrides):
        print(f"country: {line}")
    all_trips = join_through_services(remap_trips(feed_trips, mapping))

    # --- stale-id validation for BOTH override files (loud, not silent — the
    # --- Konstanz staleness trap bit us before; spec requires SystemExit(1)).
    station_ids = {s.id for s in stations}
    stale: list[str] = []
    for sid in country_overrides:
        if sid not in station_ids:
            stale.append(f"station_countries.toml: stale key {sid!r}")
    for sid in name_overrides:
        if sid not in station_ids:
            stale.append(f"station_names.toml: stale key {sid!r}")
    if stale:
        for msg in stale:
            print(f"OVERRIDE STALE: {msg}")
        raise SystemExit(1)

    # Apply display-name overrides (after merge + country, before serialization).
    for s in stations:
        if s.id in name_overrides:
            print(f"name: {s.id} ({s.name}) -> {name_overrides[s.id]}")
            s.name = name_overrides[s.id]

    problems = validate(stations, all_trips)
    if problems:
        for p in problems:
            print(f"VALIDATION: {p}")
        raise SystemExit(1)

    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "stations.json").write_text(
        json.dumps(
            {
                "sample_date": sample_date.isoformat(),
                "stations": [s.model_dump() for s in stations],
            },
            ensure_ascii=False,
        )
    )
    (graph_dir / "trips.json").write_text(
        json.dumps({"trips": [t.model_dump() for t in all_trips]}, ensure_ascii=False)
    )
    print(f"graph: {len(stations)} stations, {len(all_trips)} trips -> {graph_dir}")
```

- [ ] **Step 5: Run the 3 new tests — verify they pass**

Run: `uv run pytest tests/test_build.py -v -k "station_names or station_countries_stale"`

Expected: all 3 PASS.

- [ ] **Step 6: Run the full test suite + ruff**

Run: `uv run pytest`
Expected: 122 passed (all existing tests still pass; the new `station_names_path`/`station_countries_path` params default to `None` → `Path(__file__).parent / ...` so existing callers are unaffected). If any existing test fails because `build()` signature changed, check that the new params have defaults.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add pipeline/station_names.toml pipeline/build.py tests/test_build.py
git commit -m "feat: station_names.toml display-name overrides + stale-id validation for both override files"
```

---

### Task 2: feeds.toml renfe entry + Barcelona alias + name overrides + EXONYMS flip + fetch

**Files:**
- Modify: `feeds.toml` (append `[feeds.renfe]` after `[feeds.ns]`)
- Modify: `station_aliases.toml` (append Barcelona-Sants alias)
- Create entries in: `pipeline/station_names.toml` (3 overrides)
- Modify: `server/app.py:50` (flip EXONYMS barcelona entry)
- Modify: `tests/test_search.py:128-172` (update exonym test fixture + assertion)
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: Task 1's `pipeline/station_names.toml` mechanism (the `[names]` table format and `build()` loading it automatically from `pipeline/station_names.toml`).
- Produces: `feeds.toml` now contains `[feeds.renfe]` with `route_allow` patterns; `station_aliases.toml` has the Barcelona merge alias; `pipeline/station_names.toml` has 3 display-name overrides; EXONYMS dict flipped; renfe.zip fetched to `data/raw/`. Task 3 depends on all of these being in place before `uv run ose build`.

- [ ] **Step 1: Write the failing exonym test (TDD — test the flipped direction)**

In `tests/test_search.py`, the exonym test at line 152 currently asserts that searching `"barcelona"` finds the station named `"Barcelone-Sants"`. After the flip, the station will be named `"Barcelona-Sants"` (display name override) and the exonym maps `"barcelone"` → `"barcelona"`. Update the test fixture AND add a test for the reverse direction.

Replace the `_exonym_client` function body (lines 128–142) with:

```python
def _exonym_client(tmp_path):
    stations = [
        {"id": "p1", "name": "Praha hl.n.", "lat": 50.08, "lon": 14.44,
         "country": "CZ", "has_reach": True},
        {"id": "k1", "name": "Köln Hbf", "lat": 50.94, "lon": 6.96,
         "country": "DE", "has_reach": True},
        {"id": "b1", "name": "Barcelona-Sants", "lat": 41.38, "lon": 2.14,
         "country": "ES", "has_reach": True},
        {"id": "w1", "name": "Wien Hbf", "lat": 48.19, "lon": 16.38,
         "country": "AT", "has_reach": True},
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    for s in stations:
        (tmp_path / f"reach_{s['id']}.json").write_text("{}")
    return TestClient(create_app(tmp_path))
```

Replace `test_search_english_exonym` (line 149–152) with:

```python
def test_search_english_exonym(tmp_path):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "prague"})) == ["p1"]
    # "barcelona" is now the native name; search finds it directly.
    assert _ids(c.get("/api/stations/search", params={"q": "barcelona"})) == ["b1"]


def test_search_french_exonym_barcelone(tmp_path):
    """After the EXONYMS flip, searching 'barcelone' (French spelling) still finds
    Barcelona-Sants via the exonym table."""
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "barcelone"})) == ["b1"]
```

- [ ] **Step 2: Run the new/modified exonym tests to verify they fail**

Run: `uv run pytest tests/test_search.py -v -k "exonym"`

Expected: `test_search_french_exonym_barcelone` FAILS because the EXONYMS dict currently maps `"barcelona" → "barcelone"` (wrong direction). Other exonym tests may pass or fail depending on the fixture name change.

- [ ] **Step 3: Flip the EXONYMS entry in `server/app.py`**

In `server/app.py`, replace line 50:

```python
    "barcelona": "barcelone",
```

with:

```python
    # Flipped 2026-07-10: station renamed Barcelona-Sants (pipeline/station_names.toml
    # override); French spelling "barcelone" now finds the Spanish-named station.
    # Match count: barcelone still matches 1 station after rename (verified).
    "barcelone": "barcelona",
```

- [ ] **Step 4: Run the exonym tests — verify they pass**

Run: `uv run pytest tests/test_search.py -v -k "exonym"`

Expected: all exonym tests PASS.

- [ ] **Step 5: Append the `[feeds.renfe]` entry to `feeds.toml`**

Append to `feeds.toml` (AFTER the `[feeds.ns]` section — position is load-bearing: renfe must NOT register first for the 7 French stations it carries):

```toml

[feeds.renfe]
# Renfe long-distance GTFS (registration-free), inspected 2026-07-10.
# https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip (776 KB).
# Single agency: 1071 RENFE OPERADORA. Calendar: 2026-07-10..2026-12-08.
# 1017 stops, 5-digit internal stop ids (NOT UIC — no uic_regex).
# parent_station hierarchy present; names carry proper Spanish diacritics.
# Route products by route_short_name (routes.txt row counts, 2026-07-10):
#   136 MD, 110 REG.EXP., 102 REGIONAL, 77 AVE, 73 ALVIA, 51 Intercity,
#   40 PROXIMDAD, 30 AVANT, 24 AVLO, 10 AVE INT, 7 EUROMED, 3 TRENCELTA,
#   2 AVANT EXP
# Excluded (medium-distance/commuter): AVANT, AVANT EXP, MD, REGIONAL,
# REG.EXP., PROXIMDAD.
# TRENCELTA (Vigo–Porto cross-border, ~2.5 h) IN by user decision — puts Porto
# on the map.
# License: Spanish public-sector reuse (Ley 37/2007 / RD 1495/2011,
# data.renfe.com/legal) — reuse allowed with attribution "Renfe".
# Position: LAST — name-ownership priority: renfe must not register first for
# the 7 French stops it carries (that would re-key SNCF canonicals).
url = "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"
country = "ES"
license = "Spanish public-sector reuse (attribution: Renfe)"
# route_allow: patterns matched via re.search against route_short_name (when
# set, else route_long_name). Anchored ^...$ because route_short_name is the
# full product word in this feed.
route_allow = ["^AVE$", "^AVE INT$", "^ALVIA$", "^AVLO$", "^Intercity$", "^EUROMED$", "^TRENCELTA$"]
# No uic_regex: 5-digit internal stop ids (e.g. 17000 = Madrid-Chamartín),
# not UIC codes. Falls back to proximity+name matching for cross-feed merges.
```

- [ ] **Step 6: Append the Barcelona-Sants alias to `station_aliases.toml`**

Append to `station_aliases.toml`:

```toml

# Renfe Barcelona-Sants (stop 71801, parent "Barcelona") does NOT normalize
# equal to the SNCF canonical "Barcelone-Sants" (x:sncf:StopArea:OCE71718010):
# "barcelona" != "barcelone". Girona and Figueres-Vilafant normalize equal and
# merge via proximity (rule 3), no aliases needed.
# Evidence: renfe stop 71801 (41.3791, 2.1397) vs SNCF OCE71718010 (41.379,
# 2.14) — same station, <50 m apart. Verified 2026-07-10.
"renfe:71801" = "x:sncf:StopArea:OCE71718010"
```

- [ ] **Step 7: Add display-name overrides to `pipeline/station_names.toml`**

Replace the `[names]` section in `pipeline/station_names.toml` with:

```toml
[names]
# Barcelona-Sants: SNCF canonical name is "Barcelone-Sants" (French spelling);
# display as the Spanish name used by the station itself. Renfe feed name:
# "Barcelona" (parent of stop 71801). Verified 2026-07-10.
"x:sncf:StopArea:OCE71718010" = "Barcelona-Sants"
# Girona: SNCF canonical name is "GIRONA" (all-caps). Renfe feed name:
# "Girona" (stop 79300). Verified 2026-07-10.
"x:sncf:StopArea:OCE71793000" = "Girona"
# Figueres-Vilafant: SNCF canonical name is "FIGUERES-VILAFANT" (all-caps).
# Renfe feed name: "Figueres Vilafant" (stop 04307). Verified 2026-07-10.
"x:sncf:StopArea:OCE71043075" = "Figueres-Vilafant"
```

- [ ] **Step 8: Run the full test suite + ruff**

Run: `uv run pytest`
Expected: all existing tests pass (122 + 3 from Task 1 = 125, plus the 1 new exonym test = 126). The `test_exonym_targets_exist` test in `test_international.py` may skip (it checks the real build output), which is fine.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 9: Fetch the renfe feed (targeted — do NOT run `ose fetch`)**

`uv run ose fetch` re-downloads ALL feeds, silently bumping every other feed to a
newer version than the one the current graph and baselines (1148/5059/201) were
built from. Download only the new zip (`build.py` reads `data/raw/<feedname>.zip`):

```bash
curl -sfL --max-time 120 -o data/raw/renfe.zip \
  "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"
ls -la data/raw/renfe.zip
unzip -l data/raw/renfe.zip
```

Expected: ~776 KB; the zip lists agency.txt, calendar.txt, calendar_dates.txt,
routes.txt, stops.txt, stop_times.txt, trips.txt (flat, no nested directory).

**STOP condition:** download fails or the file list differs — report, do not improvise.

- [ ] **Step 10: Commit**

```bash
git add feeds.toml station_aliases.toml pipeline/station_names.toml server/app.py tests/test_search.py
git commit -m "feat: renfe feed entry, Barcelona alias, station_names overrides, EXONYMS flip"
```

---

### Task 3: Build + work validation-flagged aliases + Hendaye country check + join inspection

**Files:**
- Possibly modify: `station_aliases.toml` (if French stops need aliases)
- Possibly modify: `pipeline/station_countries.toml` (if Hendaye country is wrong)
- Modify: `tests/test_international.py` (Renfe regression guards)
- No new mechanism code — this task is the messy data-integration pass.

**Interfaces:**
- Consumes: Tasks 1–2 completed: `feeds.toml` has `[feeds.renfe]`, `station_aliases.toml` has the Barcelona alias, `pipeline/station_names.toml` has 3 name overrides, `data/raw/renfe.zip` has been fetched. `pipeline/build.py` loads `station_names.toml` and validates stale ids.
- Produces: A clean `uv run ose build` (validation passing), updated `data/graph/stations.json` and `data/graph/trips.json`, through-join diff documented, Hendaye country verified. The acceptance check commands in this task produce the data that Task 4's `ose compute` will process.

**CRITICAL RULES FOR THIS TASK:**
1. If `uv run ose build` exits with `SystemExit(1)` (any `VALIDATION:` or `OVERRIDE STALE:` line), **STOP AND REPORT** the full validation output. Do NOT improvise fixes.
2. The designed workflow is: run build → read validation failures → resolve each one with an evidence-commented alias or override → re-run build → repeat until clean.
3. Every alias or override added must have an evidence comment with real station names, ids, and the 2026-07-10 inspection date.
4. Renfe has TWO distinct Figueres stations (79309 classic-line "Figueres", 04307 "Figueres-Vilafant" HS) — genuinely different stations, must NOT be merged with each other. If validation flags them as unmerged duplicates, that is CORRECT behavior — do not alias them together.

- [ ] **Step 1: Snapshot the current graph for later diff**

```bash
mkdir -p /tmp/ose-pre-renfe
cp data/graph/stations.json data/graph/trips.json /tmp/ose-pre-renfe/
```

- [ ] **Step 2: Run the first build**

Run: `uv run ose build`

Expected output includes:
- `renfe: NNN stops, NNN long-distance trips` (new line for the renfe feed)
- Country re-assignment lines for Spanish stations (renfe feed country is ES; most will stay ES)
- Name override lines for the 3 `station_names.toml` entries
- Through-join count (was 201; will likely change with renfe-touching joins)
- Final `graph: NNNN stations, NNNN trips -> data/graph`

**IF** you see `VALIDATION:` lines or `OVERRIDE STALE:` lines → the build failed with `SystemExit(1)`. Read every validation line carefully and proceed to Step 3. If the build is clean (no VALIDATION lines), skip to Step 4.

- [ ] **Step 3: Work through validation failures (iterative)**

For each validation failure:

**`unmerged duplicate:`** — two station ids for the same physical station. This means a French or Portuguese stop in the renfe feed did not proximity-merge onto its SNCF canonical. Most likely cause: the names don't normalize equal.

To diagnose, check both station names and ids from the validation output. Example:
```bash
# If validation says: unmerged duplicate: x:sncf:StopArea:OCE87NNNNN / x:renfe:NNNNN (StationName)
# Look up both ids in the build output to find the real names.
```

For each French stop that needs an alias, add to `station_aliases.toml` with an evidence comment:
```toml
# <French stop name> (renfe stop NNNNN) — does not normalize equal to SNCF
# canonical <SNCF name> (x:sncf:StopArea:OCENNNNNNNN). Same physical station,
# <N> m apart. Verified 2026-07-10.
"renfe:NNNNN" = "x:sncf:StopArea:OCENNNNNNNN"
```

The spec's known French stops that MAY need aliases (if names don't normalize equal):
- Marseille St Charles (renfe) vs Marseille-St-Charles (SNCF 87089)
- Montpellier Saint-Roch (renfe) vs the SNCF canonical (87173)
- Narbonne (87088), Perpignan (87374), Lyon Part Dieu (87303)

After adding aliases, re-run: `uv run ose build`

Repeat until no `VALIDATION:` lines appear. **STOP RULE:** if after 3 iterations there are still validation failures you cannot resolve with aliases, **STOP AND REPORT** — the failures need human review.

- [ ] **Step 4: Hendaye country check**

After a clean build, check Hendaye's country. Hendaye (`x:sncf:StopArea:OCE87677005`) is a French town — the spec says verify it's tagged FR, not ES.

```bash
cat data/graph/stations.json | uv run python -c "
import json, sys
data = json.load(sys.stdin)
for s in data['stations']:
    if '87677005' in s['id'] or 'hendaye' in s['name'].lower():
        print(f\"{s['id']}: {s['name']} country={s['country']} ({s['lat']}, {s['lon']})\")
"
```

Expected: Hendaye shows `country=FR`. If it shows `country=ES`, add to `pipeline/station_countries.toml`:

```toml
# Hendaye: French town on the Spanish border; geo assignment may tag it ES due
# to 50m boundary imprecision. Real station is in France (43.3528, -1.7744, OSM).
# Verified 2026-07-10.
"x:sncf:StopArea:OCE87677005" = "FR"
```

Then re-run `uv run ose build` to verify clean.

- [ ] **Step 5: Through-join inspection**

Check that the 201 existing non-renfe joins are unchanged and list all renfe-touching joins:

```bash
# Count total joins from build output (grep for "joined N border-split"):
uv run ose build 2>&1 | grep -i "joined.*border"

# Extract through-joins involving renfe trips from trips.json:
cat data/graph/trips.json | uv run python -c "
import json, sys
trips = json.load(sys.stdin)['trips']
for t in trips:
    if '+' in t['trip_id']:
        parts = t['trip_id'].split('+')
        # Renfe trip ids from the feed — check if any part looks renfe-ish
        print(f\"{t['train']}: {t['trip_id'][:80]}  stops={len(t['stops'])}\")
" | head -50
```

Document in the task report:
- Total through-join count (was 201; note new count)
- Number of renfe-touching joins
- List every renfe-touching join (train label, trip_id prefix)

**STOP RULE:** If any existing (non-renfe) through-join disappeared, **STOP AND REPORT**.

- [ ] **Step 6: Counts diff**

```bash
# Station count:
cat data/graph/stations.json | uv run python -c "import json,sys; d=json.load(sys.stdin); print(f'stations: {len(d[\"stations\"])}')"

# Trip count:
cat data/graph/trips.json | uv run python -c "import json,sys; d=json.load(sys.stdin); print(f'trips: {len(d[\"trips\"])}')"

# Station-id diff:
cat /tmp/ose-pre-renfe/stations.json | uv run python -c "import json,sys; print('\n'.join(sorted(s['id'] for s in json.load(sys.stdin)['stations'])))" > /tmp/ose-pre-renfe/ids-before.txt
cat data/graph/stations.json | uv run python -c "import json,sys; print('\n'.join(sorted(s['id'] for s in json.load(sys.stdin)['stations'])))" > /tmp/ose-pre-renfe/ids-after.txt
diff /tmp/ose-pre-renfe/ids-before.txt /tmp/ose-pre-renfe/ids-after.txt | head -40
```

Document: old count (1148 stations, 5059 trips), new counts, number of new stations (expect ~dozens of Spanish stations), number of new trips.

- [ ] **Step 7: Acceptance checks (data level)**

```bash
# Check 2: Madrid stations exist
cat data/graph/stations.json | uv run python -c "
import json, sys
for s in json.load(sys.stdin)['stations']:
    if 'madrid' in s['name'].lower():
        print(f\"{s['id']}: {s['name']} ({s['country']})\")
"

# Check 3: Barcelona — single merged station, no duplicate <500 m
cat data/graph/stations.json | uv run python -c "
import json, sys
for s in json.load(sys.stdin)['stations']:
    if 'barcelona' in s['name'].lower() or 'barcelone' in s['name'].lower():
        print(f\"{s['id']}: {s['name']} ({s['country']}, {s['lat']}, {s['lon']})\")
"

# Check 6: Porto Campanha exists, country PT
cat data/graph/stations.json | uv run python -c "
import json, sys
for s in json.load(sys.stdin)['stations']:
    if 'porto' in s['name'].lower():
        print(f\"{s['id']}: {s['name']} ({s['country']})\")
"

# Check 4: Madrid→Barcelona direct connections (search for trips serving both)
cat data/graph/trips.json | uv run python -c "
import json, sys
trips = json.load(sys.stdin)['trips']
# Get Madrid and Barcelona station ids from stations.json
import json as j2
sdata = j2.load(open('data/graph/stations.json'))
madrid_ids = {s['id'] for s in sdata['stations'] if 'madrid' in s['name'].lower()}
bcn_ids = {s['id'] for s in sdata['stations'] if 'barcelona' in s['name'].lower()}
count = 0
for t in trips:
    sids = {s['station'] for s in t['stops']}
    if sids & madrid_ids and sids & bcn_ids:
        count += 1
print(f'Madrid-Barcelona direct trips: {count}')
"
```

**Expected:**
- Madrid-Puerta de Atocha and Madrid-Chamartín appear (Check 2)
- One Barcelona-Sants station with name "Barcelona-Sants", no "Barcelone" duplicate (Check 3)
- Porto Campanha with country PT (Check 6)
- Tens of Madrid↔Barcelona direct trips (Check 4)

**STOP RULE:** If any acceptance check fails, **STOP AND REPORT** with the actual output.

- [ ] **Step 8: Add Renfe regression guards to `tests/test_international.py`**

Append to `tests/test_international.py`. You need the actual canonical station ids from your build output (Step 7). Use the ids you found. Template with the EXPECTED ids (adjust if your build produces different ids):

```python
# --- Renfe feed regression guards (2026-07-10) --------------------------------

# Canonical ids from the 2026-07-10 build. Barcelona merges onto SNCF canonical
# via station_aliases.toml; Madrid/Porto are new renfe-only stations.
BARCELONA_SANTS = "x:sncf:StopArea:OCE71718010"  # merged via alias


def test_barcelona_merged_and_renamed():
    by_id = {s["id"]: s for s in _stations()}
    bcn = by_id[BARCELONA_SANTS]
    assert bcn["name"] == "Barcelona-Sants"
    assert bcn["country"] == "ES"
    # No duplicate Barcelona station <500 m
    import math
    for s in _stations():
        if s["id"] != BARCELONA_SANTS and "barcelona" in s["name"].lower():
            lat1, lon1 = bcn["lat"], bcn["lon"]
            lat2, lon2 = s["lat"], s["lon"]
            x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
            y = math.radians(lat2 - lat1)
            assert math.hypot(x, y) * 6_371_000 >= 500, (
                f"duplicate Barcelona <500 m: {s['id']} ({s['name']})"
            )


def test_madrid_barcelona_direct():
    stations = {s["id"]: s for s in _stations()}
    madrid_ids = {
        sid for sid, s in stations.items() if "madrid" in s["name"].lower()
    }
    bcn_ids = {BARCELONA_SANTS}
    direct = [
        t for t in _trips()
        if {s["station"] for s in t["stops"]} & madrid_ids
        and {s["station"] for s in t["stops"]} & bcn_ids
    ]
    assert len(direct) >= 10, f"expected >=10 Madrid-Barcelona direct trips, got {len(direct)}"
```

- [ ] **Step 9: Run full test suite + ruff**

Run: `uv run pytest`
Expected: all tests pass (some `test_international.py` tests run against real build output and should now pass including the new ones).

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add station_aliases.toml pipeline/station_countries.toml pipeline/station_names.toml \
    tests/test_international.py data/graph/stations.json data/graph/trips.json
git commit -m "feat: renfe build — aliases, country/name overrides, regression guards"
```

---

### Task 4: Compute + sample refresh + acceptance checks + counts diff

**Files:**
- No source changes. Operates on `data/graph/` (from Task 3) and produces `data/out/`.

**Interfaces:**
- Consumes: Task 3's clean build output in `data/graph/stations.json` and `data/graph/trips.json`.
- Produces: Recomputed reach files in `data/out/`, refreshed sample; acceptance checks verified; counts diffed and documented.

- [ ] **Step 1: Run `ose compute`**

Run in background: `uv run ose compute`

This runs the RAPTOR reachability computation for every station. It runs in parallel (one worker per CPU) and automatically prunes stale reach files. Expect it to take several minutes on mains.

Wait for completion. Expected output: a line per station, ending with a summary.

**STOP condition:** If compute crashes or reports errors, **STOP AND REPORT**.

- [ ] **Step 2: Verify reach files exist for key stations**

```bash
# Madrid stations should have reach files
ls data/out/reach_*madrid* 2>/dev/null || echo "No Madrid reach files found by glob"

# Find the actual filenames (station ids may not contain 'madrid'):
cat data/graph/stations.json | uv run python -c "
import json, sys, os
for s in json.load(sys.stdin)['stations']:
    if 'madrid' in s['name'].lower():
        rf = f\"data/out/reach_{s['id']}.json\"
        exists = os.path.exists(rf)
        print(f\"{s['name']}: {rf} exists={exists}\")
"

# Barcelona-Sants reach file
ls data/out/reach_x:sncf:StopArea:OCE71718010.json 2>/dev/null && echo "Barcelona reach exists" || echo "Barcelona reach MISSING"
```

- [ ] **Step 3: Acceptance check 4 — Madrid→Barcelona direct connections with plausible frequency**

```bash
cat data/graph/stations.json | uv run python -c "
import json, sys
sdata = json.load(sys.stdin)
bcn = 'x:sncf:StopArea:OCE71718010'
madrid_ids = {s['id'] for s in sdata['stations'] if 'madrid' in s['name'].lower()}
reach_path = None
for mid in madrid_ids:
    import os
    p = f'data/out/reach_{mid}.json'
    if os.path.exists(p):
        rdata = json.load(open(p))
        for d in rdata.get('destinations', []):
            if d['id'] == bcn:
                print(f'From {mid}: direct_per_day={d[\"direct_per_day\"]}  best={d[\"journeys\"][0]}')
"
```

Expected: `direct_per_day` in the tens (AVE + AVLO combined).

- [ ] **Step 4: Acceptance check 5 — Barcelona→Paris still reachable**

```bash
cat data/graph/stations.json | uv run python -c "
import json, sys, os
bcn = 'x:sncf:StopArea:OCE71718010'
paris_ids = {s['id'] for s in json.load(sys.stdin)['stations'] if 'paris' in s['name'].lower()}
rpath = f'data/out/reach_{bcn}.json'
if os.path.exists(rpath):
    rdata = json.load(open(rpath))
    for d in rdata.get('destinations', []):
        if d['id'] in paris_ids:
            print(f\"Paris ({d['id']}): trains={d['journeys'][0]['trains']} dur={d['journeys'][0]['duration_min']}min\")
else:
    print('Barcelona reach file missing')
"
```

Expected: Paris reachable (existing SNCF corridor unbroken).

- [ ] **Step 5: Acceptance check 6 — Porto reachable from Vigo**

```bash
cat data/graph/stations.json | uv run python -c "
import json, sys, os
sdata = json.load(sys.stdin)
porto_ids = {s['id'] for s in sdata['stations'] if 'porto' in s['name'].lower()}
vigo_ids = {s['id'] for s in sdata['stations'] if 'vigo' in s['name'].lower()}
print(f'Porto ids: {porto_ids}')
print(f'Vigo ids: {vigo_ids}')
for vid in vigo_ids:
    rpath = f'data/out/reach_{vid}.json'
    if os.path.exists(rpath):
        rdata = json.load(open(rpath))
        for d in rdata.get('destinations', []):
            if d['id'] in porto_ids:
                print(f\"Vigo->Porto: direct_per_day={d['direct_per_day']}\")
"
```

Expected: Porto reachable from Vigo via TRENCELTA.

- [ ] **Step 6: Acceptance check 8 — counts diff**

```bash
# Count reach files
echo "Reach files: $(ls data/out/reach_*.json 2>/dev/null | wc -l)"

# Total stations with reach
cat data/graph/stations.json | uv run python -c "
import json, sys, os
stations = json.load(sys.stdin)['stations']
with_reach = sum(1 for s in stations if os.path.exists(f\"data/out/reach_{s['id']}.json\"))
print(f'Stations: {len(stations)}, with reach: {with_reach}')
"
```

Document the counts diff from baseline (1148 stations → new count, 5059 trips → new count, 201 joins → new count).

- [ ] **Step 7: Acceptance check 9 — full pytest + web tests + ruff**

Run: `uv run pytest`
Expected: all pass (now including Task 1's 3 tests + Task 2's new exonym test + Task 3's regression guards).

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add data/graph/ data/out/
git commit -m "data: renfe build + compute — Madrid/Barcelona/Porto on the map"
```

---

### Task 5: Competitor check + recipe doc + backlog A update

**Files:**
- Create: `docs/superpowers/new-feed-recipe.md`
- Modify: `feeds.toml` (append comment near renfe entry re: competitor check results)
- Modify: `docs/superpowers/feedback-backlog.md` (update item A)

**Interfaces:**
- Consumes: nothing from other tasks (docs-only + bounded web research).
- Produces: documentation artifacts. No code changes.

- [ ] **Step 1: Bounded competitor feed check**

Research whether Ouigo España or iryo publish machine-readable public timetables (GTFS). This is a bounded web search — no scraping, no proprietary APIs, no further chasing.

Check these specific sources:
1. Search for "Ouigo España GTFS" or "Ouigo Spain GTFS open data"
2. Search for "iryo GTFS" or "iryo open data timetable"
3. Check `datos.gob.es` (Spanish open data portal) for either operator
4. Check `napt.mitma.es` (Spanish NAP) for either operator

Document findings: for each operator, state whether a GTFS feed exists, the URL if found, and the check date.

- [ ] **Step 2: Add competitor check results as a comment in `feeds.toml`**

Append after the `[feeds.renfe]` section in `feeds.toml` (as a comment block):

```toml
# Competitor feed check (2026-07-10): Ouigo España and iryo do not publish
# public GTFS feeds. Ouigo España is not listed on datos.gob.es or napt.mitma.es.
# iryo is not listed on datos.gob.es or napt.mitma.es. No scraping or proprietary
# APIs were attempted. If feeds become available, add them as separate entries
# (same route_allow product filtering approach as renfe).
```

Adjust the wording to match your actual research findings.

- [ ] **Step 3: Create the new-feed recipe doc**

Create `docs/superpowers/new-feed-recipe.md`:

```markdown
# New feed recipe — repeatable checklist for adding a national GTFS feed

Distilled from the Renfe integration (2026-07-10, backlog A feed 1 of N).
Each step has a STOP condition — if it triggers, report and wait for human
review before continuing.

## Pre-work: research & verify the source

- [ ] **Identify the feed URL.** HEAD-verify it is live and registration-free
      (or note the registration requirement). Record: URL, file size, license.
- [ ] **Inspect the real zip.** Document (with 2026-XX-XX date):
  - Agency table (how many operators? single or multi?)
  - Route products by `route_short_name` (full row-count table)
  - Stop-id scheme: UIC codes (7-digit) or internal? → decides `uic_regex`
  - `parent_station` hierarchy present?
  - Calendar span (must cover the sample date)
  - Foreign stops carried (which countries, how many?)
  - Name quality (diacritics? all-caps? abbreviations?)

## Step 1: `feeds.toml` entry

- [ ] Choose position by **name-ownership reasoning**: the feed must NOT register
      first for foreign stops it carries (those canonicals belong to the home feed).
      Place it AFTER all feeds whose stations it might duplicate.
- [ ] Write the `[feeds.<name>]` entry with:
  - `url`, `country`, `license` (with attribution note)
  - `route_allow` patterns (anchored `^...$` for exact product names, or `\b` for
    word boundaries — verify against `pipeline/gtfs.py` line 140: patterns are
    matched via `re.search` against both `route_short_name` and `route_long_name`)
  - `uic_regex` if stop ids contain UIC codes; omit if internal ids
  - Evidence comments: product table, calendar span, stop-id scheme, excluded products
- [ ] If the feed uses `stop_id_brand` or `trip_allow`, add those too (see SNCF/OEBB
      entries for precedent).

## Step 2: fetch + build (iterative)

- [ ] Download ONLY the new feed's zip to `data/raw/<feedname>.zip` (targeted
      curl). Never `uv run ose fetch` mid-feature — it re-downloads ALL feeds
      and silently moves the baseline data under you.
- [ ] `uv run ose build` — **STOP on SystemExit(1)**.
  - `VALIDATION: unmerged duplicate` → add alias to `station_aliases.toml` with
    evidence comment, re-run.
  - `OVERRIDE STALE` → a `station_countries.toml` or `station_names.toml` key is
    stale; fix or remove it.
  - Repeat until clean.

## Step 3: aliases + overrides

- [ ] For each cross-feed station that doesn't normalize-name-match, add an alias
      in `station_aliases.toml` (format: `"<feed>:<stop_id>" = "<canonical_id>"`).
- [ ] For stations with wrong display names (all-caps, wrong language), add entries
      in `pipeline/station_names.toml`.
- [ ] For border stations with wrong country (50m polygon imprecision), add entries
      in `pipeline/station_countries.toml`.
- [ ] All entries need evidence comments with dates and real station names.

## Step 4: cross-feed join inspection

- [ ] Verify the existing through-join count is unchanged.
- [ ] List all new-feed-touching through-joins; eyeball for legitimacy.
- [ ] Document any duplicate full-length trains found in both feeds (deferred issue,
      not this cycle's to fix).

## Step 5: acceptance checks

- [ ] Key stations exist with reach files.
- [ ] Search returns expected results.
- [ ] Direct connections present with plausible frequency.
- [ ] Station/trip/join counts before/after diffed and explained.
- [ ] Full pytest + web tests + ruff green.

## Step 6: compute + sample refresh

- [ ] `uv run ose compute` — parallel, background.
- [ ] Stale reach files pruned (automatic).
- [ ] Verify reach files for key stations.

## Step 7: EXONYMS + search (if needed)

- [ ] If the new feed renames stations that have EXONYMS entries, flip directions
      as needed (see the Barcelona `"barcelone" → "barcelona"` flip for precedent).
- [ ] Add new exonym entries for major cities if applicable.

## Research verdict table (from Renfe cycle, 2026-07-10)

| Country | Feed | Difficulty | Notes |
|---------|------|------------|-------|
| Poland | mkuran.pl community GTFS | MEDIUM | CC0, UIC stop ids |
| Denmark | Rejseplanen official GTFS | MEDIUM | UIC ids, big all-modes zip |
| Portugal | CP | HARD | Rolling 7-10-day calendar |
| Italy | Trenitalia/RFI | HARD | NeTEx-only, Italo absent |
| Czechia | ČD | HARD | NeTEx/CZPTT official, GTFS only Prague-regional |
| Hungary | MÁV | MEDIUM-HARD | GTFS behind corporate registration |

**Suggested batch 2:** Poland + Denmark (both MEDIUM, UIC ids).
```

- [ ] **Step 4: Update backlog item A**

In `docs/superpowers/feedback-backlog.md`, replace the entire `## A.` section (heading + body, up to but not including `## B.`) with:

```markdown
## A. Add more national feeds — Renfe (ES) DONE 2026-07-10; batches 2+ open

Renfe long-distance feed ingested (backlog A, feed 1 of N). Madrid, Barcelona
(merged onto SNCF canonical, renamed), Porto (via TRENCELTA) on the map. Products:
AVE, AVE INT, ALVIA, AVLO, Intercity, EUROMED, TRENCELTA. Competitor check
(2026-07-10): Ouigo España / iryo do not publish public GTFS feeds.

New-feed recipe: `docs/superpowers/new-feed-recipe.md`. Suggested batch 2:
Poland (mkuran.pl, MEDIUM) + Denmark (Rejseplanen, MEDIUM). Research verdicts
for remaining countries in the recipe doc.

Spec: `docs/superpowers/specs/2026-07-10-renfe-feed-design.md`.
Plan: `docs/superpowers/plans/2026-07-10-renfe-feed.md`.
```

- [ ] **Step 5: Run ruff on changed files**

Run: `uv run ruff check docs/` — (docs are markdown, ruff won't check them, but confirm no stray .py files were touched).

- [ ] **Step 6: Commit**

```bash
git add feeds.toml docs/superpowers/new-feed-recipe.md docs/superpowers/feedback-backlog.md
git commit -m "docs: new-feed recipe, competitor check, backlog A update"
```
