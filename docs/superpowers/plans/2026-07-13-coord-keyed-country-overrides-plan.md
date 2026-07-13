# Coordinate-Keyed Country Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unstable station-id country overrides with coordinate-keyed overrides that match the nearest canonical station within 500 metres, warn without aborting when unused or ambiguous, and retain hard failures for stale display-name ids.

**Architecture:** Parse `[[override]]` TOML entries into a new Pydantic `CountryOverride` model. `pipeline.geo.assign_countries()` first matches each override to the nearest station with a pure-Python haversine calculation, records warning/change lines, and then runs the existing polygon assignment only for stations that were not overridden. `pipeline.build.build()` passes the typed list through and validates stale ids only in `station_names.toml`.

**Tech Stack:** Python 3.14, Pydantic 2, stdlib `math`/`tomllib`, pytest, uv, Ruff.

## Global Constraints

- Follow TDD in the order written: edit the named test first, observe the expected failure, then add only the implementation needed for that test batch.
- Use `CountryOverride(name: str, lat: float, lon: float, country: str)` exactly; `name` is for readability and warnings only and must never participate in matching.
- Use `OVERRIDE_RADIUS_M = 500` exactly and a pure-Python haversine helper in `pipeline/geo.py`; do not add a dependency or reuse name matching.
- A match at or inside 500 metres wins over polygon lookup. More than one candidate warns and the nearest wins. No candidate warns and processing continues.
- Every matched override emits the existing `id (name): OLD -> NEW` line, including an already-correct `OLD == NEW` match, so all five curated coordinate matches are auditable in the required local-build check. Non-overridden polygon behavior and its line format remain unchanged.
- Remove country overrides from stale-id abort handling. Keep `SystemExit(1)` for stale `station_names.toml` keys.
- Migrate exactly five production entries and preserve every existing per-station evidence comment. The current Viana do Castelo comment is the one repository/spec inconsistency: it does not contain coordinates, so use the checked-in Renfe feed coordinates `41.69517, -8.83134` and add that fact to its evidence comment.
- Do not fetch new feeds, chase current station ids, add `--allow-stale`, or introduce UIC matching.
- Preserve the user's unrelated existing modification to `web/public/favicon.svg`; stage only files listed by the current task.

## File Map

| File | Responsibility in this change |
|---|---|
| `pipeline/models.py` | Defines the typed `CountryOverride` record. |
| `pipeline/geo.py` | Calculates haversine distance, matches overrides, emits warnings, and preserves polygon assignment for non-overridden stations. |
| `pipeline/build.py` | Parses the new TOML shape and retains only name-override stale-id aborts. |
| `pipeline/station_countries.toml` | Holds the five coordinate-keyed production overrides and their evidence. |
| `tests/test_geo.py` | Unit coverage for override precedence, radius matching, unused warnings, ambiguity, and unchanged polygon behavior. |
| `tests/test_build.py` | Build-level coverage for the new schema, warn-without-abort behavior, and retained name-id abort behavior. |

---

### Task 1: Add the typed override and coordinate matcher

**Files:**
- Modify: `tests/test_geo.py:1-83`
- Modify: `pipeline/models.py:1-15`
- Modify: `pipeline/geo.py:21-87`

**Interfaces:**
- Consumes: Existing `Station`, `country_at(lat, lon, countries)`, and the current change-log convention `id (name): OLD -> NEW`.
- Produces: `CountryOverride(name: str, lat: float, lon: float, country: str)`, `OVERRIDE_RADIUS_M = 500`, `_haversine_m(lat1, lon1, lat2, lon2) -> float`, and `assign_countries(stations, countries, overrides: list[CountryOverride]) -> list[str]`.

- [ ] **Step 1: Write the failing coordinate-override tests first**

In `tests/test_geo.py`, change the model import to:

```python
from pipeline.models import CountryOverride, Station
```

Change the empty override argument in `test_assign_countries_corrects_and_logs` and `test_assign_countries_no_match_keeps_feed_country` from `{}` to `[]`. Replace `test_assign_countries_override_wins` and append the three new tests with this exact block:

