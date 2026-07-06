# onestopeurope Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean-slate rebuild: pick a European station, see every station reachable with ≤1/2/3 trains, colored by travel time, with ref-ready Trainline booking links.

**Architecture:** Offline Python pipeline (fetch GTFS feeds → build merged graph → compute RAPTOR reachability) writes static JSON to `data/out/`. A thin FastAPI server reads those files. A Vite + React + MapLibre frontend renders them. Spec: `docs/superpowers/specs/2026-07-07-onestopeurope-restart-design.md`.

**Tech Stack:** Python 3.14 + uv + pydantic + FastAPI + pytest; Vite + React + TypeScript (strict) + MapLibre GL JS + vitest; just; ruff.

## Global Constraints

- Python `>=3.14`, managed by **uv only** (never pip/venv/conda). All Python commands run as `uv run …`.
- Product name: **onestopeurope**. Tagline (exact copy): **"nonstopeurope with onestopeurope"**.
- Transfer minimum: **10 minutes**, hardcoded constant, not configurable via UI or API.
- Max journey: **3 trains** (UI labels: **Nonstop / One stop / Two stops**).
- Map: **MapLibre GL JS** with OpenFreeMap tiles. Leaflet and react-leaflet are banned.
- No runtime caching layers; `data/out/` files are the cache. No silent `except: pass` — every swallowed exception must log the feed/station it skipped.
- Station canonical IDs: UIC code as string where known, else `x:<feed>:<stop_id>`.
- Times inside pipeline/graph are **minutes since midnight** of the sample date (ints, may exceed 1440 for post-midnight arrivals). JSON output uses `"HH:MM"` strings only in `Leg.dep`/`Leg.arr`.
- Frontend env var for affiliate code: `VITE_TRAINLINE_REF` (empty string default).
- Commit after every task. Python style: ruff, line length 100.

---

## Phase A — Reset & Foundation

### Task 1: Checkpoint and clean slate

**Files:**
- Delete: `backend/`, `frontend/`, `README.md`, `CURRENT_STATUS.md`, `GETTING_STARTED.md`, `.env.example`, `.gitignore` (replaced)
- Keep: `.git/`, `docs/`, `.claude/`, untracked local files (`.env` — no longer needed but harmless)
- Create: `.gitignore`, `README.md`

**Interfaces:**
- Produces: an empty repo (plus docs/) that later tasks scaffold into.

- [ ] **Step 1: Checkpoint the old world**

```bash
cd /home/aaron/Projects/personal/de-trains-speed-map
git add -A
git commit -m "checkpoint: de-trains-speed-map final state before onestopeurope restart"
```

- [ ] **Step 2: Delete everything except .git, docs, .claude**

```bash
git rm -r --quiet backend frontend README.md CURRENT_STATUS.md GETTING_STARTED.md .env.example
rm -rf .ruff_cache
```

- [ ] **Step 3: Write new .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
.coverage

# Node
node_modules/
dist/
*.tsbuildinfo

# Env
.env
web/.env.local

# Pipeline data (samples in data/out/ are force-added explicitly)
data/raw/
data/graph/
data/out/
```

- [ ] **Step 4: Write minimal README.md**

```markdown
# onestopeurope

> nonstopeurope with onestopeurope

Pick a European station. See every station you can reach with at most one, two,
or three trains — colored by travel time — and click through to book.

**Status: rebuilding from scratch.** Design: `docs/superpowers/specs/2026-07-07-onestopeurope-restart-design.md`
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: clean slate for onestopeurope restart"
```

### Task 2: Python project scaffold (uv + pyproject + ruff + justfile)

**Files:**
- Create: `pyproject.toml`, `justfile`, `pipeline/__init__.py`, `server/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: `uv run pytest` and `uv run ruff check .` working; package roots `pipeline` and `server`; console script `ose = pipeline.cli:main` (cli added in Task 7).

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "onestopeurope"
version = "0.1.0"
description = "See where one, two, or three trains can take you across Europe"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.8",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.5"]

[project.scripts]
ose = "pipeline.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["pipeline", "server"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package skeletons and justfile**

```bash
mkdir -p pipeline server tests
touch pipeline/__init__.py server/__init__.py tests/__init__.py
```

`justfile`:

```just
# Run everything needed for development (web target added in Task 17)
test:
    uv run pytest -q

lint:
    uv run ruff check .

pipeline:
    uv run ose fetch && uv run ose build && uv run ose compute
```

- [ ] **Step 3: Verify toolchain**

Run: `uv python pin 3.14 && uv sync && uv run pytest -q`
Expected: `no tests ran` (exit 5 is fine), Python 3.14 in `uv run python --version`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: uv project scaffold with pipeline/server packages"
```

---

## Phase B — Pipeline

### Task 3: Data models and feeds.toml config

**Files:**
- Create: `pipeline/models.py`, `pipeline/config.py`, `feeds.toml`
- Test: `tests/test_models.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `pipeline.models`: `Station(id, name, lat, lon, country, has_reach=False)`, `StopTime(station, arr, dep)` (minutes), `Trip(trip_id, train, stops: list[StopTime])`, `Leg(train, dep, arr, from_ [alias "from"], to, via: list[str])`, `Journey(trains, duration_min, legs)`, `Destination(id, direct_per_day, journeys)`, `ReachFile(origin, computed_at, sample_date, destinations)` — all pydantic v2, `Leg` uses `populate_by_name=True`.
  - `pipeline.config`: `FeedConfig(url, country, license, route_allow: list[str], uic_regex: str | None)` and `load_feeds(path: Path) -> dict[str, FeedConfig]`.

- [ ] **Step 1: Write failing tests**

`tests/test_models.py`:

```python
from pipeline.models import Leg, Journey, ReachFile, Destination


def test_leg_serializes_with_from_alias():
    leg = Leg(train="ICE 517", dep="08:54", arr="11:26", **{"from": "8000105"}, to="8000261", via=[])
    assert leg.model_dump(by_alias=True)["from"] == "8000105"


def test_reach_file_round_trip():
    rf = ReachFile(
        origin="8000105", computed_at="2026-07-07T12:00:00Z", sample_date="2026-07-14",
        destinations=[Destination(id="8000261", direct_per_day=14, journeys=[
            Journey(trains=1, duration_min=190, legs=[
                Leg(train="ICE 517", dep="08:54", arr="12:04", **{"from": "8000105"},
                    to="8000261", via=["8000191"])])])],
    )
    again = ReachFile.model_validate_json(rf.model_dump_json(by_alias=True))
    assert again.destinations[0].journeys[0].legs[0].from_ == "8000105"
```

`tests/test_config.py`:

```python
from pathlib import Path
from pipeline.config import load_feeds


def test_load_feeds_parses_repo_feeds_toml():
    feeds = load_feeds(Path("feeds.toml"))
    assert "db_fern" in feeds
    assert feeds["db_fern"].country == "DE"
    assert any(p.startswith("^ICE") for p in feeds["db_fern"].route_allow)
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_models.py tests/test_config.py -q` — Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`pipeline/models.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class Station(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    country: str
    has_reach: bool = False


class StopTime(BaseModel):
    station: str
    arr: int  # minutes since midnight of sample date
    dep: int


class Trip(BaseModel):
    trip_id: str
    train: str  # display name, e.g. "ICE 517"
    stops: list[StopTime]


class Leg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    train: str
    dep: str  # "HH:MM"
    arr: str
    from_: str = Field(alias="from")
    to: str
    via: list[str]  # station ids strictly between from and to


class Journey(BaseModel):
    trains: int
    duration_min: int
    legs: list[Leg]


class Destination(BaseModel):
    id: str
    direct_per_day: int
    journeys: list[Journey]  # ascending trains; each strictly faster than previous


class ReachFile(BaseModel):
    origin: str
    computed_at: str
    sample_date: str
    destinations: list[Destination]
```

`pipeline/config.py`:

```python
import tomllib
from pathlib import Path

from pydantic import BaseModel


class FeedConfig(BaseModel):
    url: str
    country: str
    license: str
    route_allow: list[str]  # regexes matched against route display name
    uic_regex: str | None = None  # extracts UIC code from stop_id


def load_feeds(path: Path) -> dict[str, FeedConfig]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return {name: FeedConfig(**cfg) for name, cfg in raw.get("feeds", {}).items()}
```

`feeds.toml` (URLs verified at implementation time; if one 404s, fix the URL, not the code):

```toml
[feeds.db_fern]
url = "https://download.gtfs.de/germany/fv_free/latest.zip"
country = "DE"
license = "CC BY 4.0 - verify commercial terms before monetizing (fallback: DELFI NAP)"
route_allow = ["^ICE?\\b", "^ECE?\\b", "^NJ\\b", "^RJX?\\b", "^FLX\\b", "^TGV\\b", "^EST\\b"]
uic_regex = "(\\d{7})"

[feeds.sncf]
url = "https://eu.ftp.opendatasoft.com/sncf/gtfs/export_gtfs_voyages.zip"
country = "FR"
license = "ODbL (transport.data.gouv.fr)"
route_allow = ["^TGV", "^INTERCIT", "^OUIGO", "^EUROSTAR", "^ICE", "^LYRIA"]
uic_regex = "87(\\d{5})$"

[feeds.oebb]
url = "https://static.oebb.at/open-data/soll-fahrplan-gtfs/GTFS_OP_2026_obb.zip"
country = "AT"
license = "CC BY 4.0"
route_allow = ["^RJX?\\b", "^ICE?\\b", "^ECE?\\b", "^NJ\\b", "^D\\b"]
uic_regex = "(\\d{7})"

[feeds.sbb]
url = "https://data.opentransportdata.swiss/dataset/timetable-2026-gtfs2020/permalink"
country = "CH"
license = "Open data (opentransportdata.swiss)"
route_allow = ["^ICE?\\b", "^ECE?\\b", "^TGV", "^RJX?\\b", "^NJ\\b", "^IR\\b"]
uic_regex = "(\\d{7})"

[feeds.ns]
url = "https://gtfs.ovapi.nl/nl/gtfs-nl.zip"
country = "NL"
license = "CC0 (ovapi)"
route_allow = ["^Intercity", "^ICE?\\b", "^Eurostar", "^Nightjet"]
uic_regex = "(\\d{7})"
```