```python
def test_assign_countries_override_wins(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")
    override = CountryOverride(name="A border override", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "CH"
    assert changes == ["a (a): DE -> CH"]


def test_assign_countries_override_matches_station_within_radius(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.001, 12.0, "DE")  # about 111m north of the override
    override = CountryOverride(name="Nearby override", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "CH"
    assert changes == ["a (a): DE -> CH"]


def test_assign_countries_unmatched_override_warns_and_continues(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")  # polygon lookup must still change it to FR
    override = CountryOverride(name="Nowhere", lat=50.0, lon=50.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "FR"
    assert changes == [
        "unused override 'Nowhere' (50.000000, 50.000000): no station within 500m",
        "a (a): DE -> FR",
    ]


def test_assign_countries_ambiguous_override_warns_and_nearest_wins():
    near = _station("near", 2.0002, 12.0, "DE")
    far = _station("far", 2.001, 12.0, "DE")
    override = CountryOverride(name="Border", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([near, far], [], [override])
    assert near.country == "CH"
    assert far.country == "DE"
    assert changes[0] == (
        "ambiguous override 'Border' (2.000000, 12.000000): 2 stations within 500m "
        "(near (near), far (far)); using near (near)"
    )
    assert changes[1] == "near (near): DE -> CH"
```

Leave the existing point-in-polygon assertions and the final `"no polygon match"` assertion unchanged.

- [ ] **Step 2: Run the geo tests and confirm the new model is missing**

Run:

```bash
uv run pytest tests/test_geo.py -q
```

Expected: collection fails with `ImportError: cannot import name 'CountryOverride' from 'pipeline.models'`. This is the intentional first RED state.

- [ ] **Step 3: Add the minimal Pydantic model**

In `pipeline/models.py`, insert this immediately before `Station`:

```python
class CountryOverride(BaseModel):
    name: str
    lat: float
    lon: float
    country: str


```

Do not add validators or aliases; the approved schema needs only Pydantic's normal type validation.

- [ ] **Step 4: Run the geo tests again and confirm matching is still unimplemented**

Run:

```bash
uv run pytest tests/test_geo.py -q
```

Expected: the tests now collect, but `assign_countries()` fails because the current implementation calls `.get()` on the new override list (typically `AttributeError: 'list' object has no attribute 'get'`). This is the second RED state.

- [ ] **Step 5: Implement haversine matching and preserve the polygon path**

In `pipeline/geo.py`, add `import math` with the stdlib imports, change the model import to:

```python
from pipeline.models import CountryOverride, Station
```

Add the radius beside `ASSET`, then replace `assign_countries()` with the following helper and function:

```python
OVERRIDE_RADIUS_M = 500


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two latitude/longitude points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * 6_371_000 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def assign_countries(
    stations: list[Station],
    countries: list[tuple[str, list[list[Ring]]]],
    overrides: list[CountryOverride],
) -> list[str]:
    """Set station countries from coordinate overrides, then geography.

    Overrides match the nearest station within OVERRIDE_RADIUS_M and always emit
    an audit line. Non-overridden stations retain the existing polygon behavior.
    Returned lines are printed by the build stage, including unused/ambiguous warnings.
    """
    changes: list[str] = []
    overridden_ids: set[str] = set()

    for override in overrides:
        distances = sorted(
            (
                (_haversine_m(override.lat, override.lon, station.lat, station.lon), station)
                for station in stations
            ),
            key=lambda item: item[0],
        )
        within_radius = [item for item in distances if item[0] <= OVERRIDE_RADIUS_M]
        if not within_radius:
            changes.append(
                f"unused override {override.name!r} ({override.lat:.6f}, {override.lon:.6f}): "
                f"no station within {OVERRIDE_RADIUS_M}m"
            )
            continue

        _, nearest = within_radius[0]
        if len(within_radius) > 1:
            candidates = ", ".join(
                f"{station.id} ({station.name})" for _, station in within_radius
            )
            changes.append(
                f"ambiguous override {override.name!r} "
                f"({override.lat:.6f}, {override.lon:.6f}): "
                f"{len(within_radius)} stations within {OVERRIDE_RADIUS_M}m "
                f"({candidates}); using {nearest.id} ({nearest.name})"
            )

        old = nearest.country
        nearest.country = override.country
        overridden_ids.add(nearest.id)
        changes.append(f"{nearest.id} ({nearest.name}): {old} -> {override.country}")

    for station in stations:
        if station.id in overridden_ids:
            continue
        new = country_at(station.lat, station.lon, countries)
        if new is None:
            changes.append(
                f"{station.id} ({station.name}): no polygon match, "
                f"keeping feed country {station.country}"
            )
        elif new != station.country:
            changes.append(f"{station.id} ({station.name}): {station.country} -> {new}")
            station.country = new
    return changes
```

The sorted `(distance, station)` list makes nearest selection deterministic without comparing `Station` objects on equal distances. The `<=` comparison includes the radius boundary. Do not use `override.name` to filter candidates.

- [ ] **Step 6: Run the complete geo test file**

Run:

```bash
uv run pytest tests/test_geo.py -q
```

Expected: `10 passed`. Acceptance for this task is all four override tests passing alongside the unchanged polygon, hole, ISO-code, and no-polygon tests.

- [ ] **Step 7: Commit the model and matching unit**

```bash
git add pipeline/models.py pipeline/geo.py tests/test_geo.py
git commit -m "feat: match country overrides by coordinates"
```

Before committing, confirm `web/public/favicon.svg` is not staged.

---

### Task 2: Parse coordinate overrides in the build and remove their stale-id abort

**Files:**
- Modify: `tests/test_build.py:7-9,35-43,119-124,179-205`
- Modify: `pipeline/build.py:14-17,110-122,137-154`

**Interfaces:**
- Consumes: `CountryOverride` and `assign_countries(..., overrides: list[CountryOverride])` from Task 1; TOML document key `override` containing a list of dicts.
- Produces: `build()` loads `.get("override", [])` into `list[CountryOverride]`, prints returned unused/ambiguity warning lines with its existing `country: ` prefix, never aborts for an unmatched country override, and still raises `SystemExit(1)` for stale `station_names.toml` ids.

- [ ] **Step 1: Update the build fixture and replace the stale-country-id test first**

In `tests/test_build.py`, replace the `empty_overrides()` docstring/body with:

```python
def empty_overrides(tmp_path):
    """Empty coordinate-country and id-keyed name override files."""
    countries = tmp_path / "empty_countries.toml"
    countries.write_text("# No country overrides.\n")
    names = tmp_path / "empty_names.toml"
    names.write_text("[names]\n")
    return countries, names
```

Replace `test_station_countries_stale_id_fails_build` completely with:

```python
def test_station_countries_unmatched_override_warns_not_aborts(tmp_path, capsys):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)

    countries_toml = tmp_path / "station_countries.toml"
    countries_toml.write_text(
        '[[override]]\n'
        'name = "Ghost station"\n'
        "lat = 0.0\n"
        "lon = 0.0\n"
        'country = "XX"\n'
    )
    _, names_toml = empty_overrides(tmp_path)

    graph = tmp_path / "graph"
    build(
        raw,
        graph,
        feeds_toml,
        aliases_path=None,
        sample_date=SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )

    output = capsys.readouterr().out
    assert (
        "country: unused override 'Ghost station' (0.000000, 0.000000): "
        "no station within 500m"
    ) in output
    assert (graph / "stations.json").exists()
    assert (graph / "trips.json").exists()
```

Update the nearby section comment so it no longer says the id-keyed name override mirrors `station_countries.toml`; state that name overrides remain id-keyed while country overrides are coordinate-keyed. Do not modify `test_station_names_stale_id_fails_build`.

- [ ] **Step 2: Run the new integration test and observe the missing warning**

Run:

```bash
uv run pytest tests/test_build.py::test_station_countries_unmatched_override_warns_not_aborts -q
```

Expected: FAIL at the warning assertion. The current build reads only `.get("countries", {})`, so the `[[override]]` entry is ignored even though graph output may be written.

- [ ] **Step 3: Load typed entries and narrow stale validation to name ids**

In `pipeline/build.py`, change the model import to:

```python
from pipeline.models import CountryOverride, Station, Trip
```

Replace the country override loading block with:

```python
    country_overrides: list[CountryOverride] = []
    if station_countries_path.exists():
        raw_country_overrides = tomllib.loads(station_countries_path.read_text()).get(
            "override", []
        )
        country_overrides = [
            CountryOverride.model_validate(item) for item in raw_country_overrides
        ]
```

Replace the stale validation block at current lines 141-154 with:

```python
    # Country overrides are coordinate-keyed; unmatched entries already warn in
    # assign_countries. Display-name overrides remain id-keyed and stale ids abort.
    station_ids = {s.id for s in stations}
    stale = [
        f"station_names.toml: stale key {sid!r}"
        for sid in name_overrides
        if sid not in station_ids
    ]
    if stale:
        for msg in stale:
            print(f"OVERRIDE STALE: {msg}")
        raise SystemExit(1)
```

Keep the existing `assign_countries(stations, load_countries(ASSET), country_overrides)` call and `country: ` print prefix unchanged. Do not iterate over `country_overrides` in stale-id logic.

- [ ] **Step 4: Run all build tests**

Run:

```bash
uv run pytest tests/test_build.py -q
```

Expected: `7 passed`. Acceptance for this task is the unmatched override warning appearing while graph files are written, plus the unchanged station-name stale-id test still raising `SystemExit`.

- [ ] **Step 5: Run both affected suites together to catch interface drift**

Run:

```bash
uv run pytest tests/test_geo.py tests/test_build.py -q
```

Expected: `17 passed`.