- [ ] **Step 4: Run tests, verify pass** — `uv run pytest tests/test_models.py tests/test_config.py -q` → PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pipeline data models and feed configuration"`

### Task 4: `ose fetch` — feed downloader with failure isolation

**Files:**
- Create: `pipeline/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `load_feeds`, `FeedConfig` (Task 3).
- Produces: `fetch_all(feeds: dict[str, FeedConfig], raw_dir: Path, client: httpx.Client) -> dict[str, bool]` — downloads each feed to `raw_dir/<name>.zip`, writes `raw_dir/fetch_meta.json` (`{name: {"downloaded_at": iso, "ok": bool}}`). One failure never aborts others; failures are printed with feed name.

- [ ] **Step 1: Write failing test** (`tests/test_fetch.py`) using `httpx.MockTransport`:

```python
import json
import httpx
from pipeline.config import FeedConfig
from pipeline.fetch import fetch_all


def _cfg(url: str) -> FeedConfig:
    return FeedConfig(url=url, country="XX", license="test", route_allow=[])


def test_fetch_isolates_failures(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "good" in str(request.url):
            return httpx.Response(200, content=b"PK\x03\x04zipbytes")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    results = fetch_all(
        {"good": _cfg("https://x/good.zip"), "bad": _cfg("https://x/bad.zip")},
        tmp_path, client,
    )
    assert results == {"good": True, "bad": False}
    assert (tmp_path / "good.zip").read_bytes().startswith(b"PK")
    assert not (tmp_path / "bad.zip").exists()
    meta = json.loads((tmp_path / "fetch_meta.json").read_text())
    assert meta["good"]["ok"] and not meta["bad"]["ok"]
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_fetch.py -q`

- [ ] **Step 3: Implement** (`pipeline/fetch.py`):

```python
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipeline.config import FeedConfig


def fetch_all(
    feeds: dict[str, FeedConfig], raw_dir: Path, client: httpx.Client | None = None
) -> dict[str, bool]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    results: dict[str, bool] = {}
    meta: dict[str, dict] = {}
    try:
        for name, cfg in feeds.items():
            stamp = datetime.now(UTC).isoformat()
            try:
                resp = client.get(cfg.url)
                resp.raise_for_status()
                (raw_dir / f"{name}.zip").write_bytes(resp.content)
                results[name] = True
                print(f"fetched {name} ({len(resp.content)} bytes)")
            except Exception as exc:  # failure isolation: report, continue
                results[name] = False
                print(f"FAILED {name}: {exc}")
            meta[name] = {"downloaded_at": stamp, "ok": results[name]}
    finally:
        if own_client:
            client.close()
    (raw_dir / "fetch_meta.json").write_text(json.dumps(meta, indent=2))
    return results
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_fetch.py -q`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: ose fetch with per-feed failure isolation"`

### Task 5: Fixture GTFS feeds (hand-verified test world)

**Files:**
- Create: `tests/fixtures.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Produces: `make_fixture_feeds(dir: Path) -> dict[str, FeedConfig]` — writes `landia.zip` and `borderia.zip` GTFS feeds plus returns matching FeedConfigs. **The fixture world (all times on every day of service, sample date 2026-07-14):**
  - Stations (UIC): Alpha `1111111` (50.0, 8.0), Beta `2222222` (50.0, 9.0), Gamma `3333333` (50.0, 10.0) — Gamma exists in BOTH feeds (border station, must merge), Delta `4444444` (50.0, 11.0, only borderia).
  - landia trips: `IC 100` Alpha 08:00 → Beta 09:00 → (continues) Gamma 10:00; `IC 101` Alpha 12:00 → Beta 12:50; `IC 300` Beta dep 09:05 → Gamma 10:05 (5-min transfer from IC 100 — must be rejected); `RB 1` Alpha 07:00 → Beta 08:30 (regional — must be filtered out).
  - borderia trips: `TGV 10` Gamma 10:30 → Delta 12:00.
  - **Hand-verified truths:** Alpha→Beta nonstop best = IC 101, 50 min, direct_per_day 2 (IC 100 + IC 101). Alpha→Gamma nonstop = IC 100, 120 min. Alpha→Delta = 2 trains (IC 100 then TGV 10 with 30-min transfer at Gamma), 08:00→12:00 = 240 min; NOT reachable nonstop. Beta→Gamma nonstop: best is IC 100 boarded mid-route at Beta (09:02→10:00, 58 min, so direct_per_day = 2); IC 300 (60 min) also exists and is fine as a first train, only invalid as a 5-min transfer. Do not assert "best Beta→Gamma = 60 min".

- [ ] **Step 1: Write the fixture builder** (`tests/fixtures.py`):

```python
import io
import zipfile
from pathlib import Path

from pipeline.config import FeedConfig

CAL = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nS1,1,1,1,1,1,1,1,20260101,20261231\n"

LANDIA = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nL,Landia,https://l.example,Europe/Berlin\n",
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "st:1111111,Alpha Hbf,50.0,8.0\n"
        "st:2222222,Beta Hbf,50.0,9.0\n"
        "st:3333333,Gamma Hbf,50.0,10.0\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_type\n"
        "R100,L,IC 100,2\nR101,L,IC 101,2\nR300,L,IC 300,2\nRB1,L,RB 1,2\n"
    ),
    "trips.txt": (
        "route_id,service_id,trip_id\nR100,S1,T100\nR101,S1,T101\nR300,S1,T300\nRB1,S1,TRB1\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T100,08:00:00,08:00:00,st:1111111,1\n"
        "T100,09:00:00,09:02:00,st:2222222,2\n"
        "T100,10:00:00,10:00:00,st:3333333,3\n"
        "T101,12:00:00,12:00:00,st:1111111,1\n"
        "T101,12:50:00,12:50:00,st:2222222,2\n"
        "T300,09:05:00,09:05:00,st:2222222,1\n"
        "T300,10:05:00,10:05:00,st:3333333,2\n"
        "TRB1,07:00:00,07:00:00,st:1111111,1\n"
        "TRB1,08:30:00,08:30:00,st:2222222,2\n"
    ),
    "calendar.txt": CAL,
}

BORDERIA = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nB,Borderia,https://b.example,Europe/Paris\n",
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "bs-3333333,Gamma Central,50.0001,10.0001\n"
        "bs-4444444,Delta Gare,50.0,11.0\n"
    ),
    "routes.txt": "route_id,agency_id,route_short_name,route_type\nRT10,B,TGV 10,2\n",
    "trips.txt": "route_id,service_id,trip_id\nRT10,S1,TT10\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "TT10,10:30:00,10:30:00,bs-3333333,1\n"
        "TT10,12:00:00,12:00:00,bs-4444444,2\n"
    ),
    "calendar.txt": CAL,
}


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def make_fixture_feeds(dir: Path) -> dict[str, FeedConfig]:
    dir.mkdir(parents=True, exist_ok=True)
    (dir / "landia.zip").write_bytes(_zip(LANDIA))
    (dir / "borderia.zip").write_bytes(_zip(BORDERIA))
    return {
        "landia": FeedConfig(url="unused", country="LA", license="test",
                             route_allow=["^IC\\b", "^TGV\\b"], uic_regex="(\\d{7})"),
        "borderia": FeedConfig(url="unused", country="BO", license="test",
                               route_allow=["^TGV\\b"], uic_regex="(\\d{7})"),
    }
```

- [ ] **Step 2: Sanity test** (`tests/test_fixtures.py`):

```python
import zipfile
from tests.fixtures import make_fixture_feeds


def test_fixture_zips_are_valid_gtfs(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    assert set(cfgs) == {"landia", "borderia"}
    with zipfile.ZipFile(tmp_path / "landia.zip") as zf:
        assert {"stops.txt", "trips.txt", "stop_times.txt", "routes.txt", "calendar.txt"} <= set(zf.namelist())
```

- [ ] **Step 3: Run** — `uv run pytest tests/test_fixtures.py -q` → PASS (builder has no prod code to fail against; the test guards the fixture itself)

- [ ] **Step 4: Commit** — `git add -A && git commit -m "test: hand-verified fixture GTFS feeds"`

### Task 6: GTFS loading + long-distance filter

**Files:**
- Create: `pipeline/gtfs.py`
- Test: `tests/test_gtfs.py`

**Interfaces:**
- Consumes: fixture feeds (Task 5), `FeedConfig`, `Trip`, `StopTime`.
- Produces: `RawStop(stop_id, name, lat, lon)` dataclass and `load_feed(zip_path: Path, cfg: FeedConfig, sample_date: date) -> tuple[list[RawStop], list[Trip]]`. Trips: only services active on `sample_date` (calendar.txt weekday+range, calendar_dates.txt exceptions), only routes whose display name matches any `route_allow` regex; `Trip.train` = route_short_name; `Trip.stops[].station` holds the **feed-local stop_id** (canonicalized later); times parsed to minutes (`"26:15:00"` → 1575). Also `next_tuesday(today: date) -> date`.

- [ ] **Step 1: Write failing tests** (`tests/test_gtfs.py`):

```python
from datetime import date
from pipeline.gtfs import load_feed, next_tuesday
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)  # a Tuesday