- [ ] **Step 6: Commit the build integration**

```bash
git add pipeline/build.py tests/test_build.py
git commit -m "fix: stop aborting on unused country overrides"
```

Before committing, confirm `web/public/favicon.svg` is not staged.

---

### Task 3: Migrate all five production overrides to `[[override]]`

**Files:**
- Modify: `pipeline/station_countries.toml:1-41`

**Interfaces:**
- Consumes: The `CountryOverride` fields and `override` array key implemented in Tasks 1-2.
- Produces: Exactly five typed entries, keyed only by feed latitude/longitude: Konstanz Hbf, Weil am Rhein, Venezia Santa Lucia, Hendaye, and Viana do Castelo.

- [ ] **Step 1: Replace the old id table with five array-of-table entries**

Replace `pipeline/station_countries.toml` with the following. This updates only the obsolete schema header, preserves every existing evidence comment, retains old ids only as historical evidence, and adds the missing Viana feed-coordinate evidence:

```toml
# pipeline/station_countries.toml
#
# Per-station country overrides for pipeline/geo.py, for stations the 50m
# Natural Earth boundaries misplace (only ~1 km accurate at borders).
# Each override is keyed by feed coordinates; name is a human label only.
# Every entry needs an evidence comment: which border, why the polygon result
# is wrong.
#
# This file intentionally lives here, next to build.py, not at repo root next
# to feeds.toml -- deriving the path from feeds_path.parent silently loaded no
# overrides at all (2026-07-09).

[[override]]
name = "Konstanz Hbf"
lat = 47.65874
lon = 9.177333
country = "DE"
# Konstanz: town straddles the Bodensee shoreline right at the DE/CH border;
# the 2026-07 rebuild's polygon match flipped the station DE -> CH. Station
# coords (47.65874, 9.177333) are ~284m from Konstanz Hbf's real position
# (47.6612, 9.1763, OSM) -- the station itself is in Germany. Canonical id
# changed x:db_fern:185018 -> 8014586 when the station_aliases.toml Konstanz
# entry merged it onto sbb's UIC id (THURBO IR75 admission, 2026-07-10).

[[override]]
name = "Weil am Rhein"
lat = 47.593693
lon = 7.608739
country = "DE"
# Weil am Rhein: sits in the Basel tri-border (Dreiländereck) area where
# France/Germany/Switzerland meet within a few km; the polygon match flipped
# the station DE -> FR. Station coords (47.593693, 7.608739) are ~680m from
# the real Weil am Rhein station (47.5934, 7.6178, OSM) -- in Germany.

[[override]]
name = "Venezia Santa Lucia"
lat = 45.4424108
lon = 12.31972937
country = "IT"
# Venezia Santa Lucia (x:oebb:it:22099:110:51:1, 45.4424108, 12.31972937): "no
# polygon match" -- the 50m Natural Earth coastline is simplified across the
# Venice lagoon and the closest IT ring vertex is ~5km away, missing the
# barrier-island/reclaimed-land station site entirely. Real station, in Italy
# (verified coords match Venezia S. Lucia on OSM); feed country was AT
# (leaked in via the OEBB cross-border feed) with nothing to override it to IT.

[[override]]
name = "Hendaye"
lat = 43.353132
lon = -1.781724
country = "FR"
# Hendaye: French town right on the ES/FR border (the Bidasoa river is the
# boundary); the polygon match flipped the station FR -> ES due to 50m
# boundary imprecision. Station coords (43.353132, -1.781724) match Hendaye
# station's real position (43.3532, -1.7817, OSM) -- in France.
# Verified 2026-07-10.

[[override]]
name = "Viana do Castelo"
lat = 41.69517
lon = -8.83134
country = "PT"
# Viana do Castelo: Portuguese town on the border; the polygon match missed it
# so it inherited the feed country (ES).
# Feed coords (41.69517, -8.83134) are from data/raw/renfe.zip stops.txt.
# Verified 2026-07-10.
```

- [ ] **Step 2: Parse and validate the exact migrated values**

Run:

```bash
uv run python - <<'PY'
import tomllib
from pathlib import Path

from pipeline.models import CountryOverride

path = Path("pipeline/station_countries.toml")
raw = tomllib.loads(path.read_text()).get("override", [])
overrides = [CountryOverride.model_validate(item) for item in raw]
actual = [(o.name, o.lat, o.lon, o.country) for o in overrides]
expected = [
    ("Konstanz Hbf", 47.65874, 9.177333, "DE"),
    ("Weil am Rhein", 47.593693, 7.608739, "DE"),
    ("Venezia Santa Lucia", 45.4424108, 12.31972937, "IT"),
    ("Hendaye", 43.353132, -1.781724, "FR"),
    ("Viana do Castelo", 41.69517, -8.83134, "PT"),
]
assert actual == expected, actual
print("5 coordinate country overrides validated")
PY
```

Expected: `5 coordinate country overrides validated`. Any TOML parse/Pydantic failure or value mismatch fails the task.

- [ ] **Step 3: Re-run the focused tests with the real schema present**

Run:

```bash
uv run pytest tests/test_geo.py tests/test_build.py -q
```

Expected: `17 passed`.

- [ ] **Step 4: Commit the data migration**

```bash
git add pipeline/station_countries.toml
git commit -m "data: migrate country overrides to coordinates"
```

Before committing, confirm `web/public/favicon.svg` is not staged.

---

### Task 4: Verify the focused suites and the Jul-7 local build

**Files:**
- Verify: `pipeline/models.py`
- Verify: `pipeline/geo.py`
- Verify: `pipeline/build.py`
- Verify: `pipeline/station_countries.toml`
- Verify: `tests/test_geo.py`
- Verify: `tests/test_build.py`
- Runtime input: `data/raw/db_fern.zip`, with provenance in `data/raw/fetch_meta.json`

**Interfaces:**
- Consumes: All implementation and migration outputs from Tasks 1-3 plus the existing local feed archive.
- Produces: Test/lint evidence and a successful `ose build` log containing exactly five matched override audit lines and no unused/ambiguous override warnings.

- [ ] **Step 1: Confirm the required Jul-7 db_fern archive is the local input**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

archive = Path("data/raw/db_fern.zip")
meta = json.loads(Path("data/raw/fetch_meta.json").read_text())
assert archive.exists(), archive
assert meta["db_fern"]["ok"] is True
assert meta["db_fern"]["downloaded_at"].startswith("2026-07-07")
print(f"Jul-7 db_fern input ready: {archive}")
PY
```

Expected: `Jul-7 db_fern input ready: data/raw/db_fern.zip`. Do not run `ose fetch`.

- [ ] **Step 2: Run the required focused verification suite**

Run:

```bash
uv run pytest tests/test_geo.py tests/test_build.py -v
```

Expected: `17 passed`; specifically, the country unmatched case completes, the ambiguity case selects `near`, and `test_station_names_stale_id_fails_build` remains green by observing `SystemExit`.

- [ ] **Step 3: Lint every changed Python file**

Run:

```bash
uv run ruff check pipeline/models.py pipeline/geo.py pipeline/build.py tests/test_geo.py tests/test_build.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run the local graph build against the checked-in feeds**

Run in the foreground (allow approximately four minutes):

```bash
set -o pipefail
uv run ose build --date 2026-07-14 2>&1 | tee /tmp/coord-keyed-country-overrides-build.log
```

Expected: exit status 0 and a final `graph: ... stations, ... trips -> data/graph` line. There must be no `OVERRIDE STALE:` abort for `station_countries.toml`.

- [ ] **Step 5: Prove no override went stale/unused/ambiguous, and that all five resolved**

PRIMARY GATE — the build must contain none of these warning/abort lines. Run:

```bash
rg "OVERRIDE STALE: station_countries|unused override|ambiguous override" /tmp/coord-keyed-country-overrides-build.log
```

Expected: no output and exit status 1 (no matches). This, together with the Step 4 exit-0 build, is the real acceptance for the fix.

EVIDENCE — confirm each of the five migrated stations produced a `country:` audit line. Match the town name as a SUBSTRING (do NOT anchor on `(name)` with a trailing paren: canonical names carry suffixes like "Konstanz Hbf", so an exact-paren match would miss them):

```bash
rg -c "^country: .*(Konstanz|Weil am Rhein|Venezia Santa Lucia|Hendaye|Viana do Castelo)" /tmp/coord-keyed-country-overrides-build.log
```

Expected: `5`. An already-correct match legitimately reads `XX -> XX`; the line proves the coordinate override resolved rather than going unused. If the count is not 5, do NOT change implementation code — first inspect the log for the actual canonical names and confirm whether a name simply differs from the town label (adjust this grep) versus a genuine unused/ambiguous warning (a real problem, already caught by the primary gate).

Finally run `git status --short`; only the three intended commits plus any build-generated graph output should be attributable to this work, and the pre-existing `web/public/favicon.svg` modification must remain unstaged and untouched.

Acceptance for the entire plan: the exact focused pytest command passes, Ruff passes, `ose build` exits successfully against the Jul-7 db_fern archive, five coordinate matches appear, country overrides never enter stale-id abort handling, and stale name ids still abort.