def test_load_feed_filters_regional_and_parses_times(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    stops, trips = load_feed(tmp_path / "landia.zip", cfgs["landia"], SAMPLE)
    names = {t.train for t in trips}
    assert names == {"IC 100", "IC 101", "IC 300"}  # RB 1 filtered out
    t100 = next(t for t in trips if t.train == "IC 100")
    assert [s.station for s in t100.stops] == ["st:1111111", "st:2222222", "st:3333333"]
    assert t100.stops[0].dep == 8 * 60 and t100.stops[2].arr == 10 * 60
    assert {s.stop_id for s in stops} == {"st:1111111", "st:2222222", "st:3333333"}


def test_load_feed_respects_calendar(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    _, trips = load_feed(tmp_path / "landia.zip", cfgs["landia"], date(2027, 1, 1))
    assert trips == []  # outside service range


def test_next_tuesday():
    assert next_tuesday(date(2026, 7, 7)) == date(2026, 7, 14)  # Tue -> next Tue
    assert next_tuesday(date(2026, 7, 8)) == date(2026, 7, 14)  # Wed -> coming Tue
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_gtfs.py -q`

- [ ] **Step 3: Implement** (`pipeline/gtfs.py`):

```python
import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import FeedConfig
from pipeline.models import StopTime, Trip

WEEKDAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class RawStop:
    stop_id: str
    name: str
    lat: float
    lon: float


def next_tuesday(today: date) -> date:
    days_ahead = (1 - today.weekday()) % 7  # Tuesday == 1
    return today + timedelta(days=days_ahead or 7)


def _minutes(hms: str) -> int:
    h, m, _s = hms.split(":")
    return int(h) * 60 + int(m)


def _rows(zf: zipfile.ZipFile, name: str) -> list[dict]:
    if name not in zf.namelist():
        return []
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def _active_services(zf: zipfile.ZipFile, day: date) -> set[str]:
    ymd = day.strftime("%Y%m%d")
    active: set[str] = set()
    for row in _rows(zf, "calendar.txt"):
        if (row["start_date"] <= ymd <= row["end_date"]
                and row[WEEKDAY_COLS[day.weekday()]] == "1"):
            active.add(row["service_id"])
    for row in _rows(zf, "calendar_dates.txt"):
        if row["date"] == ymd:
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            else:
                active.discard(row["service_id"])
    return active


def load_feed(
    zip_path: Path, cfg: FeedConfig, sample_date: date
) -> tuple[list[RawStop], list[Trip]]:
    allow = [re.compile(p) for p in cfg.route_allow]
    with zipfile.ZipFile(zip_path) as zf:
        routes = {}
        for r in _rows(zf, "routes.txt"):
            name = r.get("route_short_name") or r.get("route_long_name") or ""
            if any(p.search(name) for p in allow):
                routes[r["route_id"]] = name

        active = _active_services(zf, sample_date)
        trip_train = {
            t["trip_id"]: routes[t["route_id"]]
            for t in _rows(zf, "trips.txt")
            if t["route_id"] in routes and t["service_id"] in active
        }

        stop_times: dict[str, list[tuple[int, StopTime]]] = {}
        used_stops: set[str] = set()
        for st in _rows(zf, "stop_times.txt"):
            tid = st["trip_id"]
            if tid not in trip_train:
                continue
            arr, dep = st["arrival_time"] or st["departure_time"], st["departure_time"] or st["arrival_time"]
            entry = (int(st["stop_sequence"]),
                     StopTime(station=st["stop_id"], arr=_minutes(arr), dep=_minutes(dep)))
            stop_times.setdefault(tid, []).append(entry)
            used_stops.add(st["stop_id"])

        trips = []
        for tid, entries in stop_times.items():
            entries.sort(key=lambda e: e[0])
            trips.append(Trip(trip_id=tid, train=trip_train[tid], stops=[e[1] for e in entries]))

        stops = [
            RawStop(s["stop_id"], s["stop_name"], float(s["stop_lat"]), float(s["stop_lon"]))
            for s in _rows(zf, "stops.txt")
            if s["stop_id"] in used_stops and s.get("stop_lat") and s.get("stop_lon")
        ]
    return stops, trips
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_gtfs.py -q`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: GTFS loading with service-day and long-distance filtering"`

### Task 7: Station merging across feeds

**Files:**
- Create: `pipeline/merge.py`, `station_aliases.toml`
- Test: `tests/test_merge.py`

**Interfaces:**
- Consumes: `RawStop`, `FeedConfig`, `Station`.
- Produces: `merge_stations(per_feed: dict[str, tuple[list[RawStop], FeedConfig]], aliases: dict[str, str]) -> tuple[list[Station], dict[tuple[str, str], str]]` — returns registry and mapping `(feed_name, stop_id) → canonical_id`. Canonical id: alias override first (`"<feed>:<stop_id>"` key), then UIC via `cfg.uic_regex` on stop_id, else proximity fallback (existing station within 500m) else `x:<feed>:<stop_id>`. First feed to name a station wins the display name; `Station.country` from that feed.

- [ ] **Step 1: Write failing tests** (`tests/test_merge.py`):

```python
from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop
from pipeline.merge import merge_stations


def _cfg(**kw) -> FeedConfig:
    return FeedConfig(url="u", country=kw.pop("country", "XX"), license="t",
                      route_allow=[], **kw)


def test_border_station_merges_via_uic():
    per_feed = {
        "landia": ([RawStop("st:3333333", "Gamma Hbf", 50.0, 10.0)], _cfg(uic_regex=r"(\d{7})", country="LA")),
        "borderia": ([RawStop("bs-3333333", "Gamma Central", 50.0001, 10.0001)], _cfg(uic_regex=r"(\d{7})", country="BO")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert stations[0].id == "3333333" and stations[0].name == "Gamma Hbf"
    assert mapping[("landia", "st:3333333")] == mapping[("borderia", "bs-3333333")] == "3333333"


def test_proximity_fallback_merges_unmatched_ids():
    per_feed = {
        "a": ([RawStop("weird-id", "Same Place", 51.0, 7.0)], _cfg(uic_regex=r"^(\d{7})$")),
        "b": ([RawStop("other-id", "Same Place", 51.001, 7.001)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("a", "weird-id")] == mapping[("b", "other-id")]


def test_alias_override_wins():
    per_feed = {"a": ([RawStop("odd", "X", 40.0, 4.0)], _cfg())}
    stations, mapping = merge_stations(per_feed, {"a:odd": "1234567"})
    assert mapping[("a", "odd")] == "1234567"
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_merge.py -q`

- [ ] **Step 3: Implement** (`pipeline/merge.py`):

```python
import math
import re

from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop
from pipeline.models import Station

PROXIMITY_M = 500


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Equirectangular approximation, fine below a few km
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6_371_000


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def merge_stations(
    per_feed: dict[str, tuple[list[RawStop], FeedConfig]],
    aliases: dict[str, str],
) -> tuple[list[Station], dict[tuple[str, str], str]]:
    registry: dict[str, Station] = {}
    mapping: dict[tuple[str, str], str] = {}

    for feed, (stops, cfg) in per_feed.items():
        uic_re = re.compile(cfg.uic_regex) if cfg.uic_regex else None
        for stop in stops:
            canonical = aliases.get(f"{feed}:{stop.stop_id}")
            if canonical is None and uic_re:
                m = uic_re.search(stop.stop_id)
                canonical = m.group(1) if m else None
            if canonical is None:
                canonical = next(
                    (sid for sid, s in registry.items()
                     if _norm(s.name) == _norm(stop.name)
                     and _dist_m(s.lat, s.lon, stop.lat, stop.lon) < PROXIMITY_M),
                    None,
                ) or f"x:{feed}:{stop.stop_id}"
            if canonical not in registry:
                registry[canonical] = Station(
                    id=canonical, name=stop.name, lat=stop.lat, lon=stop.lon,
                    country=cfg.country,
                )
            mapping[(feed, stop.stop_id)] = canonical
    return list(registry.values()), mapping
```

`station_aliases.toml` (checked in, initially near-empty):

```toml
# Manual overrides: "<feed>:<stop_id>" = "<canonical UIC id>"
# Add entries when the validation step reports unmerged duplicates.
[aliases]
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_merge.py -q`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: cross-feed station merging (UIC, proximity, aliases)"`

### Task 8: `ose build` — graph assembly + validation + CLI

**Files:**
- Create: `pipeline/build.py`, `pipeline/cli.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: everything from Tasks 3–7.
- Produces:
  - `build(raw_dir, graph_dir, feeds_path, aliases_path, sample_date) -> None` — loads every `<name>.zip` present, remaps trip stop ids to canonical ids, drops trips with <2 stops after remap, writes `graph_dir/stations.json` (`{"sample_date": "...", "stations": [...]}`) and `graph_dir/trips.json` (`{"trips": [...]}`).
  - `validate(stations: list[Station], trips: list[Trip]) -> list[str]` — returns human-readable problems: station at (0,0); trip with non-increasing stop times; two stations <500m apart with identical normalized names (unmerged duplicate). `build` prints problems and raises `SystemExit(1)` if any.
  - `pipeline/cli.py`: `main()` with argparse subcommands `fetch` / `build` / `compute` (compute wired in Task 10), default dirs `data/raw`, `data/graph`, `data/out`, `--date YYYY-MM-DD` optional (default `next_tuesday(today)`).

- [ ] **Step 1: Write failing tests** (`tests/test_build.py`):

```python
import json
from datetime import date
from pipeline.build import build, validate
from pipeline.models import Station, StopTime, Trip
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)


def _write_feeds_toml(tmp_path, cfgs):
    lines = []
    for name, c in cfgs.items():
        lines += [f"[feeds.{name}]", f'url = "{c.url}"', f'country = "{c.country}"',
                  f'license = "{c.license}"',
                  "route_allow = [" + ", ".join(f'"{p}"' for p in c.route_allow) + "]"]
        if c.uic_regex:
            lines.append(f'uic_regex = "{c.uic_regex}"'.replace("\\", "\\\\"))
    p = tmp_path / "feeds.toml"
    p.write_text("\n".join(lines))
    return p


def test_build_produces_merged_graph(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    graph = tmp_path / "graph"
    build(raw, graph, feeds_toml, aliases_path=None, sample_date=SAMPLE)

    stations = json.loads((graph / "stations.json").read_text())
    ids = {s["id"] for s in stations["stations"]}
    assert ids == {"1111111", "2222222", "3333333", "4444444"}  # Gamma merged once

    trips = json.loads((graph / "trips.json").read_text())["trips"]
    tgv = next(t for t in trips if t["train"] == "TGV 10")
    assert [s["station"] for s in tgv["stops"]] == ["3333333", "4444444"]


def test_validate_flags_nonsense():
    bad_station = Station(id="1", name="Zero", lat=0.0, lon=0.0, country="XX")
    bad_trip = Trip(trip_id="t", train="IC 1", stops=[
        StopTime(station="1", arr=600, dep=600), StopTime(station="2", arr=500, dep=500)])
    problems = validate([bad_station], [bad_trip])
    assert any("0,0" in p for p in problems) and any("non-increasing" in p for p in problems)
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_build.py -q`

- [ ] **Step 3: Implement** (`pipeline/build.py`):

```python
import json
import tomllib
from datetime import date
from pathlib import Path

from pipeline.config import load_feeds
from pipeline.gtfs import load_feed
from pipeline.merge import _dist_m, _norm, merge_stations
from pipeline.models import Station, Trip


def validate(stations: list[Station], trips: list[Trip]) -> list[str]:
    problems: list[str] = []
    for s in stations:
        if abs(s.lat) < 0.01 and abs(s.lon) < 0.01:
            problems.append(f"station {s.id} ({s.name}) sits at 0,0")
    for t in trips:
        for a, b in zip(t.stops, t.stops[1:]):
            if b.arr < a.dep:
                problems.append(f"trip {t.trip_id} ({t.train}) has non-increasing times")
                break
    for i, a in enumerate(stations):
        for b in stations[i + 1:]:
            if _norm(a.name) == _norm(b.name) and _dist_m(a.lat, a.lon, b.lat, b.lon) < 500:
                problems.append(f"unmerged duplicate: {a.id} / {b.id} ({a.name})")
    return problems


def build(
    raw_dir: Path, graph_dir: Path, feeds_path: Path,
    aliases_path: Path | None, sample_date: date,
) -> None:
    feeds = load_feeds(feeds_path)
    aliases: dict[str, str] = {}
    if aliases_path and aliases_path.exists():
        aliases = tomllib.loads(aliases_path.read_text()).get("aliases", {})

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

    all_trips: list[Trip] = []
    for name, trips in feed_trips.items():
        for t in trips:
            for s in t.stops:
                s.station = mapping[(name, s.station)]
            if len(t.stops) >= 2:
                all_trips.append(t)

    problems = validate(stations, all_trips)
    if problems:
        for p in problems:
            print(f"VALIDATION: {p}")
        raise SystemExit(1)

    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "stations.json").write_text(json.dumps(
        {"sample_date": sample_date.isoformat(),
         "stations": [s.model_dump() for s in stations]}, ensure_ascii=False))
    (graph_dir / "trips.json").write_text(json.dumps(
        {"trips": [t.model_dump() for t in all_trips]}, ensure_ascii=False))
    print(f"graph: {len(stations)} stations, {len(all_trips)} trips -> {graph_dir}")
```

`pipeline/cli.py`:

```python
import argparse
from datetime import date
from pathlib import Path

from pipeline.gtfs import next_tuesday

RAW, GRAPH, OUT = Path("data/raw"), Path("data/graph"), Path("data/out")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ose", description="onestopeurope data pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    b.add_argument("--date", type=date.fromisoformat, default=next_tuesday(date.today()))
    sub.add_parser("compute")
    args = parser.parse_args()

    if args.cmd == "fetch":
        from pipeline.config import load_feeds
        from pipeline.fetch import fetch_all
        fetch_all(load_feeds(Path("feeds.toml")), RAW)
    elif args.cmd == "build":
        from pipeline.build import build
        build(RAW, GRAPH, Path("feeds.toml"), Path("station_aliases.toml"), args.date)
    elif args.cmd == "compute":
        from pipeline.compute import compute_all
        compute_all(GRAPH, OUT)
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_build.py -q` (the `compute` import only runs when invoked; fine until Task 10)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: ose build with graph validation and CLI"`

### Task 9: RAPTOR reachability core

**Files:**
- Create: `pipeline/raptor.py`
- Test: `tests/test_raptor.py`

**Interfaces:**
- Consumes: `Trip`, `StopTime`, `Leg`, `Journey`.
- Produces: `compute_reachability(trips: list[Trip], origin: str, max_trains: int = 3, transfer_min: int = 10) -> dict[str, list[Journey]]` — per destination, the best journey per train-count tier (ascending `trains`, each strictly faster than the previous; tiers that don't improve are omitted). Duration = arrival − actual first departure, minimized over hourly departure floors 05:00–20:00. Also `fmt(minutes: int) -> str` ("HH:MM", modulo 24h).

- [ ] **Step 1: Write failing tests** (`tests/test_raptor.py`) — these encode the hand-verified fixture truths:

```python
from datetime import date
from pipeline.gtfs import load_feed
from pipeline.merge import merge_stations
from pipeline.raptor import compute_reachability, fmt
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)
ALPHA, BETA, GAMMA, DELTA = "1111111", "2222222", "3333333", "4444444"


def _world(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    per_feed, all_trips = {}, []
    for name in cfgs:
        stops, trips = load_feed(tmp_path / f"{name}.zip", cfgs[name], SAMPLE)
        per_feed[name] = (stops, cfgs[name])
        all_trips.append((name, trips))
    _, mapping = merge_stations(per_feed, {})
    trips = []
    for name, ts in all_trips:
        for t in ts:
            for s in t.stops:
                s.station = mapping[(name, s.station)]
            trips.append(t)
    return trips


def test_nonstop_picks_fastest_direct_train(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    beta = reach[BETA]
    assert beta[0].trains == 1 and beta[0].duration_min == 50  # IC 101, not IC 100
    assert beta[0].legs[0].train == "IC 101"


def test_one_stop_respects_min_transfer(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    gamma = reach[GAMMA]
    # Direct IC 100 exists (120 min). IC 100->IC 300 (5-min transfer) is illegal,
    # so no 2-train journey can beat the direct one -> exactly one tier.
    assert [j.trains for j in gamma] == [1]
    assert gamma[0].duration_min == 120


def test_two_trains_cross_border(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    delta = reach[DELTA]
    assert [j.trains for j in delta] == [2]
    assert delta[0].duration_min == 240  # 08:00 -> 12:00
    assert [leg.train for leg in delta[0].legs] == ["IC 100", "TGV 10"]
    assert delta[0].legs[0].via == [BETA]  # via-station for the polyline


def test_unreachable_station_absent(tmp_path):
    reach = compute_reachability(_world(tmp_path), DELTA)
    assert ALPHA not in reach  # no trains run backwards in the fixture


def test_fmt():
    assert fmt(8 * 60) == "08:00" and fmt(25 * 60 + 5) == "01:05"
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_raptor.py -q`

- [ ] **Step 3: Implement** (`pipeline/raptor.py`):

```python
from pipeline.models import Journey, Leg, Trip

INF = 10**9


def fmt(minutes: int) -> str:
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def _raptor(trips, origin, dep_floor, max_trains, transfer_min):
    """Round k = earliest arrival using <= k trains, departing origin no earlier
    than dep_floor. parent[(k, station)] = (trip, board_station, board_dep,
    alight_arr, board_idx, alight_idx)."""
    arr: list[dict[str, int]] = [{origin: dep_floor}]
    parent: dict[tuple[int, str], tuple] = {}
    for k in range(1, max_trains + 1):
        cur = dict(arr[k - 1])
        for st in arr[k - 1]:
            if (k - 1, st) in parent:
                parent[(k, st)] = parent[(k - 1, st)]
        for trip in trips:
            board = None  # (station, dep, idx)
            for i, s in enumerate(trip.stops):
                if board is not None and s.arr < cur.get(s.station, INF):
                    cur[s.station] = s.arr
                    parent[(k, s.station)] = (trip, board[0], board[1], s.arr, board[2], i)
                if board is None:
                    reached = arr[k - 1].get(s.station, INF)
                    buffer = 0 if s.station == origin else transfer_min
                    if reached + buffer <= s.dep:
                        board = (s.station, s.dep, i)
        arr.append(cur)
    return arr, parent


def _reconstruct(parent, k, dest, origin):
    """Walk parent pointers back to origin. Returns (legs, first_dep) or None."""
    legs: list[Leg] = []
    st, kk = dest, k
    while st != origin:
        p = parent.get((kk, st))
        if p is None:
            return None
        trip, b_st, b_dep, a_arr, bi, ai = p
        legs.append(Leg(
            train=trip.train, dep=fmt(b_dep), arr=fmt(a_arr),
            **{"from": b_st}, to=st,
            via=[x.station for x in trip.stops[bi + 1:ai]],
        ))
        st, kk = b_st, kk - 1
        if kk < 0:
            return None
    legs.reverse()
    first_dep = legs[0].dep
    return legs, int(first_dep[:2]) * 60 + int(first_dep[3:])


def compute_reachability(
    trips: list[Trip], origin: str, max_trains: int = 3, transfer_min: int = 10
) -> dict[str, list[Journey]]:
    best: dict[tuple[str, int], Journey] = {}
    for dep_floor in range(5 * 60, 21 * 60, 60):
        arr, parent = _raptor(trips, origin, dep_floor, max_trains, transfer_min)
        for k in range(1, max_trains + 1):
            for dest, t in arr[k].items():
                if dest == origin:
                    continue
                rec = _reconstruct(parent, k, dest, origin)
                if rec is None:
                    continue
                legs, first_dep = rec
                journey = Journey(trains=len(legs), duration_min=t - first_dep, legs=legs)
                key = (dest, journey.trains)
                if key not in best or journey.duration_min < best[key].duration_min:
                    best[key] = journey

    out: dict[str, list[Journey]] = {}
    dests = {d for d, _ in best}
    for dest in dests:
        tiers = []
        for k in range(1, max_trains + 1):
            j = best.get((dest, k))
            if j and (not tiers or j.duration_min < tiers[-1].duration_min):
                tiers.append(j)
        out[dest] = tiers
    return out
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_raptor.py -q`. If a fixture assertion fails, debug the algorithm — the fixture truths were verified by hand and are correct.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: RAPTOR reachability with transfer validation and tier collapse"`

### Task 10: `ose compute` — reach files, frequency, meta

**Files:**
- Create: `pipeline/compute.py`
- Test: `tests/test_compute.py`

**Interfaces:**
- Consumes: graph files (Task 8), `compute_reachability` (Task 9), models (Task 3).
- Produces: `compute_all(graph_dir: Path, out_dir: Path) -> None` — for each station in the graph: run reachability; if any destination reached, write `out_dir/reach_<id>.json` (a `ReachFile`, serialized `by_alias`) with `direct_per_day` = count of trips serving origin before destination in stop order. Writes `out_dir/stations.json` (registry with `has_reach` flags) and `out_dir/meta.json` (`computed_at`, `sample_date`, `feeds` from `data/raw/fetch_meta.json` when present).

- [ ] **Step 1: Write failing test** (`tests/test_compute.py`):

```python
import json
from datetime import date
from pipeline.build import build
from pipeline.compute import compute_all
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml

SAMPLE = date(2026, 7, 14)


def test_compute_all_writes_reach_files(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    build(raw, tmp_path / "graph", _write_feeds_toml(tmp_path, cfgs), None, SAMPLE)
    compute_all(tmp_path / "graph", tmp_path / "out")

    reach = json.loads((tmp_path / "out" / "reach_1111111.json").read_text())
    beta = next(d for d in reach["destinations"] if d["id"] == "2222222")
    assert beta["direct_per_day"] == 2  # IC 100 + IC 101
    assert beta["journeys"][0]["legs"][0]["from"] == "1111111"  # alias serialization

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    delta = next(s for s in stations["stations"] if s["id"] == "4444444")
    assert alpha["has_reach"] is True and delta["has_reach"] is False

    meta = json.loads((tmp_path / "out" / "meta.json").read_text())
    assert meta["sample_date"] == "2026-07-14" and "computed_at" in meta
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_compute.py -q`

- [ ] **Step 3: Implement** (`pipeline/compute.py`):

```python
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pipeline.models import Destination, ReachFile, Station, Trip
from pipeline.raptor import compute_reachability


def _direct_counts(trips: list[Trip], origin: str) -> Counter:
    counts: Counter = Counter()
    for t in trips:
        seen_origin = False
        for s in t.stops:
            if seen_origin:
                counts[s.station] += 1
            if s.station == origin:
                seen_origin = True
    return counts


def compute_all(graph_dir: Path, out_dir: Path) -> None:
    graph = json.loads((graph_dir / "stations.json").read_text())
    sample_date = graph["sample_date"]
    stations = [Station(**s) for s in graph["stations"]]
    trips = [Trip(**t) for t in json.loads((graph_dir / "trips.json").read_text())["trips"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    for station in stations:
        reach = compute_reachability(trips, station.id)
        if not reach:
            continue
        directs = _direct_counts(trips, station.id)
        rf = ReachFile(
            origin=station.id, computed_at=now, sample_date=sample_date,
            destinations=[
                Destination(id=dest, direct_per_day=directs.get(dest, 0), journeys=js)
                for dest, js in sorted(reach.items())
            ],
        )
        (out_dir / f"reach_{station.id}.json").write_text(rf.model_dump_json(by_alias=True))
        station.has_reach = True
        print(f"reach_{station.id}.json: {len(reach)} destinations")

    (out_dir / "stations.json").write_text(json.dumps(
        {"stations": [s.model_dump() for s in stations]}, ensure_ascii=False))

    fetch_meta_path = Path("data/raw/fetch_meta.json")
    feeds_meta = json.loads(fetch_meta_path.read_text()) if fetch_meta_path.exists() else {}
    (out_dir / "meta.json").write_text(json.dumps(
        {"computed_at": now, "sample_date": sample_date, "feeds": feeds_meta}))
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_compute.py -q`, then full suite `uv run pytest -q` and `uv run ruff check .`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: ose compute writes reach files, frequencies, meta"`

---

## Phase C — Server

### Task 11: FastAPI core endpoints

**Files:**
- Create: `server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `data/out/` file formats (Task 10).
- Produces: `create_app(data_dir: Path) -> FastAPI` and module-level `app = create_app(Path("data/out"))`. Endpoints: `GET /api/stations` (stations.json verbatim), `GET /api/reach/{station_id}` (file verbatim; 404 unknown), `GET /api/meta` (meta.json; 503 `{"detail": "Pipeline has never run - no data available"}` if missing). CORS: allow all origins (dev-friendly; tighten at deploy).

- [ ] **Step 1: Write failing tests** (`tests/test_server.py`):

```python
import pytest
from datetime import date
from fastapi.testclient import TestClient
from pipeline.build import build
from pipeline.compute import compute_all
from server.app import create_app
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("world")
    raw = tmp / "raw"
    cfgs = make_fixture_feeds(raw)
    build(raw, tmp / "graph", _write_feeds_toml(tmp, cfgs), None, date(2026, 7, 14))
    compute_all(tmp / "graph", tmp / "out")
    return TestClient(create_app(tmp / "out"))


def test_stations_endpoint(client):
    stations = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in stations} == {"1111111", "2222222", "3333333", "4444444"}


def test_reach_endpoint(client):
    r = client.get("/api/reach/1111111")
    assert r.status_code == 200 and r.json()["origin"] == "1111111"
    assert client.get("/api/reach/9999999").status_code == 404


def test_meta_and_503(client, tmp_path):
    assert client.get("/api/meta").json()["sample_date"] == "2026-07-14"
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/api/meta").status_code == 503
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_server.py -q`

- [ ] **Step 3: Implement** (`server/app.py`):

```python
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def _read(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=503,
                            detail="Pipeline has never run - no data available")
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(title="onestopeurope")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

    @app.get("/api/stations")
    def stations() -> dict:
        return _read(data_dir / "stations.json")

    @app.get("/api/reach/{station_id}")
    def reach(station_id: str) -> dict:
        path = data_dir / f"reach_{station_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"No data for station {station_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/meta")
    def meta() -> dict:
        return _read(data_dir / "meta.json")

    return app


app = create_app(Path("data/out"))
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_server.py -q`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: FastAPI serving precomputed reach data"`

### Task 12: Station search endpoint

**Files:**
- Modify: `server/app.py` (add endpoint inside `create_app`)
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `GET /api/stations/search?q=<str>&limit=<int=10>` → `{"stations": [Station…]}` — accent-insensitive, case-insensitive; prefix matches rank above substring matches; ties broken by shorter name; only stations with `has_reach=true`. Helper `normalize(s: str) -> str` exported from `server.app`.

- [ ] **Step 1: Write failing tests** (`tests/test_search.py`):

```python
import json
from fastapi.testclient import TestClient
from server.app import create_app, normalize


def _client(tmp_path):
    stations = [
        {"id": "1", "name": "München Hbf", "lat": 48.1, "lon": 11.5, "country": "DE", "has_reach": True},
        {"id": "2", "name": "München Ost", "lat": 48.1, "lon": 11.6, "country": "DE", "has_reach": True},
        {"id": "3", "name": "Bad München-Dorf", "lat": 48.2, "lon": 11.7, "country": "DE", "has_reach": True},
        {"id": "4", "name": "Münchenberg", "lat": 49.0, "lon": 12.0, "country": "DE", "has_reach": False},
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    return TestClient(create_app(tmp_path))


def test_normalize_strips_accents():
    assert normalize("München") == "munchen"
    assert normalize("Zürich HB") == "zurich hb"


def test_search_prefix_beats_substring_and_skips_no_reach(tmp_path):
    got = _client(tmp_path).get("/api/stations/search", params={"q": "munchen"}).json()["stations"]
    names = [s["name"] for s in got]
    assert names[0] == "München Hbf"          # prefix + shortest
    assert "Bad München-Dorf" in names        # substring still found
    assert all(s["id"] != "4" for s in got)   # has_reach=False excluded
```

- [ ] **Step 2: Run, verify FAIL** — `uv run pytest tests/test_search.py -q`

- [ ] **Step 3: Implement** — add to `server/app.py` (module level + inside `create_app`, above the `{station_id}` route so `/search` isn't shadowed):

```python
import unicodedata


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
```

```python
    @app.get("/api/stations/search")
    def search(q: str, limit: int = 10) -> dict:
        nq = normalize(q)
        scored = []
        for s in _read(data_dir / "stations.json")["stations"]:
            if not s.get("has_reach"):
                continue
            name = normalize(s["name"])
            if name.startswith(nq):
                scored.append((0, len(name), s))
            elif nq in name:
                scored.append((1, len(name), s))
        scored.sort(key=lambda x: (x[0], x[1]))
        return {"stations": [s for _, _, s in scored[:limit]]}
```

- [ ] **Step 4: Run, verify PASS** — `uv run pytest tests/test_search.py tests/test_server.py -q` (server tests confirm no route shadowing)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: accent-insensitive station search"`

---

## Phase D — Web

### Task 13: Vite scaffold, types, API client, booking links

**Files:**
- Create: `web/` (Vite react-ts scaffold), `web/src/lib/types.ts`, `web/src/lib/api.ts`, `web/src/lib/booking.ts`, `web/.env.example`
- Test: `web/src/lib/booking.test.ts`

**Interfaces:**
- Produces: TS types mirroring the JSON contracts (`Station`, `Leg`, `Journey`, `Destination`, `ReachFile`, `Meta`); `api.getStations() / getReach(id) / searchStations(q) / getMeta()` fetching from `/api/...` (Vite proxy added in Task 17); `bookingUrl(origin: Station, dest: Station, ref: string): string`.

- [ ] **Step 1: Scaffold**

```bash
npm create vite@latest web -- --template react-ts
cd web && npm install && npm install maplibre-gl && npm install -D vitest
```

Add to `web/package.json` scripts: `"test": "vitest run"`. Ensure `web/tsconfig.json` has `"strict": true` (Vite default does).
`web/.env.example`: `VITE_TRAINLINE_REF=`

- [ ] **Step 2: Write failing test** (`web/src/lib/booking.test.ts`):

```typescript
import { describe, expect, it } from "vitest";
import { bookingUrl } from "./booking";

const frankfurt = { id: "8000105", name: "Frankfurt (Main) Hbf", lat: 50.1, lon: 8.66, country: "DE", has_reach: true };
const paris = { id: "8700011", name: "Paris Est", lat: 48.87, lon: 2.35, country: "FR", has_reach: true };

describe("bookingUrl", () => {
  it("builds a Trainline deep link with origin, destination, tomorrow's date", () => {
    const url = new URL(bookingUrl(frankfurt, paris, ""));
    expect(url.hostname).toBe("www.thetrainline.com");
    expect(url.searchParams.get("origin")).toBe("Frankfurt (Main) Hbf");
    expect(url.searchParams.get("destination")).toBe("Paris Est");
    expect(url.searchParams.get("outwardDate")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(url.searchParams.has("aff")).toBe(false);
  });

  it("appends the affiliate ref when configured", () => {
    const url = new URL(bookingUrl(frankfurt, paris, "OSE123"));
    expect(url.searchParams.get("aff")).toBe("OSE123");
  });
});
```

- [ ] **Step 3: Run, verify FAIL** — `cd web && npm test`

- [ ] **Step 4: Implement**

`web/src/lib/types.ts`:

```typescript
export interface Station {
  id: string; name: string; lat: number; lon: number; country: string; has_reach: boolean;
}
export interface Leg {
  train: string; dep: string; arr: string; from: string; to: string; via: string[];
}
export interface Journey { trains: number; duration_min: number; legs: Leg[] }
export interface Destination { id: string; direct_per_day: number; journeys: Journey[] }
export interface ReachFile {
  origin: string; computed_at: string; sample_date: string; destinations: Destination[];
}
export interface Meta { computed_at: string; sample_date: string }
```

`web/src/lib/api.ts`:

```typescript
import type { Meta, ReachFile, Station } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  getStations: () => get<{ stations: Station[] }>("/api/stations"),
  getReach: (id: string) => get<ReachFile>(`/api/reach/${id}`),
  searchStations: (q: string) =>
    get<{ stations: Station[] }>(`/api/stations/search?q=${encodeURIComponent(q)}`),
  getMeta: () => get<Meta>("/api/meta"),
};
```

`web/src/lib/booking.ts`:

```typescript
import type { Station } from "./types";

export function bookingUrl(origin: Station, dest: Station, ref: string): string {
  const tomorrow = new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 10);
  const params = new URLSearchParams({
    origin: origin.name,
    destination: dest.name,
    outwardDate: tomorrow,
  });
  if (ref) params.set("aff", ref);
  return `https://www.thetrainline.com/book/results?${params.toString()}`;
}
```

- [ ] **Step 5: Run, verify PASS** — `cd web && npm test`

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: web scaffold with typed API client and booking links"`

### Task 14: GeoJSON builders (dots, lines, smoothing)

**Files:**
- Create: `web/src/lib/geojson.ts`
- Test: `web/src/lib/geojson.test.ts`

**Interfaces:**
- Consumes: types (Task 13).
- Produces:
  - `bestJourney(d: Destination, maxTrains: 1 | 2 | 3): Journey | null` — fastest journey using ≤ maxTrains.
  - `timeBucket(min: number): 0 | 1 | 2 | 3` — <180 → 0, <360 → 1, <600 → 2, else 3.
  - `destinationsGeoJSON(reach, stationsById, maxTrains, maxMinutes)` — Point features, props `{ id, name, duration_min, trains, bucket, direct_per_day }`; destinations over `maxMinutes` or without a qualifying journey are omitted.
  - `linesGeoJSON(reach, stationsById, maxTrains, maxMinutes)` — one LineString per shown destination through every leg's via-stations (coords: origin → via… → transfer → via… → dest), smoothed with `chaikin(coords, 2)`, props `{ id, bucket, trains }`.
  - `chaikin(coords: [number, number][], iterations: number): [number, number][]` — corner-cutting smoothing, endpoints preserved.

- [ ] **Step 1: Write failing tests** (`web/src/lib/geojson.test.ts`):

```typescript
import { describe, expect, it } from "vitest";
import { bestJourney, chaikin, destinationsGeoJSON, linesGeoJSON, timeBucket } from "./geojson";
import type { ReachFile, Station } from "./types";

const S = (id: string, lon: number): Station =>
  ({ id, name: id, lat: 50, lon, country: "XX", has_reach: true });
const stationsById = new Map(["A", "B", "C", "D"].map((id, i) => [id, S(id, 8 + i)]));

const reach: ReachFile = {
  origin: "A", computed_at: "", sample_date: "2026-07-14",
  destinations: [
    { id: "C", direct_per_day: 1, journeys: [
      { trains: 1, duration_min: 120, legs: [{ train: "IC 100", dep: "08:00", arr: "10:00", from: "A", to: "C", via: ["B"] }] } ] },
    { id: "D", direct_per_day: 0, journeys: [
      { trains: 2, duration_min: 240, legs: [
        { train: "IC 100", dep: "08:00", arr: "10:00", from: "A", to: "C", via: ["B"] },
        { train: "TGV 10", dep: "10:30", arr: "12:00", from: "C", to: "D", via: [] } ] } ] },
  ],
};

describe("bestJourney / timeBucket", () => {
  it("respects the train budget", () => {
    expect(bestJourney(reach.destinations[1], 1)).toBeNull();
    expect(bestJourney(reach.destinations[1], 2)?.duration_min).toBe(240);
  });
  it("buckets by duration", () => {
    expect([timeBucket(100), timeBucket(200), timeBucket(400), timeBucket(700)]).toEqual([0, 1, 2, 3]);
  });
});

describe("geojson builders", () => {
  it("nonstop view hides multi-train destinations", () => {
    const fc = destinationsGeoJSON(reach, stationsById, 1, Infinity);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("max-minutes filter applies", () => {
    const fc = destinationsGeoJSON(reach, stationsById, 3, 130);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("lines pass through via and transfer stations", () => {
    const fc = linesGeoJSON(reach, stationsById, 3, Infinity);
    const d = fc.features.find((f) => f.properties.id === "D")!;
    const lons = (d.geometry.coordinates as [number, number][]).map(([lon]) => lon);
    expect(lons[0]).toBe(8);                       // origin A preserved
    expect(lons[lons.length - 1]).toBe(11);        // dest D preserved
    expect(Math.max(...lons)).toBe(11);            // monotone-ish through B(9), C(10)
  });
});

describe("chaikin", () => {
  it("preserves endpoints and adds points", () => {
    const input: [number, number][] = [[0, 0], [1, 1], [2, 0]];
    const out = chaikin(input, 2);
    expect(out[0]).toEqual([0, 0]);
    expect(out[out.length - 1]).toEqual([2, 0]);
    expect(out.length).toBeGreaterThan(input.length);
  });
});
```

- [ ] **Step 2: Run, verify FAIL** — `cd web && npm test`

- [ ] **Step 3: Implement** (`web/src/lib/geojson.ts`):

```typescript
import type { Destination, Journey, ReachFile, Station } from "./types";

export type MaxTrains = 1 | 2 | 3;

export function bestJourney(d: Destination, maxTrains: MaxTrains): Journey | null {
  const eligible = d.journeys.filter((j) => j.trains <= maxTrains);
  return eligible.length
    ? eligible.reduce((a, b) => (b.duration_min < a.duration_min ? b : a))
    : null;
}

export function timeBucket(min: number): 0 | 1 | 2 | 3 {
  if (min < 180) return 0;
  if (min < 360) return 1;
  if (min < 600) return 2;
  return 3;
}

export function chaikin(coords: [number, number][], iterations: number): [number, number][] {
  let pts = coords;
  for (let it = 0; it < iterations; it++) {
    if (pts.length < 3) break;
    const next: [number, number][] = [pts[0]];
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, ay] = pts[i];
      const [bx, by] = pts[i + 1];
      next.push([ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25]);
      next.push([ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75]);
    }
    next.push(pts[pts.length - 1]);
    pts = next;
  }
  return pts;
}

type FC<G> = { type: "FeatureCollection"; features: Feature<G>[] };
type Feature<G> = { type: "Feature"; geometry: G; properties: Record<string, unknown> & { id: string } };
type Point = { type: "Point"; coordinates: [number, number] };
type LineString = { type: "LineString"; coordinates: [number, number][] };

function shown(reach: ReachFile, maxTrains: MaxTrains, maxMinutes: number) {
  return reach.destinations
    .map((d) => ({ d, j: bestJourney(d, maxTrains) }))
    .filter((x): x is { d: Destination; j: Journey } => x.j !== null && x.j.duration_min <= maxMinutes);
}

export function destinationsGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
): FC<Point> {
  const features: Feature<Point>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const s = stationsById.get(d.id);
    if (!s) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [s.lon, s.lat] },
      properties: {
        id: d.id, name: s.name, duration_min: j.duration_min, trains: j.trains,
        bucket: timeBucket(j.duration_min), direct_per_day: d.direct_per_day,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function linesGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
): FC<LineString> {
  const features: Feature<LineString>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const ids = [j.legs[0].from, ...j.legs.flatMap((leg) => [...leg.via, leg.to])];
    const coords = ids
      .map((id) => stationsById.get(id))
      .filter((s): s is Station => s !== undefined)
      .map((s): [number, number] => [s.lon, s.lat]);
    if (coords.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: chaikin(coords, 2) },
      properties: { id: d.id, bucket: timeBucket(j.duration_min), trains: j.trains },
    });
  }
  return { type: "FeatureCollection", features };
}
```

- [ ] **Step 4: Run, verify PASS** — `cd web && npm test`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: geojson builders with tier/time filtering and smoothing"`

### Task 15: Map component with reachability layers

**Files:**
- Create: `web/src/components/Map.tsx`, `web/src/lib/colors.ts`
- Modify: `web/src/index.css` (import maplibre css)

**Interfaces:**
- Consumes: geojson builders (Task 14).
- Produces: `<MapView stations={Station[]} reach={ReachFile | null} maxTrains={MaxTrains} maxMinutes={number} onSelectOrigin={(id: string) => void} onSelectDestination={(id: string) => void} />`. Colors module: `BUCKET_COLORS = ["#1a9850", "#fee08b", "#f46d43", "#d73027"]` and `BUCKET_LABELS = ["< 3 h", "3–6 h", "6–10 h", "> 10 h"]`.

- [ ] **Step 1: Implement colors** (`web/src/lib/colors.ts`):

```typescript
export const BUCKET_COLORS = ["#1a9850", "#fee08b", "#f46d43", "#d73027"] as const;
export const BUCKET_LABELS = ["< 3 h", "3–6 h", "6–10 h", "> 10 h"] as const;
```

- [ ] **Step 2: Implement Map component** (`web/src/components/Map.tsx`). Key decisions: one `maplibregl.Map` instance in a ref; OpenFreeMap `positron` style (muted, no key); three sources/layers — `all-stations` (small gray circles, click = new origin), `reach-lines` (line layer, `line-cap/join: round`, width `["case", ["==", ["get", "trains"], 1], 2.5, 1.5]`), `reach-dots` (circles colored by bucket, click = select destination):

```tsx
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { destinationsGeoJSON, linesGeoJSON, type MaxTrains } from "../lib/geojson";
import { BUCKET_COLORS } from "../lib/colors";
import type { ReachFile, Station } from "../lib/types";

const EMPTY = { type: "FeatureCollection", features: [] } as const;
const bucketColor = ["to-color", ["at", ["get", "bucket"], ["literal", BUCKET_COLORS]]];

interface Props {
  stations: Station[];
  reach: ReachFile | null;
  maxTrains: MaxTrains;
  maxMinutes: number;
  onSelectOrigin: (id: string) => void;
  onSelectDestination: (id: string) => void;
}

export default function MapView(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    const m = new maplibregl.Map({
      container: container.current!,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [8, 50],
      zoom: 4.5,
    });
    m.on("load", () => {
      m.addSource("all-stations", { type: "geojson", data: EMPTY as never });
      m.addSource("reach-lines", { type: "geojson", data: EMPTY as never });
      m.addSource("reach-dots", { type: "geojson", data: EMPTY as never });
      m.addLayer({
        id: "all-stations", type: "circle", source: "all-stations",
        paint: { "circle-radius": 3, "circle-color": "#9ca3af", "circle-opacity": 0.7 },
      });
      m.addLayer({
        id: "reach-lines", type: "line", source: "reach-lines",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": bucketColor as never,
          "line-width": ["case", ["==", ["get", "trains"], 1], 2.5, 1.5] as never,
          "line-opacity": 0.75,
        },
      });
      m.addLayer({
        id: "reach-dots", type: "circle", source: "reach-dots",
        paint: {
          "circle-radius": 5.5, "circle-color": bucketColor as never,
          "circle-stroke-width": 1, "circle-stroke-color": "#ffffff",
        },
      });
      m.on("click", "all-stations", (e) =>
        propsRef.current.onSelectOrigin(e.features![0].properties.id as string));
      m.on("click", "reach-dots", (e) =>
        propsRef.current.onSelectDestination(e.features![0].properties.id as string));
      for (const layer of ["all-stations", "reach-dots"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
      map.current = m;
      syncData();
    });
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncData() {
    const m = map.current;
    if (!m) return;
    const { stations, reach, maxTrains, maxMinutes } = propsRef.current;
    const byId = new Map(stations.map((s) => [s.id, s]));
    (m.getSource("all-stations") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: stations.filter((s) => s.has_reach).map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name },
      })),
    });
    (m.getSource("reach-lines") as maplibregl.GeoJSONSource).setData(
      reach ? (linesGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    (m.getSource("reach-dots") as maplibregl.GeoJSONSource).setData(
      reach ? (destinationsGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    const origin = reach && byId.get(reach.origin);
    if (origin) m.easeTo({ center: [origin.lon, origin.lat], zoom: 5 });
  }

  useEffect(syncData, [props.stations, props.reach, props.maxTrains, props.maxMinutes]);

  return <div ref={container} style={{ position: "absolute", inset: 0 }} />;
}
```

Add to `web/src/index.css` first line: `@import "maplibre-gl/dist/maplibre-gl.css";`

- [ ] **Step 3: Verify it compiles** — `cd web && npx tsc --noEmit && npm test` → PASS (visual check happens in Task 17 with the full app running)

- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: MapLibre map with reachability dot and line layers"`

### Task 16: Controls, JourneyCard, App wiring

**Files:**
- Create: `web/src/components/SearchBox.tsx`, `web/src/components/StopToggle.tsx`, `web/src/components/TimeSlider.tsx`, `web/src/components/Legend.tsx`, `web/src/components/JourneyCard.tsx`
- Modify: `web/src/App.tsx` (replace scaffold), `web/src/index.css` (app styles), delete `web/src/App.css` scaffold content

**Interfaces:**
- Consumes: api (13), geojson helpers (14), MapView (15), `bookingUrl` (13), colors (15).
- Produces: complete app. State lives in `App.tsx`: `stations`, `reach`, `maxTrains` (default **1** = Nonstop), `maxMinutes` (default 1440), `selectedDest`, `error`.

- [ ] **Step 1: Implement components**

`web/src/components/StopToggle.tsx`:

```tsx
import type { MaxTrains } from "../lib/geojson";

const OPTIONS: { value: MaxTrains; label: string }[] = [
  { value: 1, label: "Nonstop" },
  { value: 2, label: "One stop" },
  { value: 3, label: "Two stops" },
];

export default function StopToggle(props: { value: MaxTrains; onChange: (v: MaxTrains) => void }) {
  return (
    <div className="stop-toggle" role="group" aria-label="Maximum trains">
      {OPTIONS.map((o) => (
        <button key={o.value} className={o.value === props.value ? "active" : ""}
                onClick={() => props.onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
```

`web/src/components/TimeSlider.tsx`:

```tsx
export default function TimeSlider(props: { value: number; onChange: (v: number) => void }) {
  const label = props.value >= 1440 ? "any duration" : `≤ ${Math.round(props.value / 60)} h`;
  return (
    <label className="time-slider">
      Max travel time: <strong>{label}</strong>
      <input type="range" min={60} max={1440} step={60} value={props.value}
             onChange={(e) => props.onChange(Number(e.target.value))} />
    </label>
  );
}
```

`web/src/components/SearchBox.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Station } from "../lib/types";

export default function SearchBox(props: { onSelect: (s: Station) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Station[]>([]);

  useEffect(() => {
    if (q.length < 2) return setResults([]);
    const t = setTimeout(
      () => api.searchStations(q).then((r) => setResults(r.stations)).catch(() => setResults([])),
      250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="search-box">
      <input placeholder="Start from…" value={q} onChange={(e) => setQ(e.target.value)} />
      {results.length > 0 && (
        <ul>
          {results.map((s) => (
            <li key={s.id}>
              <button onClick={() => { props.onSelect(s); setQ(""); setResults([]); }}>
                {s.name} <span className="country">{s.country}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

`web/src/components/Legend.tsx`:

```tsx
import { BUCKET_COLORS, BUCKET_LABELS } from "../lib/colors";

export default function Legend() {
  return (
    <div className="legend">
      {BUCKET_COLORS.map((c, i) => (
        <span key={c}><i style={{ background: c }} /> {BUCKET_LABELS[i]}</span>
      ))}
    </div>
  );
}
```

`web/src/components/JourneyCard.tsx`:

```tsx
import { bookingUrl } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station } from "../lib/types";

const REF = import.meta.env.VITE_TRAINLINE_REF ?? "";

interface Props {
  origin: Station;
  destination: Station;
  dest: Destination;
  maxTrains: MaxTrains;
  stationsById: Map<string, Station>;
  onClose: () => void;
}

export default function JourneyCard({ origin, destination, dest, maxTrains, stationsById, onClose }: Props) {
  const journey = bestJourney(dest, maxTrains);
  if (!journey) return null;
  const h = Math.floor(journey.duration_min / 60);
  const m = journey.duration_min % 60;
  return (
    <div className="journey-card">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2>{origin.name} → {destination.name}</h2>
      <p className="duration">{h} h {m ? `${m} min` : ""} · {journey.trains === 1
        ? `nonstop · ${dest.direct_per_day}× per day`
        : `${journey.trains} trains`}</p>
      <ol className="legs">
        {journey.legs.map((leg) => (
          <li key={`${leg.train}-${leg.dep}`}>
            <strong>{leg.train}</strong> {leg.dep} {stationsById.get(leg.from)?.name ?? leg.from}
            {" → "} {leg.arr} {stationsById.get(leg.to)?.name ?? leg.to}
          </li>
        ))}
      </ol>
      <a className="book" href={bookingUrl(origin, destination, REF)} target="_blank" rel="noopener noreferrer">
        Book this trip
      </a>
      <p className="fineprint">Times from a sample weekday — pick your date at checkout.</p>
    </div>
  );
}
```

`web/src/App.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import MapView from "./components/Map";
import JourneyCard from "./components/JourneyCard";
import Legend from "./components/Legend";
import SearchBox from "./components/SearchBox";
import StopToggle from "./components/StopToggle";
import TimeSlider from "./components/TimeSlider";
import { api } from "./lib/api";
import type { MaxTrains } from "./lib/geojson";
import type { ReachFile, Station } from "./lib/types";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(1440);
  const [selectedDest, setSelectedDest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);

  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch((e) => setError(String(e)));
  }, []);

  function selectOrigin(id: string) {
    setSelectedDest(null);
    api.getReach(id).then(setReach).catch((e) => setError(String(e)));
  }

  const origin = reach ? stationsById.get(reach.origin) : undefined;
  const dest = selectedDest && reach
    ? reach.destinations.find((d) => d.id === selectedDest) : undefined;

  return (
    <div className="app">
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest} />
      <header className="panel">
        <h1>onestopeurope</h1>
        <p className="tagline">nonstopeurope with onestopeurope</p>
        <SearchBox onSelect={(s) => selectOrigin(s.id)} />
        <StopToggle value={maxTrains} onChange={setMaxTrains} />
        <TimeSlider value={maxMinutes} onChange={setMaxMinutes} />
        <Legend />
        {!reach && <p className="hint">Search or click a station to begin.</p>}
        {error && <p className="error">{error}</p>}
      </header>
      {origin && dest && stationsById.get(dest.id) && (
        <JourneyCard origin={origin} destination={stationsById.get(dest.id)!} dest={dest}
                     maxTrains={maxTrains} stationsById={stationsById}
                     onClose={() => setSelectedDest(null)} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Styles** — replace `web/src/index.css` body with (keep the maplibre import first):

```css
@import "maplibre-gl/dist/maplibre-gl.css";

* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; }
.app { position: fixed; inset: 0; }
.panel {
  position: absolute; top: 16px; left: 16px; z-index: 10; width: 300px;
  background: #fff; border-radius: 12px; padding: 16px;
  box-shadow: 0 4px 16px rgb(0 0 0 / 0.15); display: flex; flex-direction: column; gap: 10px;
}
.panel h1 { margin: 0; font-size: 22px; }
.tagline { margin: 0; color: #6b7280; font-size: 13px; }
.search-box { position: relative; }
.search-box input { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }
.search-box ul {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 20; margin: 4px 0 0; padding: 0;
  list-style: none; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}
.search-box li button { display: block; width: 100%; text-align: left; padding: 8px; border: 0; background: none; cursor: pointer; }
.search-box li button:hover { background: #f3f4f6; }
.search-box .country { color: #9ca3af; font-size: 12px; }
.stop-toggle { display: flex; border: 1px solid #d1d5db; border-radius: 8px; overflow: hidden; }
.stop-toggle button { flex: 1; padding: 8px 4px; border: 0; background: #fff; cursor: pointer; font-size: 13px; }
.stop-toggle button.active { background: #111827; color: #fff; }
.time-slider { font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.legend { display: flex; gap: 10px; font-size: 12px; flex-wrap: wrap; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 3px; }
.hint, .error { font-size: 13px; color: #6b7280; margin: 0; }
.error { color: #dc2626; }
.journey-card {
  position: absolute; bottom: 16px; left: 16px; z-index: 10; width: 340px;
  background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 4px 16px rgb(0 0 0 / 0.15);
}
.journey-card h2 { margin: 0 0 4px; font-size: 16px; }
.journey-card .duration { margin: 0 0 8px; color: #374151; }
.journey-card .legs { margin: 0 0 12px; padding-left: 18px; font-size: 13px; }
.journey-card .close { position: absolute; top: 8px; right: 12px; border: 0; background: none; font-size: 18px; cursor: pointer; }
.journey-card .book {
  display: block; text-align: center; background: #111827; color: #fff;
  padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 600;
}
.journey-card .fineprint { margin: 8px 0 0; font-size: 11px; color: #9ca3af; }
```

Also update `web/index.html` `<title>` to `onestopeurope` and remove the scaffold's `App.css` import from `App.tsx` (done above) and delete `web/src/App.css`.

- [ ] **Step 3: Verify** — `cd web && npx tsc --noEmit && npm test && npm run build` → all pass

- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: full app UI - search, stop toggle, slider, journey card"`

### Task 17: Dev experience — proxy, just dev, VS Code debugging

**Files:**
- Modify: `web/vite.config.ts`, `justfile`
- Create: `.vscode/launch.json`, `.vscode/tasks.json`

**Interfaces:**
- Produces: `just dev` runs API (:8000) + web (:5173) together; Vite proxies `/api` to the backend; F5 in VS Code launches both with debuggers attached.

- [ ] **Step 1: Vite proxy** (`web/vite.config.ts`):

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
```

- [ ] **Step 2: justfile dev target** (append):

```just
# Run API and web dev servers together (Ctrl-C stops both)
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn server.app:app --reload --port 8000 &
    (cd web && npm run dev) &
    wait
```

- [ ] **Step 3: VS Code configs**

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "API (FastAPI)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["server.app:app", "--reload", "--port", "8000"],
      "python": "${workspaceFolder}/.venv/bin/python"
    },
    {
      "name": "Web (Chrome)",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/web/src",
      "preLaunchTask": "vite-dev"
    }
  ],
  "compounds": [
    { "name": "Full stack", "configurations": ["API (FastAPI)", "Web (Chrome)"] }
  ]
}
```

`.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "vite-dev",
      "type": "shell",
      "command": "npm run dev",
      "options": { "cwd": "${workspaceFolder}/web" },
      "isBackground": true,
      "problemMatcher": {
        "pattern": { "regexp": "." },
        "background": { "activeOnStart": true, "beginsPattern": ".", "endsPattern": "Local:" }
      }
    }
  ]
}
```

- [ ] **Step 4: Verify** — run `just dev`; check `curl -s localhost:8000/api/meta` returns 503 JSON (pipeline hasn't run) and `curl -s localhost:5173/api/meta` returns the same through the proxy. Stop with Ctrl-C.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: one-command dev with proxy and VS Code full-stack debugging"`

### Task 18: First real pipeline run, sample data, README

**Files:**
- Create: `data/out/` samples (force-added), final `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: a repo where `git clone && just dev` shows a working map.

- [ ] **Step 1: Run the real pipeline**

```bash
just pipeline
```

Expected: fetch reports per-feed success/failure (a failed feed is OK — fix its URL in `feeds.toml` if trivially wrong, otherwise continue with the feeds that work); build prints station/trip counts and passes validation (add `station_aliases.toml` entries if it reports unmerged duplicates); compute writes `data/out/reach_*.json`.

- [ ] **Step 2: Sanity-check real data**

```bash
uv run python -c "
import json
d = json.load(open('data/out/reach_8000105.json'))  # Frankfurt Hbf
best = {x['id']: x['journeys'][0]['duration_min'] for x in d['destinations']}
print(len(best), 'destinations from Frankfurt')
assert len(best) > 20
"
```

Then `just dev`, open http://localhost:5173, and verify by hand: search "Frankfurt" → select → dots+lines appear; toggle One stop → more dots; click a dot → journey card → Book link opens Trainline with origin/destination prefilled.

- [ ] **Step 3: Commit sample data** (stations.json + meta.json + 5 major stations so fresh clones work without running the pipeline):

```bash
git add -f data/out/stations.json data/out/meta.json
git add -f data/out/reach_8000105.json data/out/reach_8000261.json data/out/reach_8011160.json data/out/reach_8000191.json data/out/reach_8002549.json
git commit -m "data: sample precomputed reachability for fresh clones"
```

(EVAs: Frankfurt, München, Berlin, Karlsruhe, Hamburg Hbf — substitute whatever IDs the merged registry actually produced; check `data/out/stations.json`.)

- [ ] **Step 4: Final README.md** (replace stub; keep under 100 lines):

```markdown
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

## How it works

- `pipeline/` downloads national long-distance GTFS feeds, merges stations
  across feeds (UIC codes, proximity, aliases), and runs a RAPTOR search
  (max 3 trains, 10-min minimum transfer) for one representative weekday.
- `server/` is a thin FastAPI that serves the precomputed JSON in `data/out/`.
- `web/` is Vite + React + MapLibre GL (OpenFreeMap tiles).

## Development

    just test         # Python tests
    (cd web && npm test)
    just lint

VS Code: "Full stack" launch config debugs API + browser together.

Design docs: `docs/superpowers/specs/`, plans: `docs/superpowers/plans/`.
```

- [ ] **Step 5: Full verification and commit**

Run: `uv run pytest -q && uv run ruff check . && (cd web && npm test && npm run build)`
Expected: everything green.

```bash
git add -A && git commit -m "docs: honest README with quickstart"
```

---

## Self-Review Notes

- **Spec coverage:** name/tagline (T16, T18), Nonstop/One stop/Two stops default Nonstop (T16), travel-time coloring (T14/15), via-station stylized lines with smoothing (T14/15), fixed 10-min transfer (T9), Trainline ref-ready deep link built client-side (T13), search accent-insensitive prefix-weighted (T12), 404/503 (T11), feeds.toml with 5 feeds + per-feed filters (T3), failure isolation (T4), UIC/proximity/alias merging incl. border stations (T7), validation that fails loudly (T8), representative Tuesday (T6), weekly rerun = `just pipeline` (T2/T18), sample data for fresh clones (T18), one-command dev + VS Code compound debug (T17), clean-slate migration (T1). Licensing check is a spec *risk*, noted in feeds.toml license fields — no code task needed.
- **Known simplification:** RAPTOR scans all trips per round (no route-indexing optimization). At long-distance scale (~10–30k trips) × ~2k origins × 16 departure floors this is minutes-not-hours in Python; if the real run is too slow, index trips by station before optimizing further. Correctness is what the fixture locks down.
- **Type consistency:** `Leg.from` alias round-trips through pipeline (pydantic `by_alias`) → server (verbatim files) → web (`from` property in TS). `MaxTrains` = `maxTrains` prop everywhere. `has_reach` flag drives both search filtering (T12) and marker layer (T15).
